"""
test_v12.py
v1.2 の主要機能テスト:
  1. トグル再生: 再生中に play() を呼ぶと停止する
  2. 停止後に再度 play() で再生できる
  3. 録音 + WAV 保存（events を直接渡す方式）
  4. stop_recording() 後に save_recording_as_wav() が失敗しない（バグ修正確認）
"""

import os
import sys
import struct
import wave
import math

os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_VIDEODRIVER"] = "dummy"

sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.mixer.pre_init(44100, -16, 2, 256)
pygame.mixer.init()

from audio_engine import AudioEngine

# --- テスト用 WAV を生成 ---
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

wav1 = "/tmp/test_v12_a.wav"
wav2 = "/tmp/test_v12_b.wav"
make_wav(wav1, 440)
make_wav(wav2, 880)

engine = AudioEngine(16)
assert engine.load_file(0, wav1), "WAV1 読み込み失敗"
assert engine.load_file(1, wav2), "WAV2 読み込み失敗"

# --- テスト1: トグル再生（再生中に押すと停止） ---
engine.play(0)
import time; time.sleep(0.05)
was_playing = engine.is_playing(0)
engine.play(0)  # 再生中 → 停止
time.sleep(0.05)
is_stopped = not engine.is_playing(0)
assert was_playing, "テスト1失敗: 再生開始されていない"
assert is_stopped, "テスト1失敗: 停止されていない"
print("[OK] テスト1: トグル再生（再生中 → 停止）")

# --- テスト2: 停止後に再度再生できる ---
engine.play(0)
time.sleep(0.05)
assert engine.is_playing(0), "テスト2失敗: 停止後に再生できない"
print("[OK] テスト2: 停止後に再度再生できる")

# --- テスト3: 録音 + WAV 保存 ---
engine.start_recording()
time.sleep(0.1)
engine.play(0)
time.sleep(0.2)
engine.play(1)
time.sleep(0.2)
events = engine.stop_recording()
assert len(events) >= 1, f"テスト3失敗: イベント数が {len(events)} (期待: 1以上)"

out_path = "/tmp/test_v12_recording.wav"
ok = engine.save_recording_as_wav(out_path, events)
assert ok, "テスト3失敗: WAV保存失敗"
assert os.path.isfile(out_path), "テスト3失敗: ファイルが存在しない"
with wave.open(out_path) as wf:
    frames = wf.getnframes()
assert frames > 0, "テスト3失敗: WAVが空"
print(f"[OK] テスト3: 録音 + WAV保存成功 ({frames} frames)")

# --- テスト4: stop_recording() 後に save_recording_as_wav() が失敗しない（バグ修正確認） ---
engine.start_recording()
time.sleep(0.05)
engine.play(0)
time.sleep(0.05)
events2 = engine.stop_recording()
# stop_recording() 後に内部リストは空になっているはず
# events2 を直接渡すので保存は成功するはず
out_path2 = "/tmp/test_v12_recording2.wav"
ok2 = engine.save_recording_as_wav(out_path2, events2)
assert ok2, "テスト4失敗: stop_recording()後のWAV保存失敗（バグ再発）"
print("[OK] テスト4: stop_recording()後もevents渡しで保存成功（バグ修正確認）")

# --- テスト5: イベントなしで save_recording_as_wav() が False を返す ---
ok3 = engine.save_recording_as_wav("/tmp/test_v12_empty.wav", [])
assert not ok3, "テスト5失敗: 空イベントでTrueが返った"
print("[OK] テスト5: 空イベントで正しくFalseを返す")

print("\n[ALL PASS] v1.2 テスト全通過 ✓")
