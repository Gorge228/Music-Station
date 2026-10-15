# core/interfaces/metadata.py
"""
Интерфейсы для чтения и записи строковых тегов.
Соблюдение Interface Segregation Principle (ISP): текстовые теги отделены от работы с обложками.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from core.domain.models import AudioMetadata


class IMetadataReader(ABC):
    """Контракт чтения метаданных."""
    @abstractmethod
    def read(self, path: Path) -> AudioMetadata:
        """Считывает метаданные из указанного аудиофайла."""
        pass

    @abstractmethod
    def supports(self, path: Path) -> bool:
        """Проверяет, поддерживается ли формат файла реализацией."""
        pass


class IMetadataWriter(ABC):
    """Контракт записи метаданных."""
    @abstractmethod
    def write(self, path: Path, metadata: AudioMetadata, encoding: str = "utf-8") -> None:
        """Записывает метаданные в файл с заданной кодировкой."""
        pass