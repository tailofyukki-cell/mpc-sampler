"""
test_v11_fix.py
バグ修正確認テスト:
  stop_recording() → ダイアログ → save_recording_as_wav(path, events) の流れを検証
"""
import os
import sys
import wave
import time

os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_VIDEODRIVER"] = "dummy"

sys.path.insert(0, os.path.dirname(__file__))
from audio_engine import AudioEngine

def make_wav(path: str, duration_sec: float = 0.5):
    import struct
    import math
    sr = 44100
    frames = int(sr * duration_sec)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(frames):
            v = int(math.sin(2 * math.pi * 440 * i / sr) * 8000)
            wf.writeframes(struct.pack("<hh", v, v))

def test_stop_then_save():
    """stop_recording() 後に events を渡して save_recording_as_wav() が成功するか確認"""
    engine = AudioEngine(16)

    wav_path = "/tmp/test_pad.wav"
    make_wav(wav_path, 0.3)
    assert engine.load_file(0, wav_path), "load_file failed"

    engine.start_recording()
    time.sleep(0.05)
    engine.play(0)
    time.sleep(0.05)
    engine.play(0)
    time.sleep(0.05)

    # stop_recording() でイベントを取得（内部リストはクリアされる）
    events = engine.stop_recording()
    assert len(events) == 2, f"expected 2 events, got {len(events)}"

    # 内部リストがクリアされていることを確認
    assert engine._record_events == [], "internal list should be cleared"

    # events を直接渡して保存
    out_path = "/tmp/test_recording_fix.wav"
    ok = engine.save_recording_as_wav(out_path, events)
    assert ok, "save_recording_as_wav should succeed when events are passed directly"
    assert os.path.isfile(out_path), "output WAV file should exist"

    with wave.open(out_path, "rb") as wf:
        frames = wf.getnframes()
        assert frames > 0, "output WAV should have frames"
        print(f"[OK] 修正確認: events渡し保存成功 ({frames} frames)")

    # 内部リストが空の場合（eventsなし）は失敗することを確認
    ok2 = engine.save_recording_as_wav(out_path)  # events=None, 内部リストは空
    assert not ok2, "should fail when internal list is empty and events not passed"
    print("[OK] 修正確認: 内部リスト空・eventsなしは正しく失敗")

    engine.shutdown()
    print("[ALL PASS] バグ修正確認テスト通過 ✓")

if __name__ == "__main__":
    test_stop_then_save()
