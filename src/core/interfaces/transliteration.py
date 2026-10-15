"""Контракт сервиса транслитерации."""
from abc import ABC, abstractmethod
from core.domain.enums import TranslitMode


class ITransliterationService(ABC):
    """Контракт преобразования строк между алфавитами."""

    @abstractmethod
    def transform(self, text: str, mode: TranslitMode) -> str:
        """Преобразует строку в соответствии с выбранным TranslitMode."""
        pass