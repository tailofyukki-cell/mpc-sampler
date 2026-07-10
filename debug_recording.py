"""
debug_recording.py
録音WAVが無音になる原因を診断する
"""
import os, sys, struct, wave, math
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.mixer.pre_init(44100, -16, 2, 256)
pygame.mixer.init()

import pygame.sndarray
import numpy as np

# テスト用WAVを生成
def make_wav(path, freq=440, duration=0.3):
    sr = 44100
    frames = int(sr * duration)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(frames):
            v = int(math.sin(2 * math.pi * freq * i / sr) * 16000)
            wf.writeframes(struct.pack("<hh", v, v))

wav1 = "/tmp/debug_a.wav"
make_wav(wav1, 440)

# pygame.mixer.Soundで読み込む
snd = pygame.mixer.Sound(wav1)
print(f"Sound length: {snd.get_length():.3f}s")

# sndarray で配列取得
try:
    arr = pygame.sndarray.array(snd)
    print(f"Array shape: {arr.shape}, dtype: {arr.dtype}")
    print(f"Array ndim: {arr.ndim}")
    print(f"Array max: {arr.max()}, min: {arr.min()}")
    print(f"Array sample[100]: {arr[100]}")
    
    # 最大値が0なら無音
    if arr.max() == 0 and arr.min() == 0:
        print("⚠ 警告: sndarray が全ゼロ（無音）を返している")
    else:
        print("✓ sndarray は正常なデータを返している")
        
except Exception as e:
    print(f"sndarray エラー: {e}")

# 別の方法: get_raw() でバイト列を取得
try:
    raw = snd.get_raw()
    print(f"\nget_raw() length: {len(raw)} bytes")
    # 最初の数サンプルを確認
    samples = struct.unpack(f"<{min(10, len(raw)//2)}h", raw[:min(20, len(raw))])
    print(f"get_raw() first samples: {samples}")
    if all(s == 0 for s in samples):
        print("⚠ 警告: get_raw() が全ゼロを返している")
    else:
        print("✓ get_raw() は正常なデータを返している")
except Exception as e:
    print(f"get_raw() エラー: {e}")

# WAVファイルを直接読み込んで確認
print("\n--- 元のWAVファイルを直接確認 ---")
with wave.open(wav1) as wf:
    frames = wf.readframes(10)
    samples = struct.unpack(f"<{len(frames)//2}h", frames)
    print(f"WAV direct read first samples: {samples}")

# save_recording_as_wav の代替実装テスト（get_raw() 使用）
print("\n--- get_raw() を使ったミックスダウンテスト ---")
SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_WIDTH = 2

events = [(0, 0.0), (0, 0.1)]  # パッド0を0秒と0.1秒で再生

raw = snd.get_raw()
raw_len = len(raw) // (SAMPLE_WIDTH * CHANNELS)
print(f"Sound frames from get_raw(): {raw_len}")

# 総フレーム数
max_ts = max(ts for _, ts in events)
total_frames = int((max_ts + snd.get_length() + 0.5) * SAMPLE_RATE)
print(f"Total output frames: {total_frames}")

# numpy でミックス
mix = np.zeros((total_frames, 2), dtype=np.float64)

for pad_idx, ts in events:
    start = int(ts * SAMPLE_RATE)
    # get_raw() からnumpy配列に変換
    raw_bytes = snd.get_raw()
    n = len(raw_bytes) // (SAMPLE_WIDTH * CHANNELS)
    arr_raw = np.frombuffer(raw_bytes, dtype=np.int16).reshape(n, CHANNELS).astype(np.float64)
    end = min(start + n, total_frames)
    length = end - start
    mix[start:end] += arr_raw[:length] / 32768.0

# クリッピング
mix = np.clip(mix, -1.0, 1.0)
mix_int16 = (mix * 32767).astype(np.int16)

out_path = "/tmp/debug_recording.wav"
with wave.open(out_path, "wb") as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(mix_int16.tobytes())

# 出力WAVを確認
with wave.open(out_path) as wf:
    frames_out = wf.readframes(100)
    samples_out = struct.unpack(f"<{len(frames_out)//2}h", frames_out)
    max_val = max(abs(s) for s in samples_out)
    print(f"Output WAV max sample value: {max_val}")
    if max_val == 0:
        print("⚠ 出力WAVが無音")
    else:
        print(f"✓ 出力WAVに音声データあり (max={max_val})")
