"""
Контракты извлечения и внедрения обложек (ISP).
Позволяет компонентам запрашивать только операцию чтения без риска записи.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class ICoverArtReader(ABC):
    """Контракт чтения обложек из аудиофайлов."""

    @abstractmethod
    def read_cover(self, path: Path) -> Optional[bytes]:
        """Возвращает сырые бинарные данные обложки (JPEG/PNG) или None."""
        pass


class ICoverArtWriter(ABC):
    """Контракт записи и удаления обложек в аудиофайлах."""

    @abstractmethod
    def write_cover(self, path: Path, cover_bytes: Optional[bytes]) -> None:
        """Записывает переданную обложку или удаляет её при cover_bytes=None."""
        pass


class ICoverArtHandler(ICoverArtReader, ICoverArtWriter, ABC):
    """Объединенный контракт полного управления обложкой аудиофайла."""
    pass