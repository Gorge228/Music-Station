"""
Инспектор фонотеки со свободным упорядочиванием панелей и сохранением в репозиторий настроек.
"""
from typing import Dict, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QToolButton,
    QLabel, QCheckBox, QPushButton, QFrame, QStackedWidget
)
from PySide6.QtCore import Qt, QPoint

from ui.panels.formatting_panel import FormattingPanel
from ui.panels.tag_editor_panel import TagEditorPanel
from ui.panels.converter_panel import ConverterPanel
from ui.panels.debug_panel import TrackDebugPanel
from ui.panels.hotkeys_panel import HotkeysPanel
from core.interfaces.settings_repository import ISettingsRepository
from ui.theme import PANELS_MENU_POPUP_QSS, INSPECTOR_TABS_QSS, PRIMARY_BTN_QSS


class PanelsMenuPopup(QFrame):
    """Контекстное всплывающее меню выбора отображаемых панелей."""

    def __init__(self, inspector: "InspectorPanel", parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.inspector = inspector
        self.setStyleSheet(PANELS_MENU_POPUP_QSS)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(10, 8, 10, 8)
        self.root_layout.setSpacing(6)
        self._build_items()

    def _build_items(self) -> None:
        while self.root_layout.count():
            item = self.root_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.root_layout.addWidget(QLabel("Отображение и порядок панелей:"))

        for idx, key in enumerate(self.inspector.current_order):
            if key not in self.inspector.registry:
                continue
            title, _ = self.inspector.registry[key]
            row = QHBoxLayout()
            row.setSpacing(6)

            chk = QCheckBox(title)
            chk.setChecked(key in self.inspector.visible_keys)
            chk.toggled.connect(lambda checked, k=key: self.inspector.toggle_panel(k, checked))
            row.addWidget(chk, stretch=1)

            btn_up = QPushButton("▲")
            btn_up.setFixedWidth(26)
            btn_up.setEnabled(idx > 0)
            btn_up.clicked.connect(lambda _, i=idx: self._move_item_up(i))
            row.addWidget(btn_up)

            self.root_layout.addLayout(row)

    def _move_item_up(self, index: int) -> None:
        if index > 0:
            order = self.inspector.current_order
            order[index], order[index - 1] = order[index - 1], order[index]
            self.inspector.rebuild_tabs()
            self._build_items()


class InspectorPanel(QWidget):
    """Главная панель инспектора с переключаемыми вкладками инструментов."""

    def __init__(self, settings_repo: ISettingsRepository, parent=None):
        super().__init__(parent)
        self._settings = settings_repo

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.p_format = FormattingPanel()
        self.p_tags = TagEditorPanel()
        self.p_converter = ConverterPanel()
        self.p_debug = TrackDebugPanel()


        self.registry: Dict[str, Tuple[str, QWidget]] = {
            "p_format": ("⚙ Форматирование", self.p_format),
            "p_tags": ("🏷 Редактор тегов", self.p_tags),
            "p_converter": ("🎛 Конвертер", self.p_converter),
            "p_debug": ("🔍 Инспектор трека", self.p_debug),
        }

        self.btn_panel_menu = QToolButton()
        self.btn_panel_menu.setText("☰ Панели ▼")
        self.btn_panel_menu.setCursor(Qt.PointingHandCursor)
        self.btn_panel_menu.clicked.connect(self._show_panels_popup)

        self.stack = QStackedWidget()
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(False)
        self.tabs.setMovable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setStyleSheet(INSPECTOR_TABS_QSS)
        self.tabs.tabBar().tabMoved.connect(self._on_tab_dragged)
        self.tabs.currentChanged.connect(self._on_active_tab_changed)
        self.tabs.setCornerWidget(self.btn_panel_menu, Qt.TopRightCorner)

        self.empty_widget = QWidget()
        l_empty = QVBoxLayout(self.empty_widget)
        l_empty.setAlignment(Qt.AlignCenter)
        l_empty.addWidget(QLabel("Все панели скрыты"))

        btn_reopen = QPushButton("☰ Открыть панели инструментов")
        btn_reopen.setStyleSheet(PRIMARY_BTN_QSS)
        btn_reopen.clicked.connect(self._show_panels_popup)
        l_empty.addWidget(btn_reopen)

        self.stack.addWidget(self.tabs)
        self.stack.addWidget(self.empty_widget)
        layout.addWidget(self.stack)

        saved_cfg = self._settings.load_panels_config(list(self.registry.keys()))
        self.current_order = saved_cfg["order"]
        self.visible_keys = set(saved_cfg["visible"])
        self._initial_active = saved_cfg.get("active", "")

        self.rebuild_tabs()

    def rebuild_tabs(self) -> None:
        self.tabs.blockSignals(True)
        cur_widget = self.tabs.currentWidget()
        self.tabs.clear()

        for key in self.current_order:
            if key in self.visible_keys and key in self.registry:
                title, widget = self.registry[key]
                self.tabs.addTab(widget, title)

        if self.tabs.count() == 0:
            self.stack.setCurrentWidget(self.empty_widget)
        else:
            self.stack.setCurrentWidget(self.tabs)
            found_idx = -1
            if cur_widget:
                found_idx = self.tabs.indexOf(cur_widget)
            elif self._initial_active and self._initial_active in self.registry:
                found_idx = self.tabs.indexOf(self.registry[self._initial_active][1])

            if found_idx != -1:
                self.tabs.setCurrentIndex(found_idx)

        self.tabs.blockSignals(False)
        self._save_state()

    def toggle_panel(self, key: str, visible: bool) -> None:
        if visible:
            self.visible_keys.add(key)
        else:
            self.visible_keys.discard(key)
        self.rebuild_tabs()

    def _show_panels_popup(self) -> None:
        popup = PanelsMenuPopup(self, self)
        if self.tabs.count() == 0:
            center_pt = self.mapToGlobal(self.rect().center())
            popup.move(center_pt.x() - 110, center_pt.y() - 100)
        else:
            pos = self.btn_panel_menu.mapToGlobal(QPoint(0, self.btn_panel_menu.height() + 2))
            popup.move(pos)
        popup.show()

    def _on_tab_dragged(self, from_idx: int, to_idx: int) -> None:
        visible_ordered = []
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            for k, (_, reg_w) in self.registry.items():
                if reg_w == w:
                    visible_ordered.append(k)
                    break

        # Скрытые вкладки сохраняют свой порядок
        hidden_ordered = [k for k in self.current_order if k not in visible_ordered]
        self.current_order = visible_ordered + hidden_ordered
        self._save_state()


        new_order = [k for k in self.current_order if k not in visible_ordered] + visible_ordered
        vis_idx = 0
        final_order = []
        for k in self.current_order:
            if k in self.visible_keys:
                final_order.append(visible_ordered[vis_idx])
                vis_idx += 1
            else:
                final_order.append(k)

        self.current_order = final_order
        self._save_state()

    def _on_active_tab_changed(self, idx: int) -> None:
        self._save_state()

    def _save_state(self) -> None:
        active_key = ""
        cur_w = self.tabs.currentWidget()
        if cur_w:
            for k, (_, w) in self.registry.items():
                if w == cur_w:
                    active_key = k
                    break

        self._settings.save_panels_config(
            order=self.current_order,
            visible=list(self.visible_keys),
            active=active_key
        )