"""
Выдвижная нижняя консоль логов и сообщений об ошибках.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QTextEdit


class BottomDrawer(QWidget):
    """Сворачиваемая консоль для мониторинга процессов и вывода ошибок."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 4)

        header = QHBoxLayout()
        header.addWidget(QLabel("Консоль операций и логов"))
        header.addStretch()

        self.btn_close = QToolButton()
        self.btn_close.setText("✕")
        self.btn_close.clicked.connect(self.hide)
        header.addWidget(self.btn_close)
        layout.addLayout(header)

        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        layout.addWidget(self.text_log)
        self.setFixedHeight(120)
        self.hide()

    def log(self, text: str) -> None:
        self.text_log.append(text)