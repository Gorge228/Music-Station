"""
Нижняя статус-панель с индикатором прогресса и кнопкой отмены экспорта.
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QProgressBar, QLabel, QPushButton, QMenu
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QAction
from ui.theme import PROGRESS_BAR_QSS, SUCCESS_BTN_QSS

CANCEL_BTN_QSS = """
QPushButton {
    background-color: #C0392B;
    border: 1px solid #E74C3C;
    border-radius: 4px;
    color: #FFFFFF;
    font-weight: 700;
}
QPushButton:hover { background-color: #D9534F; }
QPushButton:pressed { background-color: #A93226; }
"""


class BottomBar(QWidget):
    """Индикатор прогресса и запуск/отмена физического экспорта."""
    export_library_requested = Signal()
    cancel_export_requested = Signal()
    export_txt_requested = Signal()
    export_ai_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_exporting = False
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setFormat("Готов")
        self.progress_bar.setStyleSheet(PROGRESS_BAR_QSS)

        self.lbl_percentage = QLabel("  0%")
        self.lbl_percentage.setFixedWidth(40)
        self.lbl_percentage.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # ПУНКТ 9: Кнопка Экспорт / Отмена
        self.btn_export = QPushButton("🚀 Экспорт")
        self.btn_export.setStyleSheet(SUCCESS_BTN_QSS)
        self.btn_export.setToolTip("ЛКМ: Начать экспорт файлов\nПКМ: Меню выгрузки списка / ИИ")
        self.btn_export.clicked.connect(self._on_export_clicked)
        self.btn_export.setContextMenuPolicy(Qt.CustomContextMenu)
        self.btn_export.customContextMenuRequested.connect(self._show_export_menu)

        layout.addWidget(self.progress_bar, stretch=1)
        layout.addWidget(self.lbl_percentage)
        layout.addWidget(self.btn_export)

    def _on_export_clicked(self) -> None:
        if self._is_exporting:
            self.cancel_export_requested.emit()
        else:
            self.export_library_requested.emit()

    # ПУНКТ 9: Замена кнопки «Экспорт» на «Отмена»
    def set_exporting_state(self, is_exporting: bool) -> None:
        self._is_exporting = is_exporting
        if is_exporting:
            self.btn_export.setText("⛔ Отмена")
            self.btn_export.setStyleSheet(CANCEL_BTN_QSS)
            self.btn_export.setToolTip("Прервать выполнение экспорта")
        else:
            self.btn_export.setText("🚀 Экспорт")
            self.btn_export.setStyleSheet(SUCCESS_BTN_QSS)
            self.btn_export.setToolTip("ЛКМ: Начать экспорт файлов\nПКМ: Меню выгрузки списка / ИИ")

    def _show_export_menu(self, pos: QPoint) -> None:
        if self._is_exporting:
            return
        menu = QMenu(self)
        act_txt = QAction("📄 Экспорт треклиста (Tracklist.txt)...", self)
        act_txt.triggered.connect(self.export_txt_requested.emit)

        act_ai = QAction("🤖 Скопировать промпт фонотеки для ИИ", self)
        act_ai.triggered.connect(self.export_ai_requested.emit)

        menu.addAction(act_txt)
        menu.addAction(act_ai)
        menu.exec(self.btn_export.mapToGlobal(pos))

    def set_progress(self, current: int, total: int, status_message: str) -> None:
        pct = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"{status_message} [{current}/{total}]")
        self.lbl_percentage.setText(f"{pct:3d}%")

    def reset_status(self, text: str = "Готов") -> None:
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(text)
        self.lbl_percentage.setText("  0%")

    def update_track_counts(self, selected_count: int, total_count: int) -> None:
        if total_count == 0:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Фонотека пуста")
            self.lbl_percentage.setText("  0%")
            return

        if selected_count > 0:
            pct = int((selected_count / total_count) * 100)
            self.progress_bar.setValue(pct)
            self.progress_bar.setFormat(f"Выделено треков: {selected_count} из {total_count}")
            self.lbl_percentage.setText(f"{pct:3d}%")
        else:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat(f"Всего загружено треков: {total_count}")
            self.lbl_percentage.setText("  0%")