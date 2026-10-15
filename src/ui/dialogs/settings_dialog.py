"""
Диалоговое окно настроек и справочника горячих клавиш.
"""
from typing import List, Tuple
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QWidget
)
from PySide6.QtCore import Qt

HOTKEYS_CONFIG: List[Tuple[str, str, str]] = [
    ("Ctrl + Z", "Отменить последнее действие (Undo)", "История"),
    ("Ctrl + Y / Shift+Ctrl+Z", "Повторить отменённое действие (Redo)", "История"),
    ("Delete / Backspace", "Исключить выбранные треки или альбом", "Управление"),
    ("Insert", "Восстановить исключённые треки или альбом", "Управление"),
    ("Ctrl + A", "Выделить все треки в списке", "Выделение"),
    ("Ctrl + O", "Выбрать рабочую папку фонотеки", "Файлы"),
    ("Ctrl + E", "Начать экспорт фонотеки", "Экспорт"),
    ("Ctrl + P", "Вкл / выкл предпросмотр форматирования", "Вид"),
    ("Ctrl + H", "Показать / скрыть исключённые треки", "Вид"),
    ("Ctrl + Tab", "Инверсия панелей (поменять стороны местами)", "Интерфейс"),
    ("F5", "Принудительно пересчитать план и обновить список", "Обновление"),
]


class SettingsDialog(QDialog):
    """Диалог настроек и горячих клавиш."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки программы")
        self.resize(650, 480)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        tabs = QTabWidget()
        tab_hotkeys = QWidget()
        l_hk = QVBoxLayout(tab_hotkeys)
        l_hk.addWidget(QLabel("Список доступных клавиатурных комбинаций:"))

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Клавиши", "Действие", "Категория"])
        table.setRowCount(len(HOTKEYS_CONFIG))
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.verticalHeader().setVisible(False)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        for row, (keys, action, cat) in enumerate(HOTKEYS_CONFIG):
            it_keys = QTableWidgetItem(keys)
            it_keys.setTextAlignment(Qt.AlignCenter)
            it_action = QTableWidgetItem(action)
            it_cat = QTableWidgetItem(cat)
            it_cat.setTextAlignment(Qt.AlignCenter)

            table.setItem(row, 0, it_keys)
            table.setItem(row, 1, it_action)
            table.setItem(row, 2, it_cat)

        l_hk.addWidget(table)
        tabs.addTab(tab_hotkeys, "⌨ Горячие клавиши")
        layout.addWidget(tabs)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("Закрыть")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)