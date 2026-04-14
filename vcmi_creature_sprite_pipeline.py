import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import PipelineRunner
from ui.widgets import _make_app_icon


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(_make_app_icon())
    w = PipelineRunner()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
