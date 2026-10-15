"""
Панель форматирования структуры папок, имен файлов и метаданных.
Шаблоны представлены в наглядном виде без технических скобок.
"""
from typing import List, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox,
    QCheckBox, QPushButton, QInputDialog
)
from PySide6.QtCore import Signal
from core.domain.enums import TranslitMode

# Человекочитаемые шаблоны: (Отображаемый текст, Технический формат)
HUMAN_TRACK_TEMPLATES: List[Tuple[str, str]] = [
    ("01 - Track", "{index:02d} - {title}"),
    ("01. Track", "{index:02d}. {title}"),
    ("01_Track", "{index:02d}_{title}"),
    ("01-Track", "{index:02d}-{title}"),
    ("1 - Track", "{index} - {title}"),
    ("1. Track", "{index}. {title}"),
    ("1_Track", "{index}_{title}"),
    ("1-Track", "{index}-{title}"),
    ("Track", "{title}"),
    ("Artist - Track", "{artist} - {title}"),
    ("01. Artist - Track", "{index:02d}. {artist} - {title}"),
]

HUMAN_ALBUM_TEMPLATES: List[Tuple[str, str]] = [
    ("[2008] Album", "[{year}] {album}"),
    ("(2008) Album", "({year}) {album}"),
    ("2008 - Album", "{year} - {album}"),
    ("2008. Album", "{year}. {album}"),
    ("2008_Album", "{year}_{album}"),
    ("2008-Album", "{year}-{album}"),
    ("Album (2008)", "{album} ({year})"),
    ("1. Album", "{chrono_idx}. {album}"),
    ("Album", "{album}"),
]


class FormattingPanel(QWidget):
    settings_changed = Signal()
    apply_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._custom_track_templates: List[Tuple[str, str]] = []
        self._custom_album_templates: List[Tuple[str, str]] = []
        self._init_ui()

    def _notify(self, *args) -> None:
        self.settings_changed.emit()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ----------------------------------------------------------------------
        # 1. ГЛАВНЫЙ ТУМБЛЕР (По умолчанию выключен)
        # ----------------------------------------------------------------------
        self.chk_enable_formatting = QCheckBox("Включить форматирование экспорта")
        self.chk_enable_formatting.setChecked(False)
        self.chk_enable_formatting.toggled.connect(self._on_master_toggle)
        layout.addWidget(self.chk_enable_formatting)

        self.box_container = QWidget()
        l_cont = QVBoxLayout(self.box_container)
        l_cont.setContentsMargins(0, 0, 0, 0)
        l_cont.setSpacing(8)

        # ----------------------------------------------------------------------
        # 2. СТРУКТУРА ПАПОК АЛЬБОМОВ
        # ----------------------------------------------------------------------
        box_grp = QGroupBox("Структура каталогов и альбомов")
        l_grp = QVBoxLayout(box_grp)
        l_grp.setSpacing(6)

        l_grp.addWidget(QLabel("Тип группировки папок:"))
        self.combo_grouping = QComboBox()
        self.combo_grouping.addItems([
            "Альбомная (Исполнитель / [Год] Альбом / Треки)",
            "Плейлист (Папка плейлиста / Треки)",
            "Плоская (Все файлы в одну общую папку)"
        ])
        self.combo_grouping.currentIndexChanged.connect(self._notify)
        l_grp.addWidget(self.combo_grouping)

        l_grp.addWidget(QLabel("Вид папки альбома:"))
        row_alb = QHBoxLayout()
        self.combo_album_template = QComboBox()
        self.combo_album_template.currentIndexChanged.connect(self._notify)
        row_alb.addWidget(self.combo_album_template, stretch=1)

        btn_add_alb = QPushButton("+")
        btn_add_alb.setFixedWidth(28)
        btn_add_alb.setToolTip("Добавить свой шаблон альбома")
        btn_add_alb.clicked.connect(self._prompt_add_album_template)
        row_alb.addWidget(btn_add_alb)
        l_grp.addLayout(row_alb)

        self.chk_apply_album_tag = QCheckBox("Записывать шаблон с годом в тег «Альбом»")
        self.chk_apply_album_tag.setChecked(False)
        self.chk_apply_album_tag.toggled.connect(self._notify)
        l_grp.addWidget(self.chk_apply_album_tag)

        self.chk_merge_albums = QCheckBox("Сливать переиздания альбома (Remaster, Deluxe) в один")
        self.chk_merge_albums.setChecked(False)
        self.chk_merge_albums.toggled.connect(self._notify)
        l_grp.addWidget(self.chk_merge_albums)

        self.chk_merge_singles = QCheckBox("Сливать синглы и EP исполнителя в альбом «Singles»")
        self.chk_merge_singles.setChecked(False)
        self.chk_merge_singles.toggled.connect(self._notify)
        l_grp.addWidget(self.chk_merge_singles)

        l_cont.addWidget(box_grp)

        # ----------------------------------------------------------------------
        # 3. ИМЕНА ФАЙЛОВ И ТЕГИ НАЗВАНИЙ
        # ----------------------------------------------------------------------
        box_name = QGroupBox("Имена файлов и теги названий")
        l_name = QVBoxLayout(box_name)
        l_name.setSpacing(6)

        l_name.addWidget(QLabel("Вид имени файла трека:"))
        row_trk = QHBoxLayout()
        self.combo_naming = QComboBox()
        self.combo_naming.currentIndexChanged.connect(self._notify)
        row_trk.addWidget(self.combo_naming, stretch=1)

        btn_add_trk = QPushButton("+")
        btn_add_trk.setFixedWidth(28)
        btn_add_trk.setToolTip("Добавить свой шаблон трека")
        btn_add_trk.clicked.connect(self._prompt_add_track_template)
        row_trk.addWidget(btn_add_trk)
        l_name.addLayout(row_trk)

        # Взаимоисключающие пункты для тега названия
        self.chk_num_in_title = QCheckBox("Вшить номер трека в название (тег Title)")
        self.chk_num_in_title.setChecked(False)
        self.chk_num_in_title.toggled.connect(self._on_title_num_toggled)
        l_name.addWidget(self.chk_num_in_title)

        self.chk_strip_title_numbers = QCheckBox("Очистить название от номеров (тег Title)")
        self.chk_strip_title_numbers.setChecked(False)
        self.chk_strip_title_numbers.toggled.connect(self._on_title_strip_toggled)
        l_name.addWidget(self.chk_strip_title_numbers)

        l_cont.addWidget(box_name)

        # ----------------------------------------------------------------------
        # 4. ТРАНСЛИТЕРАЦИЯ И ОЧИСТКА
        # ----------------------------------------------------------------------
        box_meta = QGroupBox("Транслитерация и очистка метаданных")
        l_meta = QVBoxLayout(box_meta)
        l_meta.setSpacing(6)

        l_meta.addWidget(QLabel("Режим транслитерации:"))
        self.combo_translit = QComboBox()
        self.combo_translit.addItem("Без транслитерации (Выкл)", TranslitMode.OFF)
        self.combo_translit.addItem("Кириллица → Латиница (Lyubov)", TranslitMode.CYRILLIC_TO_LATIN)
        self.combo_translit.addItem("Латиница → Кириллица (Любовь)", TranslitMode.LATIN_TO_CYRILLIC)
        self.combo_translit.currentIndexChanged.connect(self._on_translit_changed)
        l_meta.addWidget(self.combo_translit)

        self.chk_translit_meta = QCheckBox("Транслитерировать и сами теги внутри аудиофайла")
        self.chk_translit_meta.setChecked(False)
        self.chk_translit_meta.setEnabled(False)  # По умолчанию выключено и серое
        self.chk_translit_meta.toggled.connect(self._notify)
        l_meta.addWidget(self.chk_translit_meta)

        self.chk_clean_feats = QCheckBox("Очистить исполнителя от фитов (Feat / Ft → Автор альбома)")
        self.chk_clean_feats.setChecked(False)
        self.chk_clean_feats.toggled.connect(self._notify)
        l_meta.addWidget(self.chk_clean_feats)

        self.chk_clear_lyrics = QCheckBox("Очистить текст песни (Удалить тег Lyrics)")
        self.chk_clear_lyrics.setChecked(False)
        self.chk_clear_lyrics.toggled.connect(self._notify)
        l_meta.addWidget(self.chk_clear_lyrics)

        l_cont.addWidget(box_meta)

        # ----------------------------------------------------------------------
        # 5. УМНЫЕ ФИЛЬТРЫ ИСКЛЮЧЕНИЙ (Все выключены по умолчанию)
        # ----------------------------------------------------------------------
        box_dedup = QGroupBox("Умный фильтр (Исключение из плана экспорта)")
        l_dedup = QVBoxLayout(box_dedup)
        l_dedup.setSpacing(4)

        self.chk_excl_dup = QCheckBox("Исключать чистые дубликаты (Duplicate)")
        self.chk_excl_dup.setChecked(False)
        self.chk_excl_dup.toggled.connect(self._notify)

        self.chk_excl_remix = QCheckBox("Исключать ремиксы и версии (Remix)")
        self.chk_excl_remix.setChecked(False)
        self.chk_excl_remix.toggled.connect(self._notify)

        self.chk_excl_feat = QCheckBox("Исключать совместные треки (Feat)")
        self.chk_excl_feat.setChecked(False)
        self.chk_excl_feat.toggled.connect(self._notify)

        self.chk_excl_karaoke = QCheckBox("Исключать минусовки / караоке (Karaoke)")
        self.chk_excl_karaoke.setChecked(False)
        self.chk_excl_karaoke.toggled.connect(self._notify)

        l_dedup.addWidget(self.chk_excl_dup)
        l_dedup.addWidget(self.chk_excl_remix)
        l_dedup.addWidget(self.chk_excl_feat)
        l_dedup.addWidget(self.chk_excl_karaoke)
        l_cont.addWidget(box_dedup)

        layout.addWidget(self.box_container)

        # Кнопка применения
        self.btn_apply = QPushButton("🚀 Применить форматирование")
        self.btn_apply.setFixedHeight(34)
        self.btn_apply.clicked.connect(self.apply_requested.emit)
        layout.addWidget(self.btn_apply)

        layout.addStretch()

        self._rebuild_combos()
        self._on_master_toggle(False)

    def _on_master_toggle(self, enabled: bool) -> None:
        """Включает/выключает всю панель форматирования."""
        self.box_container.setEnabled(enabled)
        self.btn_apply.setEnabled(enabled)
        self._notify()

    def _on_title_num_toggled(self, checked: bool) -> None:
        """Если вшиваем номер в название — снимаем флаг очистки названия."""
        if checked:
            self.chk_strip_title_numbers.blockSignals(True)
            self.chk_strip_title_numbers.setChecked(False)
            self.chk_strip_title_numbers.blockSignals(False)
        self._notify()

    def _on_title_strip_toggled(self, checked: bool) -> None:
        """Если очищаем название от номеров — снимаем флаг вшивания номера."""
        if checked:
            self.chk_num_in_title.blockSignals(True)
            self.chk_num_in_title.setChecked(False)
            self.chk_num_in_title.blockSignals(False)
        self._notify()

    def _on_translit_changed(self) -> None:
        """При выключенном транслите блокирует зависимый чекбокс."""
        mode = self.combo_translit.currentData()
        is_active = (mode != TranslitMode.OFF)
        self.chk_translit_meta.setEnabled(is_active)
        if not is_active:
            self.chk_translit_meta.setChecked(False)
        self._notify()

    def _rebuild_combos(self) -> None:
        self.combo_naming.blockSignals(True)
        self.combo_naming.clear()
        for label, tpl in self._custom_track_templates:
            self.combo_naming.addItem(f"⭐ {label}", tpl)
        for label, tpl in HUMAN_TRACK_TEMPLATES:
            if not any(tpl == c_tpl for _, c_tpl in self._custom_track_templates):
                self.combo_naming.addItem(label, tpl)
        self.combo_naming.blockSignals(False)

        self.combo_album_template.blockSignals(True)
        self.combo_album_template.clear()
        for label, tpl in self._custom_album_templates:
            self.combo_album_template.addItem(f"⭐ {label}", tpl)
        for label, tpl in HUMAN_ALBUM_TEMPLATES:
            if not any(tpl == c_tpl for _, c_tpl in self._custom_album_templates):
                self.combo_album_template.addItem(label, tpl)
        self.combo_album_template.blockSignals(False)

    def set_custom_templates(self, track_templates: List[str], album_templates: List[str]) -> None:
        self._custom_track_templates = [(tpl, tpl) for tpl in track_templates if tpl]
        self._custom_album_templates = [(tpl, tpl) for tpl in album_templates if tpl]
        self._rebuild_combos()

    def get_custom_templates_for_save(self) -> Tuple[List[str], List[str]]:
        tr = [tpl for _, tpl in self._custom_track_templates]
        alb = [tpl for _, tpl in self._custom_album_templates]
        return tr, alb

    def _prompt_add_track_template(self) -> None:
        text, ok = QInputDialog.getText(
            self, "Новый шаблон имени файла",
            "Введите шаблон имени файла:\nПримеры:\n01 - Track\n01. Artist - Track\n1_Track"
        )
        if ok and text.strip():
            raw = text.strip()
            # Преобразуем человеческий вид в рабочий шаблон
            tech = raw.replace("01", "{index:02d}").replace("1", "{index}")
            tech = tech.replace("Artist", "{artist}").replace("Track", "{title}")
            item = (raw, tech)
            if not any(tech == c[1] for c in self._custom_track_templates):
                self._custom_track_templates.insert(0, item)
                self._rebuild_combos()
                self.combo_naming.setCurrentIndex(0)
                self._notify()

    def _prompt_add_album_template(self) -> None:
        text, ok = QInputDialog.getText(
            self, "Новый шаблон папки альбома",
            "Введите шаблон папки альбома:\nПримеры:\n(2008) Album\n[2008] ~ Album\n2008_Album"
        )
        if ok and text.strip():
            raw = text.strip()
            tech = raw.replace("2008", "{year}").replace("Album", "{album}")
            item = (raw, tech)
            if not any(tech == c[1] for c in self._custom_album_templates):
                self._custom_album_templates.insert(0, item)
                self._rebuild_combos()
                self.combo_album_template.setCurrentIndex(0)
                self._notify()

    def is_formatting_enabled(self) -> bool:
        return self.chk_enable_formatting.isChecked()

    def get_selected_naming_template(self) -> str:
        return self.combo_naming.currentData() or "{index:02d} - {title}"

    def get_selected_album_template(self) -> str:
        return self.combo_album_template.currentData() or "[{year}] {album}"

    def get_translit_mode(self) -> TranslitMode:
        return self.combo_translit.currentData() or TranslitMode.OFF

    def set_detected_structure(self, is_album_structure: bool) -> None:
        """Устанавливает выявленную структуру исходной папки (Альбомная или Одна папка)."""
        # 0 = Альбомная, 2 = Плоская (Одна папка)
        target_idx = 0 if is_album_structure else 2
        self.combo_grouping.blockSignals(True)
        self.combo_grouping.setCurrentIndex(target_idx)
        self.combo_grouping.blockSignals(False)