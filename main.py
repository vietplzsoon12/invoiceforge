"""Run with: python main.py"""
import sys
from PySide6.QtWidgets import QApplication
from db import Store
from gui import MainWindow, STYLE


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    store = Store()
    window = MainWindow(store)
    window.show()
    result = app.exec()
    store.close()
    return result


if __name__ == "__main__":
    sys.exit(main())
