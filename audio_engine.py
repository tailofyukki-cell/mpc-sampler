"""
audio_engine.py
pygame.mixer を使った低遅延・同時発音対応の音声再生エンジン
"""

import os
import threading
import pygame
from pydub import AudioSegment


# pygame mixer の初期化（44100Hz, 16bit, ステレオ, バッファ256）
pygame.mixer.pre_init(44100, -16, 2, 256)
pygame.mixer.init()
pygame.mixer.set_num_channels(32)  # 同時発音数


class AudioEngine:
    """
    各パッドに対応した音声チャンネルを管理する音声再生エンジン。
    pygame.mixer.Sound を使い、同時発音・個別音量制御を実現する。
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
        mp3 は pydub で wav に変換してから pygame に渡す。
        """
        if not os.path.isfile(file_path):
            return False

        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == ".mp3":
                audio = AudioSegment.from_mp3(file_path)
                wav_path = self._get_temp_wav_path(pad_index)
                audio.export(wav_path, format="wav")
                sound = pygame.mixer.Sound(wav_path)
            elif ext == ".wav":
                sound = pygame.mixer.Sound(file_path)
            else:
                return False

            with self._lock:
                self._sounds[pad_index] = sound
                self._file_paths[pad_index] = file_path
                vol = self._volumes.get(pad_index, 0.8)
                sound.set_volume(vol * self._master_volume)
            return True
        except Exception as e:
            print(f"[AudioEngine] load_file error: {e}")
            return False

    def _get_temp_wav_path(self, pad_index: int) -> str:
        """一時変換用 wav ファイルパスを返す"""
        temp_dir = os.path.join(os.path.dirname(__file__), "_temp")
        os.makedirs(temp_dir, exist_ok=True)
        return os.path.join(temp_dir, f"pad_{pad_index}.wav")

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
