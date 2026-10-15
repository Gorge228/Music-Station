"""
Контракт репозитория настроек приложения (DIP).
Позволяет слою UI и сервисам сохранять конфигурацию независимо от формата хранения.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class ISettingsRepository(ABC):
    """Интерфейс персистентного сохранения конфигураций приложения."""

    @abstractmethod
    def save_panels_config(self, order: List[str], visible: List[str], active: str) -> None:
        """Сохраняет порядок, видимость и активную вкладку панелей инспектора."""
        pass

    @abstractmethod
    def load_panels_config(self, default_order: List[str]) -> Dict[str, Any]:
        """Загружает конфигурацию панелей инспектора."""
        pass

    @abstractmethod
    def save_tracklist_columns(
        self, col_widths: Dict[int, int], col_hidden: Dict[int, bool], sort_col: int, sort_order: int
    ) -> None:
        """Сохраняет геометрию колонок, флаги скрытия и параметры сортировки."""
        pass

    @abstractmethod
    def load_tracklist_columns(self) -> Dict[str, Any]:
        """Загружает сохраненные параметры колонок."""
        pass

    @abstractmethod
    def save_last_export_path(self, path_str: str) -> None:
        """Сохраняет последний использованный путь экспорта."""
        pass

    @abstractmethod
    def load_last_export_path(self) -> str:
        """Загружает последний сохраненный путь экспорта."""
        pass

    @abstractmethod
    def save_custom_templates(self, track_templates: List[str], album_templates: List[str]) -> None:
        """Сохраняет пользовательские шаблоны треков и альбомов."""
        pass

    @abstractmethod
    def load_custom_templates(self) -> Tuple[List[str], List[str]]:
        """Загружает сохраненные пользовательские шаблоны."""
        pass

    def save_window_state(self, geometry: bytes, splitter_state: bytes) -> None:
        """Безопасная реализация по умолчанию: сохраняет геометрию окна и сплиттера."""
        pass

    def load_window_state(self) -> Tuple[Optional[bytes], Optional[bytes]]:
        """Безопасная реализация по умолчанию: загружает геометрию окна и сплиттера."""
        return None, None