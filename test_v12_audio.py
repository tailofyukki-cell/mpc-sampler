"""
test_v12_audio.py
録音WAVが実際に無音でないことを確認する追加テスト
"""
import os, sys, struct, wave, math
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.mixer.pre_init(44100, -16, 2, 256)
pygame.mixer.init()

from audio_engine import AudioEngine
import time

def make_wav(path, freq=440, duration=0.5):
    sr = 44100
    frames = int(sr * duration)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(frames):
            v = int(math.sin(2 * math.pi * freq * i / sr) * 16000)
            wf.writeframes(struct.pack("<hh", v, v))

wav1 = "/tmp/audio_test_a.wav"
wav2 = "/tmp/audio_test_b.wav"
make_wav(wav1, 440)
make_wav(wav2, 880)

engine = AudioEngine(16)
engine.load_file(0, wav1)
engine.load_file(1, wav2)

# 録音してWAV保存
engine.start_recording()
time.sleep(0.05)
engine.play(0)
time.sleep(0.2)
engine.play(1)
time.sleep(0.2)
events = engine.stop_recording()

out_path = "/tmp/audio_test_recording.wav"
ok = engine.save_recording_as_wav(out_path, events)
assert ok, "WAV保存失敗"

# 出力WAVの音声データを確認
with wave.open(out_path) as wf:
    total_frames = wf.getnframes()
    raw = wf.readframes(total_frames)

import struct as st
n = len(raw) // 2
samples = st.unpack(f"<{n}h", raw)
max_val = max(abs(s) for s in samples)
non_zero = sum(1 for s in samples if s != 0)

print(f"出力WAV: {total_frames} frames, max_sample={max_val}, non_zero_samples={non_zero}")

assert max_val > 1000, f"バグ: 出力WAVがほぼ無音 (max={max_val})"
assert non_zero > 1000, f"バグ: 出力WAVのほとんどのサンプルがゼロ (non_zero={non_zero})"

print(f"[OK] 録音WAVに正常な音声データが含まれている (max={max_val}, non_zero={non_zero})")
print("[ALL PASS] 無音バグ修正確認 ✓")
