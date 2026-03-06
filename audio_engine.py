"""
audio_engine.py
pygame.mixer + miniaudio を使った低遅延・同時発音対応の音声再生エンジン。
ffmpeg / avconv などの外部バイナリに一切依存しない。

対応フォーマット:
  - WAV (PCM, 8/16/24/32bit, mono/stereo)
  - MP3 (miniaudio の純粋 C 実装デコーダを使用)
"""

import os
import threading
import pygame
import miniaudio
import numpy as np


# pygame mixer の初期化（44100Hz, 16bit signed, ステレオ, バッファ256サンプル）
pygame.mixer.pre_init(44100, -16, 2, 256)
pygame.mixer.init()
pygame.mixer.set_num_channels(32)  # 同時発音数


class AudioEngine:
    """
    各パッドに対応した音声を管理する音声再生エンジン。
    miniaudio でデコードした PCM データを pygame.mixer.Sound に変換し、
    同時発音・個別音量制御を実現する。
    """

    def __init__(self, num_pads: int = 16):
        self.num_pads = num_pads
        # pad_index -> pygame.mixer.Sound
        self._sounds: dict[int, pygame.mixer.Sound] = {}
        # pad_index -> volume (0.0 ~ 1.0)
        self._volumes: dict[int, float] = {i: 0.8 for i in range(num_pads)}
        # pad_index -> file path
        self._file_paths: dict[int, str] = {}
        # マスター音量
        self._master_volume: float = 1.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # ファイル読み込み
    # ------------------------------------------------------------------
    def load_file(self, pad_index: int, file_path: str) -> bool:
        """
        指定パッドに音声ファイルを読み込む。
        miniaudio で wav/mp3 を 44100Hz ステレオ 16bit PCM に統一デコードし、
        pygame.mixer.Sound に変換する。ffmpeg 不要。
        """
        if not os.path.isfile(file_path):
            print(f"[AudioEngine] File not found: {file_path}")
            return False

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in (".wav", ".mp3"):
            print(f"[AudioEngine] Unsupported format: {ext}")
            return False

        try:
            # miniaudio でデコード（44100Hz, ステレオ, 16bit signed に統一）
            decoded = miniaudio.decode_file(
                file_path,
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=2,
                sample_rate=44100,
            )

            # bytes -> numpy int16 array -> ステレオ形状 (N, 2)
            arr = np.frombuffer(decoded.samples, dtype=np.int16).reshape(-1, 2)

            # numpy array -> pygame Sound
            sound = pygame.sndarray.make_sound(arr)

            with self._lock:
                self._sounds[pad_index] = sound
                self._file_paths[pad_index] = file_path
                vol = self._volumes.get(pad_index, 0.8)
                sound.set_volume(vol * self._master_volume)

            return True

        except Exception as e:
            print(f"[AudioEngine] load_file error ({file_path}): {e}")
            return False

    # ------------------------------------------------------------------
    # 再生
    # ------------------------------------------------------------------
    def play(self, pad_index: int):
        """指定パッドの音声を再生する（同時発音対応）"""
        with self._lock:
            sound = self._sounds.get(pad_index)
        if sound is not None:
            sound.play()

    # ------------------------------------------------------------------
    # 音量制御
    # ------------------------------------------------------------------
    def set_pad_volume(self, pad_index: int, volume: float):
        """パッド単体の音量を設定する (0.0 ~ 1.0)"""
        volume = max(0.0, min(1.0, volume))
        with self._lock:
            self._volumes[pad_index] = volume
            sound = self._sounds.get(pad_index)
            if sound:
                sound.set_volume(volume * self._master_volume)

    def get_pad_volume(self, pad_index: int) -> float:
        return self._volumes.get(pad_index, 0.8)

    def set_master_volume(self, volume: float):
        """マスター音量を設定し、全パッドに反映する"""
        volume = max(0.0, min(1.0, volume))
        self._master_volume = volume
        with self._lock:
            for idx, sound in self._sounds.items():
                pad_vol = self._volumes.get(idx, 0.8)
                sound.set_volume(pad_vol * volume)

    def get_master_volume(self) -> float:
        return self._master_volume

    # ------------------------------------------------------------------
    # 情報取得
    # ------------------------------------------------------------------
    def get_file_path(self, pad_index: int) -> str:
        return self._file_paths.get(pad_index, "")

    def has_sound(self, pad_index: int) -> bool:
        return pad_index in self._sounds

    def unload(self, pad_index: int):
        """パッドの音声をアンロードする"""
        with self._lock:
            self._sounds.pop(pad_index, None)
            self._file_paths.pop(pad_index, None)

    def shutdown(self):
        pygame.mixer.quit()
