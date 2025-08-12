# region IMPORTS (STANDARD/THIRD_PARTY/LOCAL)
import os
import sys
import subprocess
from pathlib import Path
from PyQt6 import QtWidgets
# endregion

# region CONSTANTS
# Venv-pad patroon: C:\virt omgeving\<project>\venv\Scripts\pyuic6.exe
# endregion

# region HELPERS
def _get_project_name() -> str:
    """Bepaalt projectnaam (= mapnaam van dit script)."""
    return Path(__file__).resolve().parent.name

def _get_pyuic6_path() -> Path:
    """Bouwt pad naar pyuic6.exe in jouw vaste venv-structuur."""
    project_name = _get_project_name()
    return Path(fr"C:\virt omgeving\{project_name}\venv\Scripts\pyuic6.exe")

def convert_ui_to_py(ui_file: Path) -> Path:
    """Converteert .ui naar .py naast het .ui-bestand via pyuic6.exe."""
    if not ui_file.exists() or ui_file.suffix.lower() != ".ui":
        raise FileNotFoundError("Kies een geldig .ui-bestand.")

    pyuic6 = _get_pyuic6_path()
    if not pyuic6.exists():
        raise FileNotFoundError(
            f"pyuic6.exe niet gevonden:\n{pyuic6}\n"
            "Maak/controleer je venv op dit vaste pad."
        )

    out_file = ui_file.with_suffix(".py")
    # Run pyuic6.exe: pyuic6 input.ui -o output.py
    result = subprocess.run(
        [str(pyuic6), str(ui_file), "-o", str(out_file)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Conversie mislukt:\n{result.stderr.strip()}")

    return out_file
# endregion

# [CLASS:UI2PYWindow] START
class UI2PYWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("UI → PY Converter (Minimal)")
        self._build_ui()
        self._wire_events()

    def _build_ui(self):
        self.editPath = QtWidgets.QLineEdit(self)
        self.editPath.setReadOnly(True)
        self.btnBrowse = QtWidgets.QPushButton("Bladeren…", self)
        self.btnConvert = QtWidgets.QPushButton("Zet UI om naar PY", self)
        self.lblStatus = QtWidgets.QLabel("Kies een .ui-bestand.", self)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.editPath, 1)
        row.addWidget(self.btnBrowse)

        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(row)
        lay.addWidget(self.btnConvert)
        lay.addWidget(self.lblStatus)

        self.setLayout(lay)
        self.resize(520, 140)

    def _wire_events(self):
        self.btnBrowse.clicked.connect(self._on_browse_clicked)
        self.btnConvert.clicked.connect(self._on_convert_clicked)

    # [FUNC:select_ui_file] START
    def _on_browse_clicked(self):
        start_dir = str(Path(__file__).resolve().parent / "gui")
        if not Path(start_dir).exists():
            start_dir = str(Path(__file__).resolve().parent)
        file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Kies een .ui-bestand",
            start_dir,
            "UI Files (*.ui)"
        )
        if file:
            self.editPath.setText(file)
            self.lblStatus.setText("Gekozen: " + file)
    # [FUNC:select_ui_file] END

    # [FUNC:convert_ui_to_py] START
    def _on_convert_clicked(self):
        path = self.editPath.text().strip()
        if not path:
            QtWidgets.QMessageBox.warning(self, "Geen bestand", "Kies eerst een .ui-bestand.")
            return
        try:
            out_file = convert_ui_to_py(Path(path))
            self.lblStatus.setText(f"OK: gegenereerd → {out_file}")
            QtWidgets.QMessageBox.information(self, "Gereed", f"Bestand aangemaakt:\n{out_file}")
        except Exception as ex:
            self.lblStatus.setText("Fout: " + str(ex))
            QtWidgets.QMessageBox.critical(self, "Fout", str(ex))
    # [FUNC:convert_ui_to_py] END
# [CLASS:UI2PYWindow] END

# region ENTRYPOINT
def main():
    app = QtWidgets.QApplication(sys.argv)
    w = UI2PYWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
# endregion
