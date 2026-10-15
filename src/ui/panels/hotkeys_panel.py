"""
Встраиваемая панель справочника горячих клавиш для инспектора.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLabel
)
from PySide6.QtCore import Qt
from ui.dialogs.settings_dialog import HOTKEYS_CONFIG


class HotkeysPanel(QWidget):
    """Информационная панель клавиатурных сочетаний фонотеки."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Горячие клавиши ускоряют обработку фонотеки:"))

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Клавиши", "Действие", "Категория"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.verticalHeader().setVisible(False)

        # ИСПРАВЛЕНО: Используется horizontalHeader(), а не несуществующий header()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.table.setRowCount(len(HOTKEYS_CONFIG))
        for row, (keys, action, cat) in enumerate(HOTKEYS_CONFIG):
            it_keys = QTableWidgetItem(keys)
            it_keys.setTextAlignment(Qt.AlignCenter)
            it_action = QTableWidgetItem(action)
            it_cat = QTableWidgetItem(cat)
            it_cat.setTextAlignment(Qt.AlignCenter)

            self.table.setItem(row, 0, it_keys)
            self.table.setItem(row, 1, it_action)
            self.table.setItem(row, 2, it_cat)

        layout.addWidget(self.table)