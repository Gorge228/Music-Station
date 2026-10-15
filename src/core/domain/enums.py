"""
Доменные перечисления (Enums).
Определяют допустимые форматы аудиофайлов, статусы аудита,
стили формирования каталогов и режимы транслитерации.
"""
from enum import Enum, auto


class DuplicateStatus(Enum):
    """Статус трека, определяемый дедупликатором фонотеки."""
    ORIGINAL = auto()   # Основная версия трека из номерного альбома
    UNIQUE = auto()     # Единственный уникальный трек без аналогов
    FEAT = auto()       # Совместная композиция (гостевое участие)
    REMIX = auto()      # Ремикс, инструментал, альтернативная или Live-версия
    KARAOKE = auto()    # Минусовка / фонограмма
    DUPLICATE = auto()  # Избыточный повтор песни (кандидат на удаление/пропуск)


class AudioFormat(str, Enum):
    """Поддерживаемые аудиоформаты и расширения файлов."""
    MP3 = "mp3"
    FLAC = "flac"
    M4A = "m4a"
    ALAC = "alac"
    OGG = "ogg"
    OPUS = "opus"
    WAV = "wav"
    WMA = "wma"
    AAC = "aac"
    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, ext: str) -> "AudioFormat":
        """
        Безопасно преобразует строковое расширение файла (с точкой или без)
        в элемент перечисления AudioFormat.
        """
        cleaned = ext.lower().lstrip(".")
        try:
            return cls(cleaned)
        except ValueError:
            return cls.UNKNOWN


class GroupingMode(Enum):
    """Стратегия распределения файлов по выходным каталогам при экспорте."""
    BY_METADATA = auto()    # Альбомная: Исполнитель / [Год] Альбом / Трек
    PLAYLIST = auto()       # Иерархический плейлист: Playlists / Имя / Трек
    FLAT_PLAYLIST = auto()  # Плоский плейлист: Имя плейлиста / Трек (Various Artists)
    AS_IS = auto()          # Повторение структуры каталогов источника
    FLAT = auto()           # Все файлы в одну общую директорию


class FlatNumberingStyle(Enum):
    """Стиль нумерации треков для плоского списка."""
    KEEP_ALBUM_INDEX = auto()   # Сохранять исходный номер песни в альбоме
    CONTINUOUS_GLOBAL = auto()  # Сквозная нумерация 1..N по всему списку


class TranslitMode(Enum):
    """Режимы преобразования кириллицы и латиницы."""
    OFF = auto()
    CYRILLIC_TO_LATIN = auto()
    LATIN_TO_CYRILLIC = auto()