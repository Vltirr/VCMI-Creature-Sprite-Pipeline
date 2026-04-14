from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QVBoxLayout


class LogDialog(QDialog):
    """Pop-out log viewer with Find."""

    def __init__(self, parent, html_provider):
        super().__init__(parent)
        self.setWindowTitle("Log (Pop-out)")
        self.resize(1100, 700)
        self.html_provider = html_provider

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.find_box = QLineEdit()
        self.find_box.setPlaceholderText("Find...")
        self.btn_find_next = QPushButton("Next")
        self.btn_find_prev = QPushButton("Prev")
        self.btn_refresh = QPushButton("Refresh")
        top.addWidget(self.find_box, 1)
        top.addWidget(self.btn_find_prev)
        top.addWidget(self.btn_find_next)
        top.addWidget(self.btn_refresh)
        root.addLayout(top)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        root.addWidget(self.text, 1)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_find_next.clicked.connect(lambda: self.find(direction="next"))
        self.btn_find_prev.clicked.connect(lambda: self.find(direction="prev"))
        self.find_box.returnPressed.connect(lambda: self.find(direction="next"))

        self.refresh()

    def refresh(self):
        self.text.setHtml(self.html_provider())

    def find(self, direction="next"):
        needle = self.find_box.text()
        if not needle:
            return
        flags = QTextDocument.FindFlags()
        if direction == "prev":
            flags |= QTextDocument.FindBackward
        found = self.text.find(needle, flags)
        if not found:
            cursor = self.text.textCursor()
            cursor.movePosition(QTextCursor.Start if direction == "next" else QTextCursor.End)
            self.text.setTextCursor(cursor)
            self.text.find(needle, flags)
