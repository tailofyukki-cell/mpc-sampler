"""
main_window.py
MPC Sampler メインウィンドウ（PyQt5）
"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QGridLayout, QVBoxLayout,
    QHBoxLayout, QLabel, QSlider, QPushButton,
    QFileDialog, QMessageBox, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QKeySequence

from audio_engine import AudioEngine
from pad_widget import PadWidget
from settings_manager import SettingsManager, DEFAULT_KEYS

NUM_PADS = 16
GRID_COLS = 4


class MainWindow(QMainWindow):
    """
    MPC Sampler のメインウィンドウ。
    16パッドのグリッドUI、マスター音量、設定保存/読み込みを提供する。
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MPC Sampler")
        self.setMinimumSize(680, 580)

        self._engine = AudioEngine(NUM_PADS)
        self._settings_mgr = SettingsManager()
        self._settings = self._settings_mgr.load(NUM_PADS)

        # キー -> pad_index のマッピング
        self._key_map: dict[str, int] = {}

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

        # フッター（マスター音量 + 保存/読込）
        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        # ロゴ/タイトル
        title = QLabel("● MPC SAMPLER")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: #ffa01e; letter-spacing: 2px;")
        layout.addWidget(title)

        layout.addStretch()

        # ステータスラベル
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #6a7080; font-size: 11px;")
        layout.addWidget(self._status_label)

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
        self._engine.play(pad_index)
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
        QTimer.singleShot(3000, lambda: self._status_label.setText("Ready"))

    def closeEvent(self, event):
        # 終了時に自動保存
        self._settings = self._collect_settings()
        self._settings_mgr.save(self._settings)
        self._engine.shutdown()
        event.accept()
