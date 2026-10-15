"""
Интерфейсы анализа, очистки и распознавания метаданных (ISP).
Текстовая очистка выделена в ITextCleaner, а распознавание версий — в ITrackNormalizer.
"""
from abc import ABC, abstractmethod
from typing import Tuple, List


class ITextCleaner(ABC):
    """Контракт глубокой очистки строк для вычисления дедупликационных сигнатур."""

    @abstractmethod
    def super_clean(self, text: str) -> str:
        """Транслитерирует и удаляет спецсимволы/пробелы/регистр для чистого сравнения."""
        pass

    @abstractmethod
    def clean_album_name(self, album: str) -> str:
        """Удаляет маркеры переизданий (Deluxe, Remaster, года в скобках) из названия альбома."""
        pass

    @abstractmethod
    def clean_junk(self, text: str) -> str:
        """Удаляет мусорные приписки: сайты, битрейт, [Official Video], promo и т.д."""
        pass

    @abstractmethod
    def clean_track_title(self, title: str) -> str:
        """Очищает название трека от лишнего мусора, сохраняя числа, являющиеся частью названия."""
        pass


class ITrackNormalizer(ITextCleaner, ABC):
    """Контракт разбора трека на составляющие (фиты, ремиксы, караоке)."""

    @abstractmethod
    def extract_features(self, title: str, artist: str) -> Tuple[str, List[str], List[str], bool]:
        """
        Разбирает название трека.
        Возвращает: (nuclear_title, feats_list, versions_list, is_karaoke)
        """
        pass