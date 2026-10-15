"""
Компактное диалоговое окно настройки и запуска физического экспорта.
"""
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QCheckBox, QLabel, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt

from core.interfaces.settings_repository import ISettingsRepository
from ui.theme import SUCCESS_BTN_QSS


class ExportDialog(QDialog):
    """Диалог подтверждения целевого пути экспорта фонотеки."""

    def __init__(
        self,
        settings_repo: ISettingsRepository,
        parent=None,
        source_root: Optional[Path] = None,
        active_count: int = 0,
        excluded_count: int = 0
    ):
        super().__init__(parent)
        self.setWindowTitle("Экспорт фонотеки")
        self.setModal(True)
        self.setFixedWidth(640)

        self._settings = settings_repo
        self._source_root = source_root or Path.cwd()
        self._active_count = active_count
        self._excluded_count = excluded_count

        saved_path = self._settings.load_last_export_path()
        self._saved_custom_path = saved_path if saved_path else str(self._source_root / "Exported_Music")

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 1. Информация о треках
        lbl_info = QLabel(
            f"Готово к экспорту: <b>{self._active_count}</b> треков "
            f"(исключено: <span style='color: #E74C3C;'>{self._excluded_count}</span>)"
        )
        layout.addWidget(lbl_info)

        # 2. Выбор пути
        row_path = QHBoxLayout()
        row_path.setSpacing(8)

        self.btn_browse = QPushButton("📂 Выбрать путь")
        self.btn_browse.setFixedHeight(30)
        self.btn_browse.clicked.connect(self._choose_directory)
        row_path.addWidget(self.btn_browse)

        self.edit_path = QLineEdit(self._saved_custom_path)
        self.edit_path.setFixedHeight(30)
        row_path.addWidget(self.edit_path, stretch=1)

        self.chk_modify_source = QCheckBox("Изменить исходные файлы")
        self.chk_modify_source.setToolTip("Файлы будут реструктурированы и переименованы прямо в исходной папке")
        self.chk_modify_source.toggled.connect(self._on_modify_source_toggled)
        row_path.addWidget(self.chk_modify_source)

        layout.addLayout(row_path)

        # 3. Нижний ряд кнопок
        row_bottom = QHBoxLayout()
        row_bottom.setSpacing(8)
        row_bottom.addStretch()

        btn_cancel = QPushButton("Отмена")
        btn_cancel.setFixedHeight(32)
        btn_cancel.setFixedWidth(90)
        btn_cancel.clicked.connect(self.reject)
        row_bottom.addWidget(btn_cancel)

        self.btn_export = QPushButton("🚀 Экспорт")
        self.btn_export.setFixedHeight(32)
        self.btn_export.setFixedWidth(120)
        self.btn_export.setStyleSheet(SUCCESS_BTN_QSS)
        self.btn_export.clicked.connect(self._on_export_clicked)
        row_bottom.addWidget(self.btn_export)

        layout.addLayout(row_bottom)

    def _on_modify_source_toggled(self, checked: bool) -> None:
        self.btn_browse.setEnabled(not checked)
        self.edit_path.setEnabled(not checked)

        if checked:
            self._saved_custom_path = self.edit_path.text()
            self.edit_path.setText(str(self._source_root))
        else:
            self.edit_path.setText(self._saved_custom_path)

    def _choose_directory(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите папку для экспорта", self.edit_path.text())
        if dir_path:
            self.edit_path.setText(dir_path)
            self._saved_custom_path = dir_path

    def _on_export_clicked(self) -> None:
        target_dir = self.get_target_path()

        if not self.chk_modify_source.isChecked():
            if not str(target_dir).strip():
                QMessageBox.warning(self, "Экспорт", "Укажите путь к папке назначения.")
                return
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                self._settings.save_last_export_path(str(target_dir))
            except Exception as e:
                QMessageBox.critical(self, "Ошибка пути", f"Не удалось создать каталог:\n{e}")
                return

        self.accept()

    def get_target_path(self) -> Path:
        if self.chk_modify_source.isChecked():
            return self._source_root
        return Path(self.edit_path.text().strip())

    def is_modify_source(self) -> bool:
        return self.chk_modify_source.isChecked()