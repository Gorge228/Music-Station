"""
Централизованная дизайн-система и стили приложения (Design System).
Инкапсулирует цвета статусов, общую темную тему (QSS) и стили компонентов.
"""
from core.domain.enums import DuplicateStatus

# Цветовая маркировка статусов треков
STATUS_COLORS = {
    DuplicateStatus.ORIGINAL: "#2ECC71",   # Зеленый (основной трек)
    DuplicateStatus.DUPLICATE: "#E74C3C",  # Красный (чистый дубликат)
    DuplicateStatus.REMIX: "#3498DB",      # Синий (версия, ремикс)
    DuplicateStatus.FEAT: "#F39C12",       # Оранжевый (совместный трек)
    DuplicateStatus.KARAOKE: "#9B59B6",    # Фиолетовый (минусовка)
    DuplicateStatus.UNIQUE: "#1ABC9C",     # Бирюзовый (уникальный)
}

# Базовая темная тема приложения (Global Stylesheet)
DARK_QSS = """
QWidget {
    background-color: #1A1C20;
    color: #DCE0E6;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 12px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}

QSplitter::handle {
    background-color: #262930;
}
QSplitter::handle:hover {
    background-color: #3B82F6;
}

QTreeWidget, QTableWidget {
    background-color: #131417;
    border: 1px solid #282B33;
    border-radius: 4px;
    gridline-color: #20232A;
    outline: none;
    padding: 0px;
}
QTreeWidget::item, QTableWidget::item {
    height: 25px;
    border-radius: 2px;
    padding: 4px;
}
QTreeWidget::item:hover:selectable, QTableWidget::item:hover:selectable {
    background-color: #1F2228;
}
QTreeWidget::item:selected, QTableWidget::item:selected {
    background-color: #2B3545;
    color: #FFFFFF;
}

QScrollArea {
    background-color: transparent;
    border: none;
}
QHeaderView {
    background-color: #21242B;
    border: none;
}
QHeaderView::section {
    background-color: #21242B;
    color: #9AA0A6;
    padding: 5px 8px;
    border: none;
    border-right: 1px solid #2B2F38;
    border-bottom: 2px solid #2B2F38;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
}
QHeaderView::section:hover {
    background-color: #282C35;
    color: #FFFFFF;
}

QPushButton, QToolButton {
    background-color: #282C35;
    border: 1px solid #3A3F4B;
    border-radius: 4px;
    color: #E1E3E6;
    padding: 5px 12px;
    font-weight: 500;
}
QPushButton:hover, QToolButton:hover {
    background-color: #323843;
    border-color: #4C5362;
    color: #FFFFFF;
}
QPushButton:pressed, QToolButton:pressed {
    background-color: #1E2127;
}

QPushButton:checked, QToolButton:checked {
    border-color: #2563EB;
    color: #FFFFFF;
    font-weight: 600;
}

QLineEdit, QComboBox, QTextEdit {
    background-color: #181A1F;
    border: 1px solid #333742;
    border-radius: 4px;
    padding: 3px 6px;
    color: #FFFFFF;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #3B82F6;
}
QLineEdit:disabled, QComboBox:disabled, QTextEdit:disabled {
    background-color: #131417;
    color: #555A64;
    border-color: #26282E;
}

QComboBox QAbstractItemView {
    background-color: #1A1D24;
    color: #DCE0E6;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
    border: 1px solid #3B82F6;
}

QScrollArea {
    background-color: transparent;
    border: none;
}
QScrollBar::handle:vertical:hover {
    background-color: #3B82F6;
}

QMenu {
    background-color: #1A1D24;
    border: 1px solid #333842;
    color: #DCE0E6;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 10px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #2563EB;
    color: #FFFFFF;
}
"""

# Стили для интерактивной зоны обложки (CoverDropLabel)
COVER_DROP_QSS = """
CoverDropLabel {
    background-color: #14161B;
    border: 2px dashed #3A3F4B;
    border-radius: 8px;
    color: #8C929D;
    font-size: 11px;
    font-weight: 500;
}
CoverDropLabel:hover {
    border-color: #3B82F6;
    background-color: #171A21;
    color: #DCE0E6;
}
"""

# Стили карточки галереи обложек
COVER_CARD_QSS = """
CoverCard {
    background-color: #17191F;
    border: 1px solid #282B35;
    border-radius: 8px;
}
CoverCard:hover {
    background-color: #1F2432;
    border: 2px solid #3B82F6;
}
"""

# Стили для кнопок действий в панели управления
ACTION_BTN_QSS = """
QPushButton {
    background-color: #21242B;
    border: 1px solid #363B47;
    border-radius: 4px;
    color: #DCE0E6;
    font-size: 13px;
    font-weight: bold;
    padding: 0px;
}
QPushButton:hover {
    background-color: #2D3340;
    border-color: #3B82F6;
    color: #FFFFFF;
}
QPushButton:pressed {
    background-color: #1A1D24;
}
"""

# Стили для кнопки успешного запуска (Экспорт)
SUCCESS_BTN_QSS = """
QPushButton {
    background-color: #1E7E34;
    border: 1px solid #28A745;
    border-radius: 4px;
    color: #FFFFFF;
    font-weight: 700;
}
QPushButton:hover { background-color: #218838; }
QPushButton:pressed { background-color: #19692C; }
QPushButton:disabled { background-color: #163820; color: #5B7563; border-color: #1D4728; }
"""

# Стили для первичных кнопок действий (Применить)
PRIMARY_BTN_QSS = """
QPushButton {
    background-color: #2563EB;
    border: 1px solid #3B82F6;
    border-radius: 4px;
    color: #FFFFFF;
    font-weight: 700;
}
QPushButton:hover { background-color: #1D4ED8; }
QPushButton:pressed { background-color: #1E40AF; }
"""

# Стили для всплывающего окна управления вкладками
PANELS_MENU_POPUP_QSS = """
PanelsMenuPopup {
    background-color: #1A1D24;
    border: 1px solid #3B82F6;
    border-radius: 6px;
}
QLabel {
    color: #DCE0E6;
    font-weight: 600;
    font-size: 11px;
}
QCheckBox {
    color: #FFFFFF;
    font-size: 11px;
    spacing: 8px;
}
"""

# Стили таб-бара инспектора
INSPECTOR_TABS_QSS = """
QTabWidget::pane {
    border: 1px solid #282B33;
    background-color: #181A1F;
}
QTabBar::tab {
    background-color: #20232A;
    border: 1px solid #282B33;
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #8C929D;
    font-weight: 600;
    font-size: 11px;
}
QTabBar::tab:selected {
    background-color: #181A1F;
    color: #3B82F6;
    border-top: 2px solid #3B82F6;
}
QTabBar QToolButton {
    background-color: #21242B;
    border: 1px solid #363B47;
    border-radius: 4px;
    margin: 2px 2px;
    padding: 1px;
    width: 18px;
    height: 22px;
}
QTabBar QToolButton:hover {
    background-color: #2D3340;
    border-color: #3B82F6;
}
"""

# Стили прогресс-бара нижней панели
PROGRESS_BAR_QSS = """
QProgressBar {
    background-color: #16181D;
    border: 1px solid #282B33;
    border-radius: 3px;
    text-align: center;
    color: #FFFFFF;
    font-weight: 600;
    height: 24px;
}
QProgressBar::chunk {
    background-color: #27AE60;
}
"""