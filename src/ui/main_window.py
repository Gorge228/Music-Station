"""
Главное окно приложения Music Formator (Composition Root).
Связывает сервисы фонотеки, пользовательский интерфейс и сохранение конфигурации.
"""
import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QSplitter,
    QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QDragEnterEvent, QDropEvent

from core.domain.models import Track
from core.domain.enums import DuplicateStatus, GroupingMode, FlatNumberingStyle, TranslitMode
from core.interfaces.settings_repository import ISettingsRepository
from infrastructure.settings.ini_settings_repository import IniSettingsRepository
from infrastructure.metadata.mutagen_adapter import MutagenMetadataHandler
from infrastructure.transcoder.ffmpeg_adapter import FFmpegTranscoder
from infrastructure.logger.logger_setup import setup_logger
from services.path_planner_service import PathPlannerService
from services.track_normalizer import TrackNormalizer
from services.transliteration_service import TransliterationService
from services.scanner_service import ScannerService
from services.deduplication_service import DeduplicationService
from services.export_service import ExportService
from services.history_service import HistoryService
from services.ai_exchange_service import AIExchangeService
from services.ai_export_service import AIListExporter

from ui.theme import DARK_QSS
from ui.widgets.top_bar import TopBar
from ui.widgets.bottom_bar import BottomBar
from ui.widgets.tracklist_view import TrackListWidget
from ui.panels.inspector_panel import InspectorPanel
from ui.panels.bottom_drawer import BottomDrawer
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.export_dialog import ExportDialog
from ui.workers import ScanWorker, ExportWorker

logger = setup_logger("MusicFormator")


class MainWindow(QMainWindow):
    """Главное окно управления библиотекой аудиотреков."""

    def __init__(
        self,
        settings_repo: ISettingsRepository,
        scanner: ScannerService,
        dedup: DeduplicationService,
        planner: PathPlannerService,
        exporter: ExportService,
        history: HistoryService,
        meta_handler: MutagenMetadataHandler
    ):
        super().__init__()
        self.setWindowTitle("Music Station")
        self.resize(1500, 880)

        # ПУНКТ 17: Включение Drag & Drop в главное окно
        self.setAcceptDrops(True)

        self._settings = settings_repo
        self._scanner = scanner
        self._dedup = dedup
        self._planner = planner
        self._exporter = exporter
        self._history = history
        self._meta_handler = meta_handler

        self.tracks: List[Track] = []
        self._manual_excluded_ids: set = set()
        self._is_inverted = False
        self._scan_worker: Optional[ScanWorker] = None
        self._export_worker: Optional[ExportWorker] = None

        self._init_ui()

        # ПУНКТ 18: Восстановление геометрии окна и положения сплиттера
        geo, spl = self._settings.load_window_state()
        if geo:
            self.restoreGeometry(geo)
        if spl:
            self.main_splitter.restoreState(spl)

        saved_trk_tpl, saved_alb_tpl = self._settings.load_custom_templates()
        self.inspector.p_format.set_custom_templates(saved_trk_tpl, saved_alb_tpl)

        self._wire_signals()
        self._setup_shortcuts()
        self.inspector.p_tags.set_cover_reader(self._meta_handler.read_cover)

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        self.top_bar = TopBar(self)
        root_layout.addWidget(self.top_bar)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.tracklist = TrackListWidget(self._settings, self)
        self.inspector = InspectorPanel(self._settings, self)

        self.main_splitter.addWidget(self.tracklist)
        self.main_splitter.addWidget(self.inspector)
        self.main_splitter.setSizes([750, 750])
        root_layout.addWidget(self.main_splitter, stretch=1)

        self.drawer = BottomDrawer(self)
        root_layout.addWidget(self.drawer)

        self.bottom_bar = BottomBar(self)
        root_layout.addWidget(self.bottom_bar)

    # ПУНКТ 17: Drag & Drop обработчики
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
            if paths:
                self._start_scan_paths(paths)
                event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence.Undo, self, self._on_undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._on_redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, self._on_redo)

        QShortcut(QKeySequence.Delete, self, self._on_shortcut_delete)
        QShortcut(QKeySequence("Backspace"), self, self._on_shortcut_delete)
        QShortcut(QKeySequence("Insert"), self, self._on_shortcut_restore)

        # Вызов обновленного диалога импорта по Ctrl+O
        QShortcut(QKeySequence.Open, self, self.top_bar._on_import_clicked)
        QShortcut(QKeySequence("Ctrl+E"), self, self._start_export)
        QShortcut(QKeySequence.Find, self, self.top_bar.focus_search)

        QShortcut(QKeySequence("Ctrl+P"), self, self._on_shortcut_toggle_preview)
        QShortcut(QKeySequence("Ctrl+H"), self, self._on_shortcut_toggle_excluded)
        QShortcut(QKeySequence("Ctrl+Tab"), self, self._toggle_layout_inversion)
        QShortcut(QKeySequence.Refresh, self, self._recalculate_and_refresh)

    def _wire_signals(self) -> None:
        # ПУНКТ 5: Прием списка путей (папок и файлов)
        self.top_bar.paths_selected.connect(self._start_scan_paths)
        self.top_bar.clear_requested.connect(self._clear_library)
        self.top_bar.undo_requested.connect(self._on_undo)
        self.top_bar.redo_requested.connect(self._on_redo)
        self.top_bar.reset_requested.connect(self._reset_changes)
        self.top_bar.search_changed.connect(self.tracklist.set_search_query)
        self.top_bar.invert_requested.connect(self._toggle_layout_inversion)
        self.top_bar.settings_requested.connect(self._open_settings_dialog)

        self.top_bar.preview_toggled.connect(self.tracklist.set_preview_enabled)
        self.top_bar.show_excluded_toggled.connect(self.tracklist.set_show_excluded)
        self.tracklist.preview_toggled.connect(self.top_bar.set_preview_checked)
        self.tracklist.show_excluded_toggled.connect(self.top_bar.set_show_excluded_checked)

        self.tracklist.selection_changed.connect(self._on_track_selected)
        self.tracklist.batch_tracks_toggled.connect(self._on_batch_tracks_toggled)
        self.tracklist.track_metadata_changed.connect(self._on_track_inline_edited)
        self.tracklist.album_transfer_committed.connect(self._on_album_transfer_committed)
        self.tracklist.album_artist_transfer_committed.connect(self._on_album_artist_transfer_committed)

        self.inspector.p_format.settings_changed.connect(self._on_formatting_settings_changed)
        self.inspector.p_format.apply_requested.connect(self._on_apply_formatting)
        self.inspector.p_tags.apply_tags_requested.connect(self._on_apply_tags)
        self.inspector.p_tags.renumber_requested.connect(self._on_renumber_requested)

        # ПУНКТ 9: Запуск и отмена экспорта
        self.bottom_bar.export_library_requested.connect(self._start_export)
        self.bottom_bar.cancel_export_requested.connect(self._on_cancel_export)
        self.bottom_bar.export_txt_requested.connect(self._on_export_txt_list)
        self.bottom_bar.export_ai_requested.connect(self._on_copy_ai_prompt)

    def _on_undo(self) -> None:
        if hasattr(self.tracklist, "cancel_all_pending_moves") and self.tracklist.cancel_all_pending_moves():
            self.bottom_bar.reset_status("✕ Перемещение отменено")
            return

        if not self._history.can_undo():
            self.bottom_bar.reset_status("История отменений пуста")
            return
        action = self._history.undo(self.tracks)
        self._recalculate_plan()
        self.tracklist.refresh_display()
        self.inspector.p_tags.set_library_context(self.tracks)
        selected = self.tracklist.get_selected_tracks()
        if selected:
            self.inspector.p_tags.set_track_data(selected)
        self.bottom_bar.reset_status(f"↺ Отменено: {action}")

    def _on_redo(self) -> None:
        if not self._history.can_redo():
            self.bottom_bar.reset_status("История повторений пуста")
            return
        action = self._history.redo(self.tracks)
        self._recalculate_plan()
        self.tracklist.refresh_display()
        self.inspector.p_tags.set_library_context(self.tracks)
        selected = self.tracklist.get_selected_tracks()
        if selected:
            self.inspector.p_tags.set_track_data(selected)
        self.bottom_bar.reset_status(f"↻ Повторено: {action}")

    def _on_shortcut_delete(self) -> None:
        tracks = self.tracklist.get_selected_tracks()
        if tracks:
            self._history.record_state(self.tracks, f"Исключение {len(tracks)} треков")
            self.tracklist.set_tracks_excluded_batch(tracks, True)

    def _on_shortcut_restore(self) -> None:
        tracks = self.tracklist.get_selected_tracks()
        if tracks:
            self._history.record_state(self.tracks, f"Восстановление {len(tracks)} треков")
            self.tracklist.set_tracks_excluded_batch(tracks, False)

    def _on_shortcut_toggle_preview(self) -> None:
        cur = self.tracklist.preview_enabled
        self.tracklist.set_preview_enabled(not cur)
        self.top_bar.set_preview_checked(not cur)

    def _on_shortcut_toggle_excluded(self) -> None:
        cur = self.tracklist.show_excluded
        self.tracklist.set_show_excluded(not cur)
        self.top_bar.set_show_excluded_checked(not cur)

    def _recalculate_and_refresh(self) -> None:
        self._recalculate_plan()
        self.tracklist.refresh_display()

    def _toggle_layout_inversion(self) -> None:
        sizes = self.main_splitter.sizes()
        w_left = self.main_splitter.widget(0)
        w_right = self.main_splitter.widget(1)
        w_left.setParent(None)
        w_right.setParent(None)

        if not self._is_inverted:
            self.main_splitter.addWidget(self.inspector)
            self.main_splitter.addWidget(self.tracklist)
            self._is_inverted = True
        else:
            self.main_splitter.addWidget(self.tracklist)
            self.main_splitter.addWidget(self.inspector)
            self._is_inverted = False

        self.main_splitter.setSizes(sizes)

    def _on_track_selected(self, selected_tracks: List[Track]) -> None:
        total_tracks = len(self.tracks)
        sel_count = len(selected_tracks)
        self.bottom_bar.update_track_counts(sel_count, total_tracks)

        if selected_tracks:
            self.inspector.p_tags.set_track_data(selected_tracks)
            self.inspector.p_debug.inspect_track(selected_tracks[0])

    def _on_batch_tracks_toggled(self, tracks: List[Track], state: bool) -> None:
        for t in tracks:
            if state:
                self._manual_excluded_ids.add(t.track_id)
            else:
                self._manual_excluded_ids.discard(t.track_id)
            t.is_excluded_from_export = state

        self._recalculate_plan()
        self.tracklist.refresh_display()
        status_word = "Исключено" if state else "Восстановлено"
        self.bottom_bar.reset_status(f"{status_word}: {len(tracks)} треков")

    def _on_track_inline_edited(self, track: Track, field_name: str, new_value: object) -> None:
        self._history.record_state(self.tracks, f"Правка {field_name}: {new_value}")
        setattr(track.metadata, field_name, new_value)

        if field_name == "title":
            base_t, feats, vers, is_kar = self._scanner._normalizer.extract_features(
                str(new_value), track.effective_artist
            )
            track.normalized_title = base_t
            track.detected_feats = feats
            track.detected_version_tags = vers
            track.is_karaoke = is_kar

        self.inspector.p_tags.update_live_field(track, field_name, new_value)
        self._recalculate_plan()
        self.tracklist.refresh_display()
        self.bottom_bar.reset_status(f"Обновлено {field_name} → {new_value}")

    def _on_album_transfer_committed(self, track: Track, new_album: str) -> None:
        self._history.record_state(self.tracks, f"Перенос трека в альбом '{new_album}'")
        track.metadata.album = new_album
        track.master_album = new_album
        self._recalculate_plan()
        self.tracklist.refresh_display()
        self.inspector.p_tags.set_library_context(self.tracks)
        self.bottom_bar.reset_status(f"Трек '{track.metadata.title}' перемещен в альбом '{new_album}'")

    def _on_album_artist_transfer_committed(self, track: Track, new_artist: str) -> None:
        self._history.record_state(self.tracks, f"Смена исп. альбома на '{new_artist}'")
        track.metadata.album_artist = new_artist
        self._recalculate_plan()
        self.tracklist.refresh_display()
        self.inspector.p_tags.set_library_context(self.tracks)
        self.bottom_bar.reset_status(f"Исполнитель альбома трека '{track.metadata.title}' изменён на '{new_artist}'")

    # ПУНКТ 5 и 17: Сканирование переданного набора путей
    def _start_scan_paths(self, paths: List[Path]) -> None:
        if not paths:
            return
        self._history.clear()
        self.bottom_bar.reset_status("Поиск файлов...")
        self.bottom_bar.progress_bar.setValue(0)

        # Вычисляем общий родительский каталог для выбранных папок/файлов
        try:
            import os
            if len(paths) == 1 and paths[0].is_dir():
                self._source_root = paths[0].resolve()
            else:
                resolved = [p.resolve() for p in paths]
                common = Path(os.path.commonpath([str(p) for p in resolved]))
                self._source_root = common if common.is_dir() else common.parent
        except Exception:
            self._source_root = paths[0].parent if paths[0].is_file() else paths[0]

        self._scan_worker = ScanWorker(self._scanner, paths)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.scan_complete.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_progress(self, curr: int, tot: int, name: str) -> None:
        self.bottom_bar.set_progress(curr, tot, f"Чтение тегов: {name}")

    def _on_scan_finished(self, tracks: List[Track]) -> None:
        self.tracks = tracks
        self._manual_excluded_ids.clear()
        for t in self.tracks:
            t.initial_metadata = t.metadata.clone()

        source_root = getattr(self, "_source_root", Path.cwd())
        subfolder_count = 0
        for t in self.tracks:
            try:
                rel = t.source_path.relative_to(source_root)
                if len(rel.parts) > 1:
                    subfolder_count += 1
            except ValueError:
                pass

        is_album_structure = subfolder_count > (len(self.tracks) / 2)
        self.inspector.p_format.set_detected_structure(is_album_structure)

        p = self.inspector.p_format
        self._dedup.process_library(
            self.tracks,
            merge_duplicate_albums=p.chk_merge_albums.isChecked(),
            merge_singles=p.chk_merge_singles.isChecked()
        )
        self._apply_smart_filters_state()

        self._recalculate_plan()
        self.tracklist.load_tracks(self.tracks)
        self.inspector.p_tags.set_library_context(self.tracks)
        self.bottom_bar.update_track_counts(0, len(tracks))
        self.bottom_bar.reset_status(f"Загружено треков: {len(tracks)}")


    def _on_scan_error(self, err_msg: str) -> None:
        self.bottom_bar.reset_status("Ошибка сканирования")
        self.drawer.log(f"Ошибка сканирования: {err_msg}")
        QMessageBox.critical(self, "Ошибка сканирования", f"Не удалось просканировать каталоги:\n{err_msg}")

    def _apply_smart_filters_state(self) -> None:
        p = self.inspector.p_format
        ex_dup = p.chk_excl_dup.isChecked()
        ex_remix = p.chk_excl_remix.isChecked()
        ex_feat = p.chk_excl_feat.isChecked()
        ex_karaoke = p.chk_excl_karaoke.isChecked()

        for t in self.tracks:
            if t.track_id in self._manual_excluded_ids:
                t.is_excluded_from_export = True
                continue

            auto_ex = False
            if ex_dup and t.duplicate_status == DuplicateStatus.DUPLICATE:
                auto_ex = True
            elif ex_remix and t.duplicate_status == DuplicateStatus.REMIX:
                auto_ex = True
            elif ex_feat and t.duplicate_status == DuplicateStatus.FEAT:
                auto_ex = True
            elif ex_karaoke and t.duplicate_status == DuplicateStatus.KARAOKE:
                auto_ex = True

            t.is_excluded_from_export = auto_ex

    def _on_formatting_settings_changed(self) -> None:
        if not self.tracks:
            return

        p = self.inspector.p_format
        self._dedup.process_library(
            self.tracks,
            merge_duplicate_albums=p.chk_merge_albums.isChecked(),
            merge_singles=p.chk_merge_singles.isChecked()
        )
        self._apply_smart_filters_state()

        selected = self.tracklist.get_selected_tracks()
        target = selected if selected else self.tracks
        self._execute_path_planning(target)
        self.tracklist.refresh_display()

    def _on_apply_formatting(self) -> None:
        if not self.tracks:
            return

        selected = self.tracklist.get_selected_tracks()
        target_tracks = selected if selected else self.tracks

        self._history.record_state(self.tracks, f"Форматирование ({len(target_tracks)} треков)")
        self._execute_path_planning(target_tracks)
        self.tracklist.refresh_display()
        self.bottom_bar.reset_status(f"✓ Отформатировано треков: {len(target_tracks)}")

    def _recalculate_plan(self) -> None:
        if not self.tracks:
            return
        self._execute_path_planning(self.tracks)

    def _execute_path_planning(self, target_tracks: List[Track]) -> None:
        p = self.inspector.p_format
        source_root = getattr(self, "_source_root", Path.cwd())

        grouping_modes = [
            GroupingMode.BY_METADATA,
            GroupingMode.FLAT_PLAYLIST,
            GroupingMode.FLAT
        ]
        grp_idx = min(p.combo_grouping.currentIndex(), len(grouping_modes) - 1)
        selected_mode = grouping_modes[grp_idx]

        self._planner.plan_paths_and_metadata(
            tracks=target_tracks,
            source_root=source_root,
            grouping_mode=selected_mode,
            track_template_str=p.get_selected_naming_template(),
            album_template_str=p.get_selected_album_template(),
            flat_numbering=FlatNumberingStyle.KEEP_ALBUM_INDEX,
            translit_mode=p.get_translit_mode(),
            translit_metadata=p.chk_translit_meta.isChecked(),
            clean_title_index=True,
            add_template_to_title=p.chk_num_in_title.isChecked(),
            strip_title_numbers=p.chk_strip_title_numbers.isChecked(),
            apply_template_to_album_tag=p.chk_apply_album_tag.isChecked(),
            clean_feats=p.chk_clean_feats.isChecked(),
            clear_lyrics=p.chk_clear_lyrics.isChecked(),
            clean_title_junk=True,
            embed_track_number=True,
            formatting_enabled=p.is_formatting_enabled()
        )

    def _on_apply_tags(self, tags_dict: dict, write_to_disk: bool) -> None:
        selected_tracks = self.tracklist.get_selected_tracks()
        if not selected_tracks:
            return

        self._history.record_state(self.tracks, f"Обновление тегов ({len(selected_tracks)} треков)")

        is_single = (len(selected_tracks) == 1)
        new_title = tags_dict.get("title")
        new_artist = tags_dict.get("artist")
        new_album_artist = tags_dict.get("album_artist")
        new_album = tags_dict.get("album")
        new_genre = tags_dict.get("genre")
        new_year = tags_dict.get("year")
        new_comment = tags_dict.get("comment")
        new_lyrics = tags_dict.get("lyrics")
        new_track_num = tags_dict.get("track_number")
        new_total_tracks = tags_dict.get("total_tracks")
        new_disc_num = tags_dict.get("disc_number")
        new_total_discs = tags_dict.get("total_discs")
        new_filename = tags_dict.get("filename")
        new_cover = tags_dict.get("cover")
        cover_deleted = tags_dict.get("cover_deleted", False)
        is_album_cover = tags_dict.get("is_album_cover", True)

        for t in selected_tracks:
            self.tracklist.cancel_pending_album_move(t)

            if is_single and new_title is not None:
                t.metadata.title = new_title
                base_t, feats, vers, is_kar = self._scanner._normalizer.extract_features(
                    str(new_title), t.effective_artist
                )
                t.normalized_title = base_t
                t.detected_feats = feats
                t.detected_version_tags = vers
                t.is_karaoke = is_kar

            if new_artist is not None:
                t.metadata.artist = new_artist
            if new_album_artist is not None:
                t.metadata.album_artist = new_album_artist
            if new_album is not None:
                t.metadata.album = new_album
                t.master_album = new_album
            if new_genre is not None:
                t.metadata.genre = new_genre
            if new_year is not None:
                t.metadata.year = new_year
            if new_comment is not None:
                t.metadata.comment = new_comment
            if is_single and new_lyrics is not None:
                t.metadata.lyrics = new_lyrics
            if is_single and new_track_num is not None:
                t.metadata.track_number = new_track_num
            if new_total_tracks is not None:
                t.metadata.total_tracks = new_total_tracks
            if new_disc_num is not None:
                t.metadata.disc_number = new_disc_num
            if new_total_discs is not None:
                t.metadata.total_discs = new_total_discs

            if is_single and new_filename:
                t.set_custom_filename(new_filename)
                if write_to_disk and t.source_path.name != t.custom_filename:
                    try:
                        import os
                        new_source = t.source_path.with_name(t.custom_filename)
                        os.replace(str(t.source_path), str(new_source))
                        t.source_path = new_source
                    except Exception as e:
                        self.drawer.log(f"Ошибка переименования на диске: {e}")

            if write_to_disk:
                try:
                    self._meta_handler.write(t.source_path, t.metadata)
                except Exception as e:
                    self.drawer.log(f"Ошибка записи метаданных в {t.source_path.name}: {e}")

        if new_cover is not None or cover_deleted:
            targets = set(selected_tracks)
            if is_album_cover and selected_tracks:
                first_t = selected_tracks[0]
                ref_alb = (new_album or first_t.master_album or first_t.effective_album).strip().lower()
                for t in self.tracks:
                    if (t.master_album or t.effective_album).strip().lower() == ref_alb:
                        targets.add(t)

            for t in targets:
                t.custom_cover_bytes = None if cover_deleted else new_cover
                t.is_cover_deleted = cover_deleted

                if write_to_disk:
                    try:
                        self._meta_handler.write_cover(t.source_path, None if cover_deleted else new_cover)
                    except Exception as e:
                        self.drawer.log(f"Ошибка сохранения обложки для {t.source_path.name}: {e}")

            self.inspector.p_tags.refresh_cover_cache(self.tracks, self._meta_handler.read_cover)

        self._recalculate_plan()
        self.tracklist.refresh_display()
        self.inspector.p_tags.set_track_data(selected_tracks)
        self.bottom_bar.reset_status(f"✓ Метаданные обновлены ({len(selected_tracks)} треков)")

    def _on_renumber_requested(self, tracks: List[Track], write_to_disk: bool) -> None:
        if not tracks:
            return

        self._history.record_state(self.tracks, f"Обновление нумерации ({len(tracks)} треков)")

        sorted_tracks = sorted(tracks, key=lambda t: (
            t.metadata.track_number or 999,
            t.source_path.name
        ))
        total = len(sorted_tracks)

        for idx, t in enumerate(sorted_tracks, start=1):
            t.metadata.track_number = idx
            t.metadata.total_tracks = total
            if t.export_metadata:
                t.export_metadata.track_number = idx
                t.export_metadata.total_tracks = total

            if write_to_disk:
                try:
                    self._meta_handler.write(t.source_path, t.metadata)
                except Exception as e:
                    self.drawer.log(f"Ошибка записи номера трека в {t.source_path.name}: {e}")

        self._recalculate_plan()
        self.tracklist.refresh_display()
        selected = self.tracklist.get_selected_tracks() or tracks
        self.inspector.p_tags.set_track_data(selected)
        self.bottom_bar.reset_status(f"✓ Нумерация альбома обновлена (1..{total})")

    # ПУНКТ 9: Старт экспорта с переключением кнопки на «Отмена»
    def _start_export(self) -> None:
        if not self.tracks:
            QMessageBox.warning(self, "Экспорт", "Фонотека пуста. Сначала откройте каталог с музыкой.")
            return

        active_tracks = [t for t in self.tracks if not t.is_excluded_from_export]
        if not active_tracks:
            QMessageBox.warning(self, "Экспорт", "Все треки исключены из плана экспорта.")
            return

        source_root = getattr(self, "_source_root", Path.cwd())
        dlg = ExportDialog(
            settings_repo=self._settings,
            parent=self,
            source_root=source_root,
            active_count=len(active_tracks),
            excluded_count=len(self.tracks) - len(active_tracks)
        )
        if not dlg.exec():
            return

        target_dir = dlg.get_target_path()
        modify_source = dlg.is_modify_source()
        encode_settings = self.inspector.p_converter.get_encode_settings()

        # Меняем кнопку на «⛔ Отмена»
        self.bottom_bar.set_exporting_state(True)
        self.bottom_bar.reset_status("Подготовка к экспорту...")

        self._export_worker = ExportWorker(
            exporter=self._exporter,
            tracks=active_tracks,
            target_dir=target_dir,
            encode_settings=encode_settings,
            sync_tags=True,
            modify_source=modify_source
        )

        def on_export_prog(curr: int, tot: int, name: str) -> None:
            self.bottom_bar.set_progress(curr, tot, f"Экспорт: {name}")

        def on_export_done(success_cnt: int, err_cnt: int) -> None:
            # Возвращаем кнопку в исходное состояние «🚀 Экспорт»
            self.bottom_bar.set_exporting_state(False)
            self.bottom_bar.reset_status("Экспорт завершён")
            msg = f"Экспорт завершён!\n\nУспешно экспортировано: {success_cnt} треков."
            if err_cnt > 0:
                msg += f"\nОшибок: {err_cnt} (см. консоль операций)."
            QMessageBox.information(self, "Экспорт завершён", msg)
            if modify_source:
                self._recalculate_plan()
                self.tracklist.refresh_display()

        def on_export_err(track_name: str, err: str) -> None:
            self.drawer.log(f"Ошибка экспорта {track_name}: {err}")

        self._export_worker.progress.connect(on_export_prog)
        self._export_worker.export_finished.connect(on_export_done)
        self._export_worker.track_error.connect(on_export_err)
        self._export_worker.start()

    # ПУНКТ 9: Прерывание экспорта
    def _on_cancel_export(self) -> None:
        if self._export_worker and self._export_worker.isRunning():
            self._export_worker.cancel()
            self.bottom_bar.reset_status("Прерывание экспорта...")

    def _on_export_txt_list(self) -> None:
        if not self.tracks:
            QMessageBox.warning(self, "Экспорт списка", "Фонотека пуста.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить треклист", "Tracklist.txt", "Текстовые файлы (*.txt)"
        )
        if file_path:
            try:
                AIListExporter.generate_prompt_list(self.tracks, Path(file_path))
                QMessageBox.information(self, "Экспорт списка", "Треклист успешно сохранен.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить треклист:\n{e}")

    def _on_copy_ai_prompt(self) -> None:
        if not self.tracks:
            QMessageBox.warning(self, "ИИ-аудит", "Фонотека пуста.")
            return

        source_root = getattr(self, "_source_root", Path.cwd())
        folder_name = source_root.name or "Music"
        payload = AIExchangeService.generate_prompt_payload(self.tracks, folder_name)
        QApplication.clipboard().setText(payload)
        self.bottom_bar.reset_status("Промпт для ИИ скопирован в буфер обмена")
        QMessageBox.information(
            self,
            "ИИ-аудит",
            "Промпт аудита фонотеки скопирован в буфер обмена!\n\nВставьте его в диалог с нейросетью."
        )

    def _clear_library(self) -> None:
        self._history.clear()
        self.tracks.clear()
        self.tracklist.load_tracks([])
        self.inspector.p_tags.set_track_data([])
        self.bottom_bar.reset_status("Фонотека очищена")

    def _reset_changes(self) -> None:
        if not self.tracks:
            return

        if hasattr(self.tracklist, "cancel_all_pending_moves"):
            self.tracklist.cancel_all_pending_moves()

        self._manual_excluded_ids.clear()
        self._history.record_state(self.tracks, "Сброс изменений к исходным")

        for t in self.tracks:
            if hasattr(t, "initial_metadata") and t.initial_metadata:
                t.metadata = t.initial_metadata.clone()
            t.master_album = ""
            t.target_relative_path = None
            t.export_metadata = None
            t.custom_filename = None
            t.custom_cover_bytes = None
            t.is_cover_deleted = False

        p = self.inspector.p_format
        self._dedup.process_library(
            self.tracks,
            merge_duplicate_albums=p.chk_merge_albums.isChecked(),
            merge_singles=p.chk_merge_singles.isChecked()
        )
        self._apply_smart_filters_state()
        self._recalculate_plan()

        self.tracklist.refresh_display()
        self.inspector.p_tags.set_library_context(self.tracks)
        selected = self.tracklist.get_selected_tracks()
        if selected:
            self.inspector.p_tags.set_track_data(selected)
        self.bottom_bar.reset_status("Все изменения фонотеки сброшены к исходным")

    def _open_settings_dialog(self) -> None:
        dlg = SettingsDialog(self)
        dlg.exec()

    # ПУНКТ 18: Сохранение геометрии окна и разделителей при закрытии
    def closeEvent(self, event) -> None:
        self._settings.save_window_state(
            bytes(self.saveGeometry()),
            bytes(self.main_splitter.saveState())
        )
        p = self.inspector.p_format
        tr_save, alb_save = p.get_custom_templates_for_save()
        self._settings.save_custom_templates(tr_save, alb_save)
        self.tracklist.save_column_settings()
        self.inspector._save_state()
        super().closeEvent(event)


def run_app() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)

    settings_repo = IniSettingsRepository()
    meta_handler = MutagenMetadataHandler()
    transcoder = FFmpegTranscoder()

    normalizer = TrackNormalizer()
    translit = TransliterationService()
    scanner = ScannerService(metadata_reader=meta_handler, normalizer=normalizer)
    dedup = DeduplicationService(normalizer=normalizer)
    planner = PathPlannerService(translit_service=translit, normalizer=normalizer)
    exporter = ExportService(
        metadata_writer=meta_handler,
        cover_handler=meta_handler,
        transcoder=transcoder
    )
    history = HistoryService(max_depth=50)

    window = MainWindow(
        settings_repo=settings_repo,
        scanner=scanner,
        dedup=dedup,
        planner=planner,
        exporter=exporter,
        history=history,
        meta_handler=meta_handler
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()