"""
main.py
MPC Sampler エントリーポイント
"""

import sys
import os

# Windows での高DPI対応
if sys.platform == "win32":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from main_window import MainWindow


def main():
    # High DPI スケーリング有効化
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("MPC Sampler")
    app.setOrganizationName("100DayChallenge")

    # アイコン設定（存在する場合）
    icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
