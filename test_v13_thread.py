"""
test_v13_thread.py
WavSaveWorker（QThread）のバックグラウンド保存テスト
"""
import os, sys, struct, wave, math, time
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(__file__))

import pygame
pygame.mixer.pre_init(44100, -16, 2, 256)
pygame.mixer.init()

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QEventLoop, QTimer

from audio_engine import AudioEngine
from main_window import WavSaveWorker

app = QApplication(sys.argv)

def make_wav(path, freq=440, duration=1.0):
    sr = 44100
    frames = int(sr * duration)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(frames):
            v = int(math.sin(2 * math.pi * freq * i / sr) * 16000)
            wf.writeframes(struct.pack("<hh", v, v))

wav1 = "/tmp/thread_test_a.wav"
wav2 = "/tmp/thread_test_b.wav"
make_wav(wav1, 440, 1.0)
make_wav(wav2, 880, 1.0)

engine = AudioEngine(16)
engine.load_file(0, wav1)
engine.load_file(1, wav2)

# 録音
engine.start_recording()
time.sleep(0.05)
engine.play(0)
time.sleep(0.2)
engine.play(1)
time.sleep(0.2)
events = engine.stop_recording()
assert len(events) >= 1, f"イベント数が0"

out_path = "/tmp/thread_test_recording.wav"

# WavSaveWorker でバックグラウンド保存
results = []

def on_done(ok, path):
    results.append((ok, path))
    loop.quit()

loop = QEventLoop()
worker = WavSaveWorker(engine, out_path, events)
worker.finished.connect(on_done)

# タイムアウト（10秒）
timeout = QTimer()
timeout.setSingleShot(True)
timeout.timeout.connect(lambda: (results.append((False, "timeout")), loop.quit()))
timeout.start(10000)

worker.start()
loop.exec_()

assert results, "コールバックが呼ばれなかった"
ok, path = results[0]
assert path != "timeout", "タイムアウト: バックグラウンド保存が10秒以内に完了しなかった"
assert ok, f"WAV保存失敗"
assert os.path.isfile(out_path), "出力ファイルが存在しない"

# 出力WAVが無音でないことを確認
with wave.open(out_path) as wf:
    raw = wf.readframes(wf.getnframes())
import struct as st
samples = st.unpack(f"<{len(raw)//2}h", raw)
max_val = max(abs(s) for s in samples)
assert max_val > 1000, f"出力WAVが無音 (max={max_val})"

print(f"[OK] WavSaveWorker バックグラウンド保存成功 (max_sample={max_val})")
print("[ALL PASS] v1.3 フリーズ修正テスト通過 ✓")
