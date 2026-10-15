"""
Фоновые рабочие потоки (QThread) приложения.
Обеспечивают неблокирующее выполнение сканирования диска и экспорта с возможностью отмены.
"""
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from core.domain.models import Track
from core.interfaces.transcoder import EncodeSettings
from services.scanner_service import ScannerService
from services.export_service import ExportService


class ScanWorker(QThread):
    """Поток сканирования каталогов и файлов с индикацией прогресса."""
    scan_complete = Signal(list)
    progress = Signal(int, int, str)
    error = Signal(str)

    def __init__(self, scanner: ScannerService, source_paths: List[Path]):
        super().__init__()
        self._scanner = scanner
        self._paths = source_paths

    def run(self) -> None:
        try:
            def on_prog(curr: int, tot: int, name: str) -> None:
                self.progress.emit(curr, tot, name)

            tracks = self._scanner.scan_paths(self._paths, on_progress=on_prog)
            self.scan_complete.emit(tracks)
        except Exception as e:
            self.error.emit(str(e))


class ExportWorker(QThread):
    """Поток экспорта, конвертации и вшивания метаданных с поддержкой отмены."""
    progress = Signal(int, int, str)
    track_error = Signal(str, str)
    export_finished = Signal(int, int)

    def __init__(
        self,
        exporter: ExportService,
        tracks: List[Track],
        target_dir: Path,
        encode_settings: Optional[EncodeSettings] = None,
        sync_tags: bool = True,
        modify_source: bool = False
    ):
        super().__init__()
        self._exporter = exporter
        self._tracks = tracks
        self._target_dir = target_dir
        self._encode_settings = encode_settings
        self._sync_tags = sync_tags
        self._modify_source = modify_source
        self._is_cancelled = False
        self.success_count = 0
        self.error_count = 0

    # ПУНКТ 9: Метод отмены операции
    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        def on_prog(curr: int, tot: int, name: str) -> None:
            self.success_count += 1
            self.progress.emit(curr, tot, name)

        def on_err(track: Track, err: str) -> None:
            self.error_count += 1
            self.track_error.emit(track.source_path.name, err)

        self._exporter.execute_export(
            tracks=self._tracks,
            target_directory=self._target_dir,
            encode_settings=self._encode_settings,
            sync_tags=self._sync_tags,
            modify_source=self._modify_source,
            on_progress=on_prog,
            on_error=on_err,
            is_cancelled=lambda: self._is_cancelled
        )
        self.export_finished.emit(self.success_count, self.error_count)