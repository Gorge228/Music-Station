# services/tag_editor_service.py
"""Сервис пакетного изменения метаданных и парсинга тегов из файловых масок."""
import re
from typing import List, Optional
from core.domain.models import Track, AudioMetadata
import logging

logger = logging.getLogger("MusicFormator")


class TagEditorService:
    @staticmethod
    def batch_update_metadata(
            tracks: List[Track],
            artist: Optional[str] = None,
            album: Optional[str] = None,
            year: Optional[int] = None,
            genre: Optional[str] = None
    ) -> None:
        """Пакетное обновление метаданных в оперативной памяти."""
        for track in tracks:
            if artist is not None:
                track.metadata.artist = artist
                track.metadata.album_artist = artist
            if album is not None:
                track.metadata.album = album
            if year is not None:
                track.metadata.year = year
            if genre is not None:
                track.metadata.genre = genre

    @staticmethod
    def parse_tags_from_filename(filename_stem: str, pattern: str) -> AudioMetadata:
        """Автоматическое извлечение метаданных по шаблону (например, '{artist} - {title}')."""
        regex_pattern = re.escape(pattern)
        regex_pattern = regex_pattern.replace(r'\{artist\}', r'(?P<artist>.+)')
        regex_pattern = regex_pattern.replace(r'\{title\}', r'(?P<title>.+)')
        regex_pattern = regex_pattern.replace(r'\{album\}', r'(?P<album>.+)')
        regex_pattern = regex_pattern.replace(r'\{track_number\}', r'(?P<track_number>\d+)')
        regex_pattern = regex_pattern.replace(r'\{year\}', r'(?P<year>\d{4})')
        regex_pattern = f"^{regex_pattern}$"

        match = re.match(regex_pattern, filename_stem)
        meta = AudioMetadata()
        if match:
            group_dict = match.groupdict()
            meta.artist = group_dict.get('artist', '').strip()
            meta.title = group_dict.get('title', '').strip()
            meta.album = group_dict.get('album', '').strip()
            if 'track_number' in group_dict:
                meta.track_number = int(group_dict['track_number'])
            if 'year' in group_dict:
                meta.year = int(group_dict['year'])
        return meta