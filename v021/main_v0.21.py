import sys

from PyQt6.QtWidgets import QApplication

from app_core import setup_logging
from ui_windows import MainWindow


def main() -> None:
    setup_logging()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()