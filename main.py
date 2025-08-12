import logging
import sys
from PyQt6 import QtWidgets, QtCore
try:
    from gui.MainWindow import Ui_MainWindow  # wordt gegenereerd uit .ui
except Exception:
    Ui_MainWindow = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("log.txt", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def main():
    logging.info("main.py gestart")
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    if Ui_MainWindow is None:
        win.setWindowTitle("PyQt app — eerst UI → PY uitvoeren (UI2PY Tool)")
        win.resize(1000, 700)
    else:
        ui = Ui_MainWindow()
        ui.setupUi(win)
        win.setWindowState(QtCore.Qt.WindowState.WindowMaximized)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
