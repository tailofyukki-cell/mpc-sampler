"""
audio_engine.py
pygame.mixer のみを使った低遅延・同時発音対応の音声再生エンジン。

【依存ライブラリ】
  - pygame のみ（標準インストールに含まれる SDL_mixer を使用）
  - ffmpeg / miniaudio / pydub などの外部ライブラリは一切不要

【対応フォーマット】
  - WAV  : pygame.mixer.Sound で直接読み込み
  - MP3  : pygame.mixer.Sound で直接読み込み
            （Windows版 pygame に内蔵された SDL_mixer の MP3 デコーダを使用）

【v1.2 変更点】
  - トグル再生: 再生中のパッドを押すと停止、停止中なら再生
  - 録音機能: パッド操作のタイムラインを記録し WAV としてミックスダウン保存
  - バグ修正: stop_recording() 後に save_recording_as_wav() が失敗する問題を修正
"""

import os
import time
import wave
import struct
import threading
import pygame


# pygame mixer の初期化（44100Hz, 16bit signed, ステレオ, バッファ256サンプル）
pygame.mixer.pre_init(44100, -16, 2, 256)
pygame.mixer.init()
pygame.mixer.set_num_channels(32)  # 同時発音数

SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_WIDTH = 2  # 16bit


class AudioEngine:
    """
    各パッドに対応した音声を管理する音声再生エンジン。
    pygame.mixer.Sound を使い、同時発音・個別音量制御を実現する。
    外部バイナリ・C拡張ライブラリへの依存は一切ない。

    v1.2: トグル再生・録音機能を追加。
    """

    def __init__(self, num_pads: int = 16):
        self.num_pads = num_pads
        # pad_index -> pygame.mixer.Sound
        self._sounds: dict[int, pygame.mixer.Sound] = {}
        # pad_index -> 現在再生中の Channel（トグル再生用）
        self._channels: dict[int, pygame.mixer.Channel] = {}
        # pad_index -> volume (0.0 ~ 1.0)
        self._volumes: dict[int, float] = {i: 0.8 for i in range(num_pads)}
        # pad_index -> file path
        self._file_paths: dict[int, str] = {}
        # マスター音量
        self._master_volume: float = 1.0
        self._lock = threading.Lock()

        # 録音状態
        self._recording: bool = False
        self._record_start_time: float = 0.0
        # 録音イベント: list of (pad_index, timestamp_sec)
        self._record_events: list[tuple[int, float]] = []

    # ------------------------------------------------------------------
    # ファイル読み込み
    # ------------------------------------------------------------------
    def load_file(self, pad_index: int, file_path: str) -> bool:
        """
        指定パッドに音声ファイルを読み込む。
        pygame.mixer.Sound がWAV/MP3を直接サポートしているため、
        追加のデコードライブラリは不要。
        """
        if not os.path.isfile(file_path):
            print(f"[AudioEngine] File not found: {file_path}")
            return False

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in (".wav", ".mp3"):
            print(f"[AudioEngine] Unsupported format: {ext}")
            return False

        try:
            sound = pygame.mixer.Sound(file_path)

            with self._lock:
                self._sounds[pad_index] = sound
                self._file_paths[pad_index] = file_path
                vol = self._volumes.get(pad_index, 0.8)
                sound.set_volume(vol * self._master_volume)

            return True

        except Exception as e:
            print(f"[AudioEngine] load_file error ({os.path.basename(file_path)}): {e}")
            return False

    # ------------------------------------------------------------------
    # 再生（v1.2: トグル再生 — 再生中なら停止、停止中なら再生）
    # ------------------------------------------------------------------
    def play(self, pad_index: int):
        """
        指定パッドの音声をトグル再生する。
        - 停止中 → 再生開始
        - 再生中 → 停止
        """
        with self._lock:
            sound = self._sounds.get(pad_index)
            if sound is None:
                return

            ch = self._channels.get(pad_index)
            if ch is not None and ch.get_busy():
                # 再生中 → 停止
                ch.stop()
                self._channels[pad_index] = None
                return  # 停止時は録音イベントを記録しない

            # 停止中 → 新規チャンネルで再生
            new_ch = sound.play()
            if new_ch is not None:
                self._channels[pad_index] = new_ch

        # 録音中なら再生開始イベントを記録
        if self._recording:
            ts = time.monotonic() - self._record_start_time
            self._record_events.append((pad_index, ts))

    def is_playing(self, pad_index: int) -> bool:
        """指定パッドが現在再生中かどうかを返す"""
        with self._lock:
            ch = self._channels.get(pad_index)
            return ch is not None and ch.get_busy()

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
    # 録音機能（v1.1+）
    # ------------------------------------------------------------------
    def start_recording(self):
        """録音を開始する。以前の録音データはクリアされる。"""
        self._record_events.clear()
        self._record_start_time = time.monotonic()
        self._recording = True
        print("[AudioEngine] 録音開始")

    def stop_recording(self) -> list[tuple[int, float]]:
        """
        録音を停止し、記録されたイベントリストを返す。
        戻り値: [(pad_index, timestamp_sec), ...]
        停止後は内部イベントリストをクリアする。
        """
        self._recording = False
        events = list(self._record_events)
        self._record_events.clear()  # 次の録音に備えてクリア
        print(f"[AudioEngine] 録音停止 ({len(events)} イベント)")
        return events

    def is_recording(self) -> bool:
        return self._recording

    def get_record_duration(self) -> float:
        """録音開始からの経過時間（秒）を返す"""
        if self._recording:
            return time.monotonic() - self._record_start_time
        return 0.0

    def save_recording_as_wav(self, output_path: str, events: list[tuple[int, float]] | None = None) -> bool:
        """
        録音イベントを WAV ファイルとしてミックスダウン保存する。
        各パッドの音声をタイムスタンプ位置に配置してミックスする。

        Args:
            output_path: 保存先パス
            events: 録音イベントリスト [(pad_index, timestamp_sec), ...]。
                    None の場合は内部バッファを使用（後方互換）。

        Returns:
            True: 保存成功
            False: 保存失敗（イベントなし・音声なし等）
        """
        if events is None:
            events = list(self._record_events)
        if not events:
            print("[AudioEngine] 録音イベントがありません")
            return False

        # 必要な総フレーム数を計算
        max_ts = max(ts for _, ts in events)
        max_sound_len = 0.0
        for pad_idx, _ in events:
            snd = self._sounds.get(pad_idx)
            if snd:
                max_sound_len = max(max_sound_len, snd.get_length())

        total_duration = max_ts + max_sound_len + 1.0
        total_frames = int(total_duration * SAMPLE_RATE)

        # ミックスバッファ（ステレオ、float）
        mix_left = [0.0] * total_frames
        mix_right = [0.0] * total_frames

        for pad_idx, ts in events:
            snd = self._sounds.get(pad_idx)
            if snd is None:
                continue

            vol = self._volumes.get(pad_idx, 0.8) * self._master_volume

            try:
                import pygame.sndarray
                arr = pygame.sndarray.array(snd)
            except Exception as e:
                print(f"[AudioEngine] sndarray error: {e}")
                continue

            start_frame = int(ts * SAMPLE_RATE)
            num_frames = min(len(arr), total_frames - start_frame)
            if num_frames <= 0:
                continue

            for f in range(num_frames):
                sample = arr[f]
                if arr.ndim == 2:
                    mix_left[start_frame + f] += (sample[0] / 32768.0) * vol
                    mix_right[start_frame + f] += (sample[1] / 32768.0) * vol
                else:
                    v = (sample / 32768.0) * vol
                    mix_left[start_frame + f] += v
                    mix_right[start_frame + f] += v

        def clamp(v):
            return max(-1.0, min(1.0, v))

        try:
            with wave.open(output_path, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(SAMPLE_WIDTH)
                wf.setframerate(SAMPLE_RATE)
                for f in range(total_frames):
                    l_val = int(clamp(mix_left[f]) * 32767)
                    r_val = int(clamp(mix_right[f]) * 32767)
                    wf.writeframes(struct.pack("<hh", l_val, r_val))
            print(f"[AudioEngine] WAV保存完了: {output_path}")
            return True
        except Exception as e:
            print(f"[AudioEngine] WAV保存エラー: {e}")
            return False

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
            self._channels.pop(pad_index, None)

    def shutdown(self):
        if self._recording:
            self.stop_recording()
        pygame.mixer.quit()
