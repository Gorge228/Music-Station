"""
Сервис сканирования директорий и создания доменных сущностей Track.
Поддерживает множественные пути, файлы и обратный вызов (on_progress) для индикации в UI.
"""
import os
import re
import logging
from pathlib import Path
from typing import List, Iterator, Callable, Optional, Set
from core.domain.models import Track
from core.domain.enums import AudioFormat
from core.interfaces.metadata import IMetadataReader
from core.interfaces.normalizer import ITrackNormalizer

logger = logging.getLogger("MusicFormator")


def natural_sort_key(s: str) -> list:
    """Ключ естественной сортировки: разбивает строку на текст и числа."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", str(s))]


class ScannerService:
    """Сервис обнаружения и первичной инициализации аудиофайлов."""

    def __init__(self, metadata_reader: IMetadataReader, normalizer: ITrackNormalizer):
        self._reader = metadata_reader
        self._normalizer = normalizer

    def scan_directory(
        self,
        root_path: Path,
        on_progress: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Track]:
        return self.scan_paths([root_path], on_progress=on_progress)

    # ПУНКТ 5 и 17: Сканирование произвольного набора файлов и каталогов
    def scan_paths(
        self,
        paths: List[Path],
        on_progress: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Track]:
        tracks: List[Track] = []
        candidate_files: Set[Path] = set()

        for p in paths:
            if not p.exists():
                continue
            if p.is_file():
                fmt = AudioFormat.from_extension(p.suffix)
                if fmt != AudioFormat.UNKNOWN and self._reader.supports(p):
                    candidate_files.add(p.resolve())
            elif p.is_dir():
                for file_path in self._find_audio_files(p):
                    fmt = AudioFormat.from_extension(file_path.suffix)
                    if fmt != AudioFormat.UNKNOWN and self._reader.supports(file_path):
                        candidate_files.add(file_path.resolve())

        audio_files = sorted(list(candidate_files), key=lambda p: natural_sort_key(str(p)))
        total = len(audio_files)

        if total == 0:
            return tracks

        for idx, file_path in enumerate(audio_files, start=1):
            if on_progress:
                on_progress(idx, total, file_path.name)

            fmt = AudioFormat.from_extension(file_path.suffix)
            try:
                size = file_path.stat().st_size
                metadata = self._reader.read(file_path)
            except (OSError, PermissionError) as e:
                logger.error(f"Ошибка доступа к файлу {file_path.name}: {e}")
                continue
            except Exception as e:
                logger.error(f"Не удалось прочитать метаданные файла {file_path.name}: {e}")
                continue

            title_candidate = metadata.title or file_path.stem

            base_title, feats, versions, is_karaoke = self._normalizer.extract_features(
                title=title_candidate,
                artist=metadata.artist
            )

            track = Track(
                source_path=file_path,
                file_format=fmt,
                file_size_bytes=size,
                metadata=metadata,
                normalized_title=base_title,
                detected_feats=feats,
                detected_version_tags=versions,
                is_karaoke=is_karaoke
            )
            tracks.append(track)

        return tracks

    def _find_audio_files(self, root_path: Path) -> Iterator[Path]:
        for root, _, files in os.walk(root_path):
            for file in files:
                yield Path(root) / file