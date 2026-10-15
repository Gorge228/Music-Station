"""
Сервис физического экспорта и реструктуризации фонотеки.
Выполняет копирование, прямое транскодирование и вшивание тегов без повреждения исходников.
"""
import shutil
import logging
from pathlib import Path
from typing import List, Callable, Optional
from core.domain.models import Track
from core.interfaces.metadata import IMetadataWriter
from core.interfaces.cover_art import ICoverArtHandler
from core.interfaces.transcoder import IAudioTranscoder, EncodeSettings

logger = logging.getLogger("MusicFormator")


class ExportService:
    """Координатор экспорта фонотеки с защитой структуры каталогов и обложек."""

    def __init__(
        self,
        metadata_writer: IMetadataWriter,
        cover_handler: Optional[ICoverArtHandler] = None,
        transcoder: Optional[IAudioTranscoder] = None
    ):
        self._writer = metadata_writer
        self._cover_handler = cover_handler
        self._transcoder = transcoder

    def execute_export(
        self,
        tracks: List[Track],
        target_directory: Path,
        encode_settings: Optional[EncodeSettings] = None,
        sync_tags: bool = True,
        encoding: str = "utf-8",
        modify_source: bool = False,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        on_error: Optional[Callable[[Track, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None
    ) -> None:
        active_tracks = [t for t in tracks if not t.is_excluded_from_export and t.target_relative_path]
        total = len(active_tracks)

        for index, track in enumerate(active_tracks, start=1):
            if is_cancelled and is_cancelled():
                logger.info("Экспорт прерван пользователем.")
                break

            # ПУНКТ 4: Защита структуры при изменении исходников
            if modify_source:
                # Если меняем исходники — обновляем файлы прямо в их текущих папках,
                # не создавая вложенных поддиректорий внутри альбома
                new_filename = track.target_relative_path.name
                target_path = track.source_path.parent / new_filename
            else:
                target_path = target_directory / track.target_relative_path

            needs_transcode = False
            if encode_settings is not None:
                fmt = encode_settings.target_format
                fmt_str = fmt.value if hasattr(fmt, "value") else str(fmt).lower().lstrip(".")
                ext = f".{fmt_str}"
                if fmt_str in ("alac", "aac"):
                    ext = ".m4a"
                target_path = target_path.with_suffix(ext)
                needs_transcode = True

            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)

                is_same_file = False
                try:
                    if target_path.exists() and target_path.resolve() == track.source_path.resolve():
                        is_same_file = True
                except (OSError, RuntimeError):
                    pass

                # Обложка: приоритет памяти (custom_cover_bytes) -> чтение с диска
                cover_to_apply: Optional[bytes] = None
                if getattr(track, "is_cover_deleted", False):
                    cover_to_apply = None
                elif getattr(track, "custom_cover_bytes", None) is not None:
                    cover_to_apply = track.custom_cover_bytes
                elif self._cover_handler:
                    try:
                        cover_to_apply = self._cover_handler.read_cover(track.source_path)
                    except Exception as e:
                        logger.warning(f"Не удалось прочитать обложку из {track.source_path.name}: {e}")

                old_source_dir = track.source_path.parent

                # 1. ПЕРЕКОДИРОВАНИЕ ЗВУКА
                if needs_transcode:
                    if not self._transcoder:
                        raise RuntimeError("Модуль FFmpeg транскодера не инициализирован.")

                    if is_same_file:
                        in_place_dest = target_path.with_name(f"{target_path.stem}_tmpconv{target_path.suffix}")
                        self._transcoder.transcode(track.source_path, in_place_dest, encode_settings)
                        track.source_path.unlink(missing_ok=True)
                        in_place_dest.rename(target_path)
                        track.source_path = target_path
                    else:
                        self._transcoder.transcode(track.source_path, target_path, encode_settings)
                        if modify_source:
                            track.source_path.unlink(missing_ok=True)
                            track.source_path = target_path
                            self._cleanup_empty_dirs(old_source_dir, stop_at=target_directory)

                # 2. БЕЗ ПЕРЕКОДИРОВАНИЯ (ПЕРЕМЕЩЕНИЕ / КОПИРОВАНИЕ)
                else:
                    if modify_source:
                        if not is_same_file:
                            shutil.move(str(track.source_path), str(target_path))
                            track.source_path = target_path
                            self._cleanup_empty_dirs(old_source_dir, stop_at=target_directory)
                    else:
                        if not is_same_file:
                            shutil.copy2(str(track.source_path), str(target_path))

                # 3. ВШИВАНИЕ ТЕГОВ И ОБЛОЖКИ
                if sync_tags:
                    self._apply_metadata(
                        path=target_path,
                        track=track,
                        encoding=encoding,
                        cover_bytes=cover_to_apply
                    )

                if on_progress:
                    on_progress(index, total, target_path.name)

            except Exception as e:
                logger.error(f"Ошибка при экспорте файла {track.source_path.name}: {e}")
                if on_error:
                    on_error(track, str(e))
                continue

    def _apply_metadata(
        self,
        path: Path,
        track: Track,
        encoding: str,
        cover_bytes: Optional[bytes]
    ) -> None:
        """Записывает метаданные и обложку напрямую в целевой файл."""
        meta_to_write = track.export_metadata or track.metadata
        self._writer.write(path, meta_to_write, encoding=encoding)

        if self._cover_handler:
            should_update = (
                cover_bytes is not None
                or getattr(track, "is_cover_deleted", False)
            )
            if should_update:
                try:
                    self._cover_handler.write_cover(path, cover_bytes)
                except Exception as e:
                    logger.warning(f"Не удалось внедрить обложку в {path.name}: {e}")

    @staticmethod
    def _cleanup_empty_dirs(start_dir: Path, stop_at: Path) -> None:
        """Рекурсивно удаляет пустые директории после переноса файлов, останавливаясь на stop_at."""
        try:
            curr = start_dir.resolve()
            stop = stop_at.resolve()
            while curr != stop and curr != curr.parent:
                if curr.exists() and not any(curr.iterdir()):
                    curr.rmdir()
                    curr = curr.parent
                else:
                    break
        except Exception:
            pass