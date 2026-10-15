"""
Верхняя панель инструментов и навигации.
Одна кнопка импорта с поддержкой мульти-выбора папок и файлов, без лишних полей и списков.
"""
from pathlib import Path
from typing import List
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLineEdit, QFileDialog,
    QDialog, QStackedWidget, QListView, QTreeView
)
from PySide6.QtCore import Signal
from ui.theme import ACTION_BTN_QSS


class MultiItemFileDialog(QFileDialog):
    """Диалог, позволяющий одновременно выделять и несколько папок, и несколько файлов."""

    def __init__(self, parent=None, caption="Импортировать музыку", directory=""):
        super().__init__(parent, caption)
        self.setFileMode(QFileDialog.FileMode.ExistingFiles)
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        if directory:
            self.setDirectory(str(directory))

        self._chosen_paths: List[Path] = []
        self._line_edit = self.findChild(QLineEdit)
        self.directoryEntered.connect(self._on_dir_entered)

        # Отслеживаем выбор элементов в обоих режимах отображения (список / дерево)
        stacked = self.findChild(QStackedWidget)
        if stacked:
            for v in (stacked.findChild(QListView), stacked.findChild(QTreeView)):
                if v and v.selectionModel():
                    v.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _on_dir_entered(self) -> None:
        if self._line_edit:
            self._line_edit.clear()

    def _on_selection_changed(self) -> None:
        if not self._line_edit:
            return
        items = self._get_selected_from_views()
        if items:
            self._line_edit.setText(" ".join(f'"{p.name}"' for p in items))

    def _get_selected_from_views(self) -> List[Path]:
        curr_dir = Path(self.directory().absolutePath())
        stacked = self.findChild(QStackedWidget)
        selected_paths: List[Path] = []
        if stacked:
            for v in (stacked.findChild(QListView), stacked.findChild(QTreeView)):
                if v and v.selectionModel():
                    indexes = v.selectionModel().selectedRows()
                    if indexes:
                        for idx in indexes:
                            name = str(idx.data())
                            p = curr_dir / name
                            if p.exists() and p not in selected_paths:
                                selected_paths.append(p)
                        break
        return selected_paths

    def accept(self) -> None:
        selected = self._get_selected_from_views()
        if not selected and self.selectedFiles():
            selected = [Path(f) for f in self.selectedFiles() if Path(f).exists()]

        # Если ничего конкретного не выделено, берем текущую открытую папку
        if not selected:
            curr_dir = Path(self.directory().absolutePath())
            if curr_dir.exists():
                selected = [curr_dir]

        self._chosen_paths = selected
        QDialog.accept(self)

    def get_selected_paths(self) -> List[Path]:
        return getattr(self, "_chosen_paths", [])


class TopBar(QWidget):
    """Верхняя панель: только одна кнопка импорта, поиск, история и сервисные кнопки."""
    paths_selected = Signal(list)
    clear_requested = Signal()
    reset_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()
    invert_requested = Signal()
    settings_requested = Signal()

    search_changed = Signal(str)
    preview_toggled = Signal(bool)
    show_excluded_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # 1. Кнопки истории
        self.btn_undo = QPushButton("↶")
        self.btn_undo.setFixedSize(30, 26)
        self.btn_undo.setToolTip("Назад / Отменить действие (Ctrl+Z)")
        self.btn_undo.setStyleSheet(ACTION_BTN_QSS)
        self.btn_undo.clicked.connect(self.undo_requested.emit)

        self.btn_redo = QPushButton("↷")
        self.btn_redo.setFixedSize(30, 26)
        self.btn_redo.setToolTip("Повторить отменённое действие (Ctrl+Y)")
        self.btn_redo.setStyleSheet(ACTION_BTN_QSS)
        self.btn_redo.clicked.connect(self.redo_requested.emit)

        self.btn_reset_all = QPushButton("⟲")
        self.btn_reset_all.setFixedSize(30, 26)
        self.btn_reset_all.setToolTip("Сбросить изменения фонотеки к исходным")
        self.btn_reset_all.setStyleSheet(ACTION_BTN_QSS)
        self.btn_reset_all.clicked.connect(self.reset_requested.emit)

        layout.addWidget(self.btn_undo)
        layout.addWidget(self.btn_redo)
        layout.addWidget(self.btn_reset_all)

        # 2. ЕДИНСТВЕННАЯ КНОПКА ИМПОРТА (без списков и без поля пути)
        self.btn_import = QPushButton("📂 Импортировать")
        self.btn_import.clicked.connect(self._on_import_clicked)
        layout.addWidget(self.btn_import)

        # 3. Поисковая строка (занимает всё свободное пространство)
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("🔍 Поиск по названию, автору, альбому... (Ctrl+F)")
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.setMinimumWidth(260)
        self.edit_search.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self.edit_search, stretch=1)

        # 4. Режимы и сервисные кнопки
        self.btn_invert = QPushButton("⇄ Инверсия")
        self.btn_invert.setToolTip("Поменять левую и правую панели местами (Ctrl+Tab)")
        self.btn_invert.clicked.connect(self.invert_requested.emit)
        layout.addWidget(self.btn_invert)

        self.chk_preview = QPushButton("Предпросмотр")
        self.chk_preview.setCheckable(True)
        self.chk_preview.setChecked(True)
        self.chk_preview.toggled.connect(self.preview_toggled.emit)
        layout.addWidget(self.chk_preview)

        self.chk_show_excluded = QPushButton("Показать исключённые")
        self.chk_show_excluded.setCheckable(True)
        self.chk_show_excluded.setChecked(True)
        self.chk_show_excluded.toggled.connect(self.show_excluded_toggled.emit)
        layout.addWidget(self.chk_show_excluded)

        self.btn_settings = QPushButton("⚙ Настройки")
        self.btn_settings.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.btn_settings)

        self.btn_clear = QPushButton("🧹 Очистить")
        self.btn_clear.clicked.connect(self.clear_requested.emit)
        layout.addWidget(self.btn_clear)

    def _on_import_clicked(self) -> None:
        dlg = MultiItemFileDialog(self, "Импортировать музыку")
        if dlg.exec():
            paths = dlg.get_selected_paths()
            if paths:
                self.paths_selected.emit(paths)

    def focus_search(self) -> None:
        self.edit_search.setFocus()
        self.edit_search.selectAll()

    def set_preview_checked(self, checked: bool) -> None:
        self.chk_preview.blockSignals(True)
        self.chk_preview.setChecked(checked)
        self.chk_preview.blockSignals(False)

    def set_show_excluded_checked(self, checked: bool) -> None:
        self.chk_show_excluded.blockSignals(True)
        self.chk_show_excluded.setChecked(checked)
        self.chk_show_excluded.blockSignals(False)