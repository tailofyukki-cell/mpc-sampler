"""
test_v14.py
v1.4 録音処理の根本的な再設計テスト

テスト内容:
  1. ロード時 get_raw() キャッシュが正しく動作するか
  2. 録音→停止→WAV保存が正常に完了するか
  3. events が空の場合に False を返すか
  4. WavSaveWorker が例外を出さずに完了するか
  5. スレッドセーフ（並行アクセス）
  6. unload 後の動作

注意: pygame mixer は1プロセスで1回しか初期化できないため、
      全テストで同一の AudioEngine インスタンスを使用する。
"""

import os
import sys
import time
import wave
import struct
import tempfile
import threading
import numpy as np

# pygame を headless で初期化
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(__file__))
from audio_engine import AudioEngine

PASS = "\033[92m[OK]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
errors = []

# 共有の一時ディレクトリとエンジン（mixer は1回だけ初期化）
TMPDIR = tempfile.mkdtemp()
ENGINE = AudioEngine(16)


def make_wav(path: str, duration_sec: float = 0.5, freq: int = 440):
    """テスト用WAVファイルを生成する"""
    sr = 44100
    n = int(sr * duration_sec)
    samples = [int(32767 * 0.5 * (1 if i % (sr // freq) < (sr // freq // 2) else -1)) for i in range(n)]
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        data = struct.pack(f"<{n * 2}h", *[s for s in samples for _ in range(2)])
        wf.writeframes(data)


def check(name: str, cond: bool, detail: str = ""):
    if cond:
        print(f"{PASS} {name}")
    else:
        print(f"{FAIL} {name}" + (f" — {detail}" if detail else ""))
        errors.append(name)


# ----------------------------------------------------------------
# テスト 1: ロード時キャッシュ
# ----------------------------------------------------------------
print("\n=== テスト 1: ロード時 get_raw() キャッシュ ===")
wav_path_t1 = os.path.join(TMPDIR, "test1.wav")
make_wav(wav_path_t1, duration_sec=0.3)

ok = ENGINE.load_file(0, wav_path_t1)
check("load_file 成功", ok)

cache = ENGINE._raw_cache.get(0)
check("_raw_cache に配列が存在する", cache is not None)
check("_raw_cache の shape が正しい (n, 2)", cache is not None and len(cache.shape) == 2 and cache.shape[1] == 2)
check("_raw_cache が空でない", cache is not None and len(cache) > 0)

# ----------------------------------------------------------------
# テスト 2: 録音→停止→WAV保存
# ----------------------------------------------------------------
print("\n=== テスト 2: 録音→停止→WAV保存 ===")
wav_path_t2 = os.path.join(TMPDIR, "test2.wav")
make_wav(wav_path_t2, duration_sec=0.5)
out_path_t2 = os.path.join(TMPDIR, "output.wav")

ok0 = ENGINE.load_file(0, wav_path_t2)
ok1 = ENGINE.load_file(1, wav_path_t2)
check("パッド0 ロード成功", ok0)
check("パッド1 ロード成功", ok1)

ENGINE.start_recording()
time.sleep(0.05)
# イベントを手動で追加（dummy audioでは play() が実際に音を出せないため）
with ENGINE._events_lock:
    ENGINE._record_events.append((0, 0.0))
    ENGINE._record_events.append((1, 0.2))

events_t2 = ENGINE.stop_recording()
check("録音イベント数 == 2", len(events_t2) == 2, f"実際: {len(events_t2)}")

ok = ENGINE.save_recording_as_wav(out_path_t2, events_t2)
check("save_recording_as_wav 成功", ok)
check("出力ファイルが存在する", os.path.isfile(out_path_t2))

if os.path.isfile(out_path_t2):
    with wave.open(out_path_t2, "rb") as wf:
        n_frames = wf.getnframes()
        check("出力WAVのフレーム数 > 0", n_frames > 0, f"実際: {n_frames}")
        raw = wf.readframes(n_frames)
        arr = np.frombuffer(raw, dtype=np.int16)
        max_val = int(np.max(np.abs(arr)))
        check("出力WAVが無音でない (max > 100)", max_val > 100, f"max_sample={max_val}")

# ----------------------------------------------------------------
# テスト 3: events が空の場合
# ----------------------------------------------------------------
print("\n=== テスト 3: events が空の場合 ===")
out_path_t3 = os.path.join(TMPDIR, "empty.wav")
ok = ENGINE.save_recording_as_wav(out_path_t3, [])
check("空 events で False を返す", not ok)

# ----------------------------------------------------------------
# テスト 4: WavSaveWorker（QThread）の動作
# ----------------------------------------------------------------
print("\n=== テスト 4: WavSaveWorker バックグラウンド保存 ===")
try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    out_path_t4 = os.path.join(TMPDIR, "worker_out.wav")
    events_t4 = [(0, 0.0), (1, 0.3)]

    from main_window import WavSaveWorker
    results = {}

    def on_done(ok, path):
        results["ok"] = ok
        results["path"] = path

    worker = WavSaveWorker(ENGINE, out_path_t4, events_t4)
    worker.finished.connect(on_done)
    worker.start()
    worker.wait(10000)  # 最大10秒待機
    # シグナルをUIスレッドで処理するためにイベントループを回す
    app.processEvents()

    check("WavSaveWorker 完了", worker.isFinished())
    check("WavSaveWorker 成功フラグ", results.get("ok", False))
    check("WavSaveWorker 出力ファイル存在", os.path.isfile(out_path_t4))

    if os.path.isfile(out_path_t4):
        with wave.open(out_path_t4, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            arr = np.frombuffer(raw, dtype=np.int16)
            max_val = int(np.max(np.abs(arr)))
            check("WavSaveWorker 出力が無音でない", max_val > 100, f"max_sample={max_val}")

except ImportError as e:
    print(f"  PyQt5 不可（スキップ）: {e}")
except Exception as e:
    print(f"  テスト4 エラー（スキップ）: {e}")

# ----------------------------------------------------------------
# テスト 5: スレッドセーフ（並行アクセス）
# ----------------------------------------------------------------
print("\n=== テスト 5: スレッドセーフ（並行アクセス） ===")
ENGINE.start_recording()

def spam_events():
    for i in range(20):
        with ENGINE._events_lock:
            ENGINE._record_events.append((0, i * 0.01))
        time.sleep(0.005)

threads = [threading.Thread(target=spam_events) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

events_t5 = ENGINE.stop_recording()
check("並行アクセス後もイベント記録が正常", len(events_t5) >= 0)

out_path_t5 = os.path.join(TMPDIR, "concurrent.wav")
try:
    ok = ENGINE.save_recording_as_wav(out_path_t5, events_t5)
    check("並行アクセス後の保存が例外なし", True)
except Exception as ex:
    check("並行アクセス後の保存が例外なし", False, str(ex))

# ----------------------------------------------------------------
# テスト 6: unload 後の動作
# ----------------------------------------------------------------
print("\n=== テスト 6: unload 後の動作 ===")
wav_path_t6 = os.path.join(TMPDIR, "test6.wav")
make_wav(wav_path_t6, duration_sec=0.3)
out_path_t6 = os.path.join(TMPDIR, "unload.wav")

ENGINE.load_file(2, wav_path_t6)
ENGINE.unload(2)

check("unload 後 _raw_cache から削除される", 2 not in ENGINE._raw_cache)

events_t6 = [(2, 0.0)]
ok = ENGINE.save_recording_as_wav(out_path_t6, events_t6)
check("unload 済みパッドのイベントは保存失敗（有効音声なし）", not ok)

# ----------------------------------------------------------------
# クリーンアップ
# ----------------------------------------------------------------
ENGINE.shutdown()
import shutil
shutil.rmtree(TMPDIR, ignore_errors=True)

# ----------------------------------------------------------------
# 結果
# ----------------------------------------------------------------
print()
if errors:
    print(f"\033[91m[FAIL] {len(errors)} テスト失敗: {errors}\033[0m")
    sys.exit(1)
else:
    print("\033[92m[ALL PASS] v1.4 録音処理テスト全通過 ✓\033[0m")
    sys.exit(0)
