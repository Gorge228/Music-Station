"""
Интерфейсы для работы с текстовыми тегами аудиофайлов (ISP).
Изолированы от работы с графикой (обложками).
"""
from abc import ABC, abstractmethod
from pathlib import Path
from core.domain.models import AudioMetadata


class IMetadataReader(ABC):
    """Контракт безопасного извлечения метаданных из аудиофайла."""

    @abstractmethod
    def read(self, path: Path) -> AudioMetadata:
        """Считывает текстовые метаданные из файла."""
        pass

    @abstractmethod
    def supports(self, path: Path) -> bool:
        """Проверяет, поддерживается ли формат файла данным обработчиком."""
        pass


class IMetadataWriter(ABC):
    """Контракт безопасной записи метаданных в аудиофайл."""

    @abstractmethod
    def write(self, path: Path, metadata: AudioMetadata, encoding: str = "utf-8") -> None:
        """Записывает метаданные в аудиофайл."""
        pass