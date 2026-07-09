"""
pad_widget.py
MPC風パッドウィジェット（PyQt5）
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QPushButton, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QPainter, QPen, QFont, QFontMetrics


# カラーパレット
COLOR_PAD_NORMAL   = QColor(50, 55, 65)
COLOR_PAD_ACTIVE   = QColor(255, 160, 30)
COLOR_PAD_HOVER    = QColor(70, 75, 90)
COLOR_PAD_LOADED   = QColor(40, 80, 120)
COLOR_PAD_BORDER   = QColor(30, 30, 35)
COLOR_TEXT_MAIN    = QColor(220, 220, 230)
COLOR_TEXT_SUB     = QColor(140, 145, 160)
COLOR_TEXT_FILE    = QColor(100, 200, 140)
COLOR_ACCENT       = QColor(255, 160, 30)


class PadButton(QWidget):
    """
    MPC風パッドボタン。
    クリック・ホバー・アクティブ状態の視覚フィードバックを持つ。
    """
    clicked = pyqtSignal(int)  # pad_index を emit

    ACTIVE_DURATION_MS = 120  # 点灯時間 (ms)

    def __init__(self, pad_index: int, key: str, parent=None):
        super().__init__(parent)
        self.pad_index = pad_index
        self.key = key
        self.file_name = ""
        self.is_active = False
        self.is_hovered = False
        self.is_loaded = False

        self._active_timer = QTimer(self)
        self._active_timer.setSingleShot(True)
        self._active_timer.timeout.connect(self._deactivate)

        self.setMinimumSize(100, 90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    # ------------------------------------------------------------------
    # 状態変更
    # ------------------------------------------------------------------
    def activate(self):
        """パッドを点灯させる（再生トリガー時）"""
        self.is_active = True
        self.update()
        self._active_timer.start(self.ACTIVE_DURATION_MS)

    def _deactivate(self):
        self.is_active = False
        self.update()

    def set_file_name(self, name: str):
        self.file_name = name
        self.is_loaded = bool(name)
        self.update()

    def set_key(self, key: str):
        self.key = key
        self.update()

    # ------------------------------------------------------------------
    # 描画
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        radius = 8

        # 背景色の決定
        if self.is_active:
            bg = COLOR_PAD_ACTIVE
        elif self.is_hovered:
            bg = COLOR_PAD_HOVER
        elif self.is_loaded:
            bg = COLOR_PAD_LOADED
        else:
            bg = COLOR_PAD_NORMAL

        # 押し込み表現（アクティブ時に少し縮小）
        if self.is_active:
            margin = 3
        else:
            margin = 0

        # 背景
        painter.setBrush(bg)
        painter.setPen(QPen(COLOR_PAD_BORDER, 2))
        painter.drawRoundedRect(margin, margin, w - margin * 2, h - margin * 2, radius, radius)

        # パッド番号（左上）
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.setPen(COLOR_TEXT_SUB if not self.is_active else QColor(50, 30, 0))
        pad_label = f"PAD {self.pad_index + 1:02d}"
        painter.drawText(8 + margin, 16 + margin, pad_label)

        # キー割り当て（右上）
        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        painter.setPen(COLOR_ACCENT if not self.is_active else QColor(80, 50, 0))
        key_text = f"[{self.key.upper()}]"
        fm = QFontMetrics(painter.font())
        key_w = fm.horizontalAdvance(key_text)
        painter.drawText(w - key_w - 8 - margin, 16 + margin, key_text)

        # ファイル名（中央下）
        painter.setFont(QFont("Arial", 7))
        if self.file_name:
            painter.setPen(COLOR_TEXT_FILE if not self.is_active else QColor(30, 80, 40))
            # 長いファイル名は省略
            display = self._truncate(self.file_name, painter, w - 16)
        else:
            painter.setPen(COLOR_TEXT_SUB)
            display = "-- empty --"
        painter.drawText(
            8 + margin, h - 10 - margin,
            w - 16 - margin * 2, 14,
            Qt.AlignLeft | Qt.AlignVCenter,
            display
        )

    def _truncate(self, text: str, painter: QPainter, max_width: int) -> str:
        fm = QFontMetrics(painter.font())
        if fm.horizontalAdvance(text) <= max_width:
            return text
        while len(text) > 3 and fm.horizontalAdvance(text + "...") > max_width:
            text = text[:-1]
        return text + "..."

    # ------------------------------------------------------------------
    # マウスイベント
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activate()
            self.clicked.emit(self.pad_index)

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(120, 100)


class PadWidget(QWidget):
    """
    パッドボタン + 音量スライダー + ファイル割り当てボタンを含む
    1パッド分のウィジェット
    """
    pad_clicked = pyqtSignal(int)
    file_requested = pyqtSignal(int)
    volume_changed = pyqtSignal(int, float)

    def __init__(self, pad_index: int, key: str, parent=None):
        super().__init__(parent)
        self.pad_index = pad_index
        self._build_ui(key)

    def _build_ui(self, key: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # パッドボタン
        self.pad_btn = PadButton(self.pad_index, key)
        self.pad_btn.clicked.connect(self.pad_clicked)
        layout.addWidget(self.pad_btn, stretch=1)

        # 下部コントロール（音量スライダー + ファイルボタン）
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(3)

        # ファイル割り当てボタン
        self.file_btn = QPushButton("📂")
        self.file_btn.setFixedSize(26, 22)
        self.file_btn.setToolTip("音声ファイルを割り当て")
        self.file_btn.setStyleSheet("""
            QPushButton {
                background: #3a3f4b;
                color: #aab0c0;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover { background: #4a5060; }
            QPushButton:pressed { background: #2a2f3b; }
        """)
        self.file_btn.clicked.connect(lambda: self.file_requested.emit(self.pad_index))
        ctrl_layout.addWidget(self.file_btn)

        # 音量スライダー
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setToolTip("パッド音量")
        self.vol_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #2a2f3b;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 10px; height: 10px;
                margin: -3px 0;
                background: #ffa01e;
                border-radius: 5px;
            }
            QSlider::sub-page:horizontal {
                background: #ffa01e;
                border-radius: 2px;
            }
        """)
        self.vol_slider.valueChanged.connect(
            lambda v: self.volume_changed.emit(self.pad_index, v / 100.0)
        )
        ctrl_layout.addWidget(self.vol_slider, stretch=1)

        layout.addLayout(ctrl_layout)

    # ------------------------------------------------------------------
    # 外部から状態を更新するメソッド
    # ------------------------------------------------------------------
    def trigger(self):
        """キーボード等から再生トリガーを受けたとき"""
        self.pad_btn.activate()
        self.pad_clicked.emit(self.pad_index)

    def set_file_name(self, name: str):
        self.pad_btn.set_file_name(name)

    def set_key(self, key: str):
        self.pad_btn.set_key(key)

    def set_volume(self, volume: float):
        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(int(volume * 100))
        self.vol_slider.blockSignals(False)
