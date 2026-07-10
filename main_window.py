"""
main_window.py
MPC Sampler メインウィンドウ（PyQt5）

v1.2 変更点:
  - トグル再生: 再生中のパッドを押すと停止、停止中なら再生
  - 録音開始ボタン / 録音停止ボタン
  - 録音中は赤いインジケーターと経過時間タイマーを表示
  - 録音停止後に WAV 保存ダイアログを表示
  - バグ修正: stop_recording() 後に save_recording_as_wav() が失敗する問題を修正
"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QGridLayout, QVBoxLayout,
    QHBoxLayout, QLabel, QSlider, QPushButton,
    QFileDialog, QMessageBox, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette, QKeySequence

from audio_engine import AudioEngine
from pad_widget import PadWidget
from settings_manager import SettingsManager, DEFAULT_KEYS

NUM_PADS = 16
GRID_COLS = 4


class WavSaveWorker(QThread):
    """
    WAV ミックスダウン保存をバックグラウンドスレッドで実行するワーカー。
    UIスレッドをブロックしないようにするためのクラス。
    """
    finished = pyqtSignal(bool, str)  # (success, save_path)

    def __init__(self, engine, save_path: str, events: list):
        super().__init__()
        self._engine = engine
        self._save_path = save_path
        self._events = events

    def run(self):
        ok = self._engine.save_recording_as_wav(self._save_path, self._events)
        self.finished.emit(ok, self._save_path)


class MainWindow(QMainWindow):
    """
    MPC Sampler のメインウィンドウ。
    16パッドのグリッドUI、マスター音量、設定保存/読み込み、録音機能を提供する。
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MPC Sampler v1.2")
        self.setMinimumSize(680, 640)

        self._engine = AudioEngine(NUM_PADS)
        self._settings_mgr = SettingsManager()
        self._settings = self._settings_mgr.load(NUM_PADS)

        # キー -> pad_index のマッピング
        self._key_map: dict[str, int] = {}

        # 録音タイマー（UI更新用）
        self._rec_timer = QTimer()
        self._rec_timer.setInterval(100)  # 100ms ごとに更新
        self._rec_timer.timeout.connect(self._update_rec_display)

        self._build_ui()
        self._apply_dark_theme()
        self._load_settings_to_ui()

    # ==================================================================
    # UI 構築
    # ==================================================================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ヘッダー
        root.addWidget(self._build_header())

        # セパレーター
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #3a3f4b;")
        root.addWidget(sep)

        # パッドグリッド
        self._pad_widgets: list[PadWidget] = []
        pad_area = QWidget()
        grid = QGridLayout(pad_area)
        grid.setSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)

        for i in range(NUM_PADS):
            key = DEFAULT_KEYS[i] if i < len(DEFAULT_KEYS) else ""
            pw = PadWidget(i, key)
            pw.pad_clicked.connect(self._on_pad_clicked)
            pw.file_requested.connect(self._on_file_requested)
            pw.volume_changed.connect(self._on_pad_volume_changed)
            row, col = divmod(i, GRID_COLS)
            grid.addWidget(pw, row, col)
            self._pad_widgets.append(pw)

        root.addWidget(pad_area, stretch=1)

        # 録音コントロールバー
        root.addWidget(self._build_rec_bar())

        # セパレーター
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #3a3f4b;")
        root.addWidget(sep2)

        # フッター（マスター音量 + 保存/読込）
        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("● MPC SAMPLER")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: #ffa01e; letter-spacing: 2px;")
        layout.addWidget(title)

        layout.addStretch()

        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #6a7080; font-size: 11px;")
        layout.addWidget(self._status_label)

        return w

    def _build_rec_bar(self) -> QWidget:
        """録音コントロールバーを構築する"""
        w = QWidget()
        w.setFixedHeight(44)
        w.setStyleSheet("background: #181c22; border-radius: 6px;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        # REC ラベル
        rec_label = QLabel("REC")
        rec_label.setFont(QFont("Arial", 10, QFont.Bold))
        rec_label.setStyleSheet("color: #8a90a0; letter-spacing: 2px;")
        layout.addWidget(rec_label)

        # 録音インジケーター（●）
        self._rec_indicator = QLabel("●")
        self._rec_indicator.setFont(QFont("Arial", 14, QFont.Bold))
        self._rec_indicator.setStyleSheet("color: #3a3f4b;")  # 非録音時はグレー
        self._rec_indicator.setFixedWidth(20)
        layout.addWidget(self._rec_indicator)

        # 経過時間表示
        self._rec_time_label = QLabel("00:00.0")
        self._rec_time_label.setFont(QFont("Courier New", 12, QFont.Bold))
        self._rec_time_label.setStyleSheet("color: #6a7080; min-width: 70px;")
        layout.addWidget(self._rec_time_label)

        layout.addStretch()

        # 録音開始ボタン
        self._rec_start_btn = QPushButton("⏺  録音開始")
        self._rec_start_btn.setFixedHeight(30)
        self._rec_start_btn.setFixedWidth(110)
        self._rec_start_btn.setStyleSheet(self._btn_style_rec_start())
        self._rec_start_btn.clicked.connect(self._on_rec_start)
        layout.addWidget(self._rec_start_btn)

        # 録音停止ボタン
        self._rec_stop_btn = QPushButton("⏹  録音停止")
        self._rec_stop_btn.setFixedHeight(30)
        self._rec_stop_btn.setFixedWidth(110)
        self._rec_stop_btn.setStyleSheet(self._btn_style_rec_stop(enabled=False))
        self._rec_stop_btn.setEnabled(False)
        self._rec_stop_btn.clicked.connect(self._on_rec_stop)
        layout.addWidget(self._rec_stop_btn)

        return w

    def _build_footer(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        # マスター音量
        vol_label = QLabel("MASTER VOL")
        vol_label.setStyleSheet("color: #8a90a0; font-size: 10px; font-weight: bold;")
        layout.addWidget(vol_label)

        self._master_slider = QSlider(Qt.Horizontal)
        self._master_slider.setRange(0, 100)
        self._master_slider.setValue(100)
        self._master_slider.setFixedWidth(140)
        self._master_slider.setToolTip("マスター音量")
        self._master_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px; background: #2a2f3b; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px; height: 14px; margin: -4px 0;
                background: #ffa01e; border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #ffa01e; border-radius: 3px;
            }
        """)
        self._master_slider.valueChanged.connect(self._on_master_volume_changed)
        layout.addWidget(self._master_slider)

        self._master_vol_label = QLabel("100%")
        self._master_vol_label.setStyleSheet("color: #ffa01e; font-size: 11px; min-width: 36px;")
        layout.addWidget(self._master_vol_label)

        layout.addStretch()

        # 保存ボタン
        save_btn = QPushButton("💾 保存")
        save_btn.setFixedHeight(28)
        save_btn.setStyleSheet(self._btn_style("#2a5a3a", "#3a7a50"))
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)

        # 読み込みボタン
        load_btn = QPushButton("📂 読込")
        load_btn.setFixedHeight(28)
        load_btn.setStyleSheet(self._btn_style("#2a3a5a", "#3a507a"))
        load_btn.clicked.connect(self._load_settings_dialog)
        layout.addWidget(load_btn)

        # 設定ファイルパス表示
        path_label = QLabel(f"設定: {self._settings_mgr.get_settings_path()}")
        path_label.setStyleSheet("color: #505560; font-size: 9px;")
        path_label.setWordWrap(False)
        layout.addWidget(path_label)

        return w

    def _btn_style(self, bg: str, hover: str) -> str:
        return f"""
            QPushButton {{
                background: {bg}; color: #c0c8d0;
                border: 1px solid #445; border-radius: 4px;
                padding: 0 10px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {hover}; }}
            QPushButton:pressed {{ background: #1a2030; }}
        """

    def _btn_style_rec_start(self) -> str:
        return """
            QPushButton {
                background: #5a1a1a; color: #ff6060;
                border: 1px solid #8a3030; border-radius: 4px;
                font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: #7a2020; }
            QPushButton:pressed { background: #3a0a0a; }
            QPushButton:disabled { background: #2a2a2a; color: #505050; border-color: #333; }
        """

    def _btn_style_rec_stop(self, enabled: bool) -> str:
        if enabled:
            return """
                QPushButton {
                    background: #8a2020; color: #ffffff;
                    border: 1px solid #cc4040; border-radius: 4px;
                    font-size: 11px; font-weight: bold;
                }
                QPushButton:hover { background: #aa3030; }
                QPushButton:pressed { background: #5a1010; }
            """
        else:
            return """
                QPushButton {
                    background: #2a2a2a; color: #505050;
                    border: 1px solid #333; border-radius: 4px;
                    font-size: 11px;
                }
            """

    # ==================================================================
    # ダークテーマ
    # ==================================================================
    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e2128;
                color: #c8cdd8;
                font-family: Arial, sans-serif;
            }
            QLabel { color: #c8cdd8; }
            QToolTip {
                background: #2a2f3b; color: #e0e4f0;
                border: 1px solid #555; padding: 4px;
            }
        """)

    # ==================================================================
    # 設定の UI への適用
    # ==================================================================
    def _load_settings_to_ui(self):
        """設定データを UI と AudioEngine に反映する"""
        self._key_map.clear()
        master_vol = self._settings.get("master_volume", 1.0)
        self._master_slider.setValue(int(master_vol * 100))
        self._engine.set_master_volume(master_vol)

        for pad_data in self._settings.get("pads", []):
            idx = pad_data.get("index", 0)
            if idx >= NUM_PADS:
                continue
            pw = self._pad_widgets[idx]
            key = pad_data.get("key", "")
            vol = pad_data.get("volume", 0.8)
            file_path = pad_data.get("file_path", "")

            pw.set_key(key)
            pw.set_volume(vol)
            self._engine.set_pad_volume(idx, vol)

            if key:
                self._key_map[key.lower()] = idx

            if file_path and os.path.isfile(file_path):
                ok = self._engine.load_file(idx, file_path)
                if ok:
                    pw.set_file_name(os.path.basename(file_path))
                else:
                    pw.set_file_name("")
            else:
                pw.set_file_name("")

        self._set_status("設定を読み込みました")

    def _collect_settings(self) -> dict:
        """現在の UI 状態から設定データを生成する"""
        pads = []
        for i, pw in enumerate(self._pad_widgets):
            pads.append({
                "index": i,
                "file_path": self._engine.get_file_path(i),
                "key": pw.pad_btn.key,
                "volume": pw.vol_slider.value() / 100.0,
                "label": f"PAD {i + 1:02d}",
            })
        return {
            "version": 1,
            "master_volume": self._master_slider.value() / 100.0,
            "pads": pads,
        }

    # ==================================================================
    # イベントハンドラ
    # ==================================================================
    def _on_pad_clicked(self, pad_index: int):
        # play() 呼び出し前に再生中かどうかを確認してステータスを分ける
        was_playing = self._engine.is_playing(pad_index)
        self._engine.play(pad_index)
        if was_playing:
            self._set_status(f"PAD {pad_index + 1:02d} 停止")
        else:
            self._set_status(f"PAD {pad_index + 1:02d} 再生")

    def _on_file_requested(self, pad_index: int):
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"PAD {pad_index + 1:02d} に音声ファイルを割り当て",
            os.path.expanduser("~"),
            "音声ファイル (*.wav *.mp3);;WAV (*.wav);;MP3 (*.mp3)"
        )
        if not path:
            return
        ok = self._engine.load_file(pad_index, path)
        if ok:
            self._pad_widgets[pad_index].set_file_name(os.path.basename(path))
            self._set_status(f"PAD {pad_index + 1:02d}: {os.path.basename(path)} を読み込みました")
        else:
            QMessageBox.warning(self, "読み込みエラー",
                                f"ファイルを読み込めませんでした:\n{path}")

    def _on_pad_volume_changed(self, pad_index: int, volume: float):
        self._engine.set_pad_volume(pad_index, volume)

    def _on_master_volume_changed(self, value: int):
        vol = value / 100.0
        self._engine.set_master_volume(vol)
        self._master_vol_label.setText(f"{value}%")

    def _save_settings(self):
        self._settings = self._collect_settings()
        ok = self._settings_mgr.save(self._settings)
        if ok:
            self._set_status(f"設定を保存しました → {self._settings_mgr.get_settings_path()}")
        else:
            QMessageBox.warning(self, "保存エラー", "設定の保存に失敗しました。")

    def _load_settings_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "設定ファイルを開く",
            os.path.dirname(self._settings_mgr.get_settings_path()),
            "JSON (*.json)"
        )
        if not path:
            return
        import json
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._settings = json.load(f)
            self._load_settings_to_ui()
        except Exception as e:
            QMessageBox.warning(self, "読み込みエラー", f"設定ファイルを読み込めませんでした:\n{e}")

    # ==================================================================
    # 録音コントロール（v1.1+）
    # ==================================================================
    def _on_rec_start(self):
        """録音開始ボタン押下"""
        self._engine.start_recording()

        # UI 更新
        self._rec_start_btn.setEnabled(False)
        self._rec_start_btn.setStyleSheet(self._btn_style_rec_start().replace(
            "background: #5a1a1a", "background: #2a2a2a"
        ))
        self._rec_stop_btn.setEnabled(True)
        self._rec_stop_btn.setStyleSheet(self._btn_style_rec_stop(enabled=True))
        self._rec_indicator.setStyleSheet("color: #ff3030;")  # 赤く点灯

        # タイマー開始（点滅 + 時間更新）
        self._rec_blink_state = True
        self._rec_timer.start()

        self._set_status("● 録音中...")

    def _on_rec_stop(self):
        """録音停止ボタン押下"""
        events = self._engine.stop_recording()

        # タイマー停止
        self._rec_timer.stop()

        # UI リセット
        self._rec_start_btn.setEnabled(True)
        self._rec_start_btn.setStyleSheet(self._btn_style_rec_start())
        self._rec_stop_btn.setEnabled(False)
        self._rec_stop_btn.setStyleSheet(self._btn_style_rec_stop(enabled=False))
        self._rec_indicator.setStyleSheet("color: #3a3f4b;")
        self._rec_time_label.setText("00:00.0")
        self._rec_time_label.setStyleSheet("color: #6a7080; min-width: 70px;")

        if not events:
            self._set_status("録音停止（イベントなし）")
            QMessageBox.information(self, "録音停止",
                                    "録音中にパッドが押されませんでした。\nWAVファイルは保存されませんでした。")
            return

        self._set_status(f"録音停止（{len(events)} イベント）")

        # 保存先ダイアログ
        default_dir = os.path.expanduser("~/Documents")
        os.makedirs(default_dir, exist_ok=True)
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "録音を WAV ファイルとして保存",
            os.path.join(default_dir, "recording.wav"),
            "WAV ファイル (*.wav)"
        )
        if not save_path:
            self._set_status("録音保存をキャンセルしました")
            return

        if not save_path.lower().endswith(".wav"):
            save_path += ".wav"

        # WAV ミックスダウン保存 — QThread でバックグラウンド実行（UIブロック防止）
        self._set_status("WAV を保存中...しばらくお待ちください")
        self._rec_start_btn.setEnabled(False)  # 保存完了まで操作禁止
        self._wav_worker = WavSaveWorker(self._engine, save_path, events)
        self._wav_worker.finished.connect(self._on_wav_save_done)
        self._wav_worker.start()

    def _on_wav_save_done(self, ok: bool, save_path: str):
        """バックグラウンドWAV保存完了時のコールバック"""
        self._rec_start_btn.setEnabled(True)  # 操作制限を解除
        if ok:
            self._set_status(f"録音保存完了 → {os.path.basename(save_path)}")
            QMessageBox.information(self, "録音保存完了",
                                    f"WAVファイルを保存しました:\n{save_path}")
        else:
            self._set_status("録音保存に失敗しました")
            QMessageBox.warning(self, "保存エラー",
                                "WAVファイルの保存に失敗しました。\n音声ファイルが割り当てられているか確認してください。")

    def _update_rec_display(self):
        """録音中の UI 更新（タイマーから呼ばれる）"""
        if not self._engine.is_recording():
            return

        # 経過時間表示
        elapsed = self._engine.get_record_duration()
        minutes = int(elapsed // 60)
        seconds = elapsed % 60
        self._rec_time_label.setText(f"{minutes:02d}:{seconds:04.1f}")
        self._rec_time_label.setStyleSheet("color: #ff6060; min-width: 70px;")

        # インジケーター点滅（500ms ごと）
        self._rec_blink_state = not self._rec_blink_state
        if self._rec_blink_state:
            self._rec_indicator.setStyleSheet("color: #ff3030;")
        else:
            self._rec_indicator.setStyleSheet("color: #5a1a1a;")

    # ==================================================================
    # キーボード入力
    # ==================================================================
    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        key_text = event.text().lower()
        if key_text in self._key_map:
            pad_index = self._key_map[key_text]
            self._pad_widgets[pad_index].trigger()
        else:
            super().keyPressEvent(event)

    # ==================================================================
    # ユーティリティ
    # ==================================================================
    def _set_status(self, msg: str):
        self._status_label.setText(msg)
        QTimer.singleShot(4000, lambda: self._status_label.setText("Ready"))

    def closeEvent(self, event):
        # 録音中なら停止
        if self._engine.is_recording():
            self._engine.stop_recording()
        # 終了時に自動保存
        self._settings = self._collect_settings()
        self._settings_mgr.save(self._settings)
        self._engine.shutdown()
        event.accept()
