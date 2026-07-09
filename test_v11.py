"""
test_v11.py - MPC Sampler v1.1 統合テスト
再トリガー・録音・WAVミックスダウン保存を検証する
"""
import os
import sys
import struct
import wave
import math

os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_VIDEODRIVER'] = 'dummy'

sys.path.insert(0, os.path.dirname(__file__))
from audio_engine import AudioEngine


def make_test_wav(path, freq=440, duration=0.5):
    sr = 44100
    frames = int(sr * duration)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(frames):
            v = int(math.sin(2 * math.pi * freq * i / sr) * 16000)
            wf.writeframes(struct.pack('<hh', v, v))


def test_all():
    make_test_wav('/tmp/test_kick.wav', 80, 0.3)
    make_test_wav('/tmp/test_snare.wav', 200, 0.2)

    engine = AudioEngine(16)

    # テスト1: ファイル読み込み
    ok1 = engine.load_file(0, '/tmp/test_kick.wav')
    ok2 = engine.load_file(1, '/tmp/test_snare.wav')
    assert ok1 and ok2, 'load_file failed'
    print('[OK] ファイル読み込み')

    # テスト2: 再トリガー（play を2回呼んでもエラーにならない）
    engine.play(0)
    engine.play(0)  # 再トリガー
    print('[OK] 再トリガー再生（エラーなし）')

    # テスト3: 録音開始・イベント記録・停止
    engine.start_recording()
    assert engine.is_recording(), 'recording should be True'
    engine.play(0)
    engine.play(1)
    engine.play(0)
    events = engine.stop_recording()
    assert not engine.is_recording(), 'recording should be False after stop'
    assert len(events) == 3, f'expected 3 events, got {len(events)}'
    print(f'[OK] 録音イベント記録: {len(events)} events')

    # テスト4: 録音中でない場合の play はイベントを記録しない
    engine.play(0)
    engine.play(1)
    assert len(engine._record_events) == 0, 'should not record when not recording'
    print('[OK] 非録音中はイベント記録なし')

    # テスト5: WAVミックスダウン保存
    # 録音イベントを手動で再設定
    engine._record_events = [(0, 0.0), (1, 0.1), (0, 0.3)]
    ok3 = engine.save_recording_as_wav('/tmp/test_output.wav')
    assert ok3, 'save_recording_as_wav failed'
    assert os.path.isfile('/tmp/test_output.wav'), 'output WAV not found'
    with wave.open('/tmp/test_output.wav', 'rb') as wf:
        frames = wf.getnframes()
        ch = wf.getnchannels()
        sr = wf.getframerate()
        assert frames > 0, 'output WAV has no frames'
        assert ch == 2, f'expected stereo, got {ch}ch'
        assert sr == 44100, f'expected 44100Hz, got {sr}Hz'
        print(f'[OK] WAV保存: {frames} frames ({frames/44100:.2f}s), {ch}ch, {sr}Hz')

    # テスト6: イベントなしの場合は False を返す
    engine._record_events = []
    ok4 = engine.save_recording_as_wav('/tmp/test_empty.wav')
    assert not ok4, 'should return False when no events'
    print('[OK] イベントなし時は保存スキップ')

    engine.shutdown()
    print()
    print('[ALL PASS] 全テスト通過 ✓')


if __name__ == '__main__':
    test_all()
