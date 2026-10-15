"""
Интерактивный виджет отображения треклиста фонотеки.
Поддерживает группировку по исполнителям и альбомам, нестрогий поиск и пакетные операции.
"""
import time
import re
from typing import List, Dict, Optional, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QToolButton, QMenu, QAbstractItemView, QStyle, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QPoint, QEvent, QRectF, QTimer
from PySide6.QtGui import QAction, QPainter, QColor, QBrush, QPen, QFont, QFontMetrics, QKeySequence

from core.domain.models import Track
from core.domain.enums import DuplicateStatus
from core.interfaces.settings_repository import ISettingsRepository
from ui.theme import STATUS_COLORS
from ui.widgets.track_editor_delegate import TrackEditorDelegate


def _normalize_text(s: str) -> str:
    if not s:
        return ""
    cleaned = str(s).lower().replace("ё", "е")
    cleaned = re.sub(r'[\-_.,;:!?()\[\]{}"\'\\/]', " ", cleaned)
    return " ".join(cleaned.split())


class CustomTreeWidget(QTreeWidget):
    """Кастомное дерево с ручным рендерингом плашек исполнителей и альбомов."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

    def drawRow(self, painter: QPainter, option, index) -> None:
        item = self.itemFromIndex(index)
        if not item:
            super().drawRow(painter, option, index)
            return

        item_type = item.data(0, Qt.UserRole + 1)
        if item_type == "ARTIST_HEADER":
            self._paint_artist_banner(painter, option, item, index)
            return
        if item_type == "ALBUM_HEADER":
            self._paint_album_banner(painter, option, item, index)
            return
        if item_type in ("ARTIST_SPACER", "ALBUM_SPACER"):
            return

        super().drawRow(painter, option, index)

    def _paint_artist_banner(self, painter: QPainter, option, item: QTreeWidgetItem, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        is_selected = (
            item.isSelected()
            or bool(option.state & QStyle.State_Selected)
            or (self.selectionModel() is not None and self.selectionModel().isRowSelected(index.row(), index.parent()))
        )

        artist_name = item.data(0, Qt.UserRole + 10) or "Неизвестный исполнитель"
        count_str = f"[{item.data(0, Qt.UserRole + 11) or ''}]"
        is_all_excluded = item.data(0, Qt.UserRole + 3) is True

        arrow_str = "▼ " if item.isExpanded() else "▶ "
        full_title_text = f"{arrow_str}{artist_name}"
        badge_text = "ИСПОЛНИТЕЛЬ"

        f_badge = QFont(self.font())
        f_badge.setBold(True)
        f_badge.setPointSize(9)
        f_badge.setStrikeOut(is_all_excluded)

        f_title = QFont(self.font())
        f_title.setBold(True)
        f_title.setPointSize(11)
        f_title.setStrikeOut(is_all_excluded)

        f_count = QFont(self.font())
        f_count.setPointSize(9)
        f_count.setStrikeOut(is_all_excluded)

        badge_w = QFontMetrics(f_badge).horizontalAdvance(badge_text) + 18
        title_w = QFontMetrics(f_title).horizontalAdvance(full_title_text)
        count_w = QFontMetrics(f_count).horizontalAdvance(count_str)

        card_w = min(badge_w + title_w + count_w + 40, option.rect.width() - 8)
        card_rect = QRectF(4, option.rect.y() + 2, card_w, option.rect.height() - 4)

        bg_color = QColor("#1D2432" if is_selected else "#181B22")
        border_pen = QPen(QColor("#3B82F6" if is_selected else "#4F46E5"), 1.3)

        painter.setBrush(QBrush(bg_color))
        painter.setPen(border_pen)
        painter.drawRoundedRect(card_rect, 5, 5)

        badge_rect = QRectF(card_rect.x() + 6, card_rect.y() + 4, badge_w, card_rect.height() - 8)
        badge_color = QColor("#6366F1")
        fill_b = QColor(badge_color)
        fill_b.setAlpha(60 if is_selected else 40)
        painter.setBrush(QBrush(fill_b))
        painter.setPen(QPen(badge_color, 1))
        painter.drawRoundedRect(badge_rect, 3, 3)

        painter.setFont(f_badge)
        painter.setPen(badge_color.lighter(130))
        painter.drawText(badge_rect, Qt.AlignCenter, badge_text)

        title_rect = QRectF(badge_rect.right() + 10, card_rect.y(), title_w, card_rect.height())
        painter.setPen(QColor("#FFFFFF") if not is_all_excluded else QColor("#818D9D"))
        painter.setFont(f_title)
        painter.drawText(title_rect, Qt.AlignVCenter | Qt.AlignLeft, full_title_text)

        count_rect = QRectF(title_rect.right() + 10, card_rect.y(), count_w + 10, card_rect.height())
        painter.setPen(QColor("#60A5FA" if is_selected else "#9CA3AF"))
        painter.setFont(f_count)
        painter.drawText(count_rect, Qt.AlignVCenter | Qt.AlignLeft, count_str)

        painter.restore()

    def _paint_album_banner(self, painter: QPainter, option, item: QTreeWidgetItem, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        is_selected = (
            item.isSelected()
            or bool(option.state & QStyle.State_Selected)
            or (self.selectionModel() is not None and self.selectionModel().isRowSelected(index.row(), index.parent()))
        )

        status = item.data(0, Qt.UserRole + 2) or DuplicateStatus.ORIGINAL
        is_album_excluded = item.data(0, Qt.UserRole + 3) is True
        title_text = item.data(0, Qt.UserRole + 10) or ""
        count_str = f"[{item.data(0, Qt.UserRole + 11) or ''}]"

        status_color = QColor("#4B5260" if is_album_excluded else STATUS_COLORS.get(status, "#7F8C8D"))
        arrow_str = "▼ " if item.isExpanded() else "▶ "
        full_title_text = f"{arrow_str}{title_text}"

        f_badge = QFont(self.font())
        f_badge.setBold(True)
        f_badge.setPointSize(9)
        f_badge.setStrikeOut(is_album_excluded)

        f_title = QFont(self.font())
        f_title.setBold(True)
        f_title.setPointSize(10)
        f_title.setStrikeOut(is_album_excluded)

        f_count = QFont(self.font())
        f_count.setPointSize(9)
        f_count.setStrikeOut(is_album_excluded)

        badge_w = QFontMetrics(f_badge).horizontalAdvance(status.name) + 16
        title_w = QFontMetrics(f_title).horizontalAdvance(full_title_text)
        count_w = QFontMetrics(f_count).horizontalAdvance(count_str)

        card_w = min(badge_w + title_w + count_w + 36, option.rect.width() - 24)
        card_rect = QRectF(16, option.rect.y() + 2, card_w, option.rect.height() - 4)

        bg_color = QColor("#1D2432" if is_selected else ("#181A1F" if is_album_excluded else "#1F2229"))
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(QColor("#3B82F6" if is_selected else status_color), 1.2))
        painter.drawRoundedRect(card_rect, 4, 4)

        badge_rect = QRectF(card_rect.x() + 6, card_rect.y() + 3, badge_w, card_rect.height() - 6)
        fill_badge = QColor(status_color)
        fill_badge.setAlpha(60 if is_selected else 40)
        painter.setBrush(QBrush(fill_badge))
        painter.setPen(QPen(status_color, 1))
        painter.drawRoundedRect(badge_rect, 3, 3)

        painter.setFont(f_badge)
        painter.setPen(status_color.lighter(130))
        painter.drawText(badge_rect, Qt.AlignCenter, status.name)

        title_rect = QRectF(badge_rect.right() + 8, card_rect.y(), title_w, card_rect.height())
        painter.setPen(QColor("#FFFFFF") if not is_album_excluded else QColor("#94A3B8"))
        painter.setFont(f_title)
        painter.drawText(title_rect, Qt.AlignVCenter | Qt.AlignLeft, full_title_text)

        count_rect = QRectF(title_rect.right() + 8, card_rect.y(), count_w + 10, card_rect.height())
        painter.setPen(QColor("#60A5FA" if is_selected else "#8C929D"))
        painter.setFont(f_count)
        painter.drawText(count_rect, Qt.AlignVCenter | Qt.AlignLeft, count_str)

        painter.restore()

    def mousePressEvent(self, event) -> None:
        pos = event.pos()
        item = self.itemAt(pos)
        if item and item.data(0, Qt.UserRole + 1) == "TRACK":
            col = self.columnAt(pos.x())
            track: Optional[Track] = item.data(0, Qt.UserRole)
            p = self.parent()

            if track and hasattr(p, "delegate"):
                if col == 7 and track.track_id in p.delegate.pending_album_moves:
                    p.cancel_pending_album_move(track)
                    super().mousePressEvent(event)
                    return
                elif col == 8 and track.track_id in p.delegate.pending_artist_moves:
                    p.cancel_pending_artist_move(track)
                    super().mousePressEvent(event)
                    return

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        pos = event.pos()
        item = self.itemAt(pos)
        if item:
            item_type = item.data(0, Qt.UserRole + 1)
            if item_type in ("ARTIST_HEADER", "ALBUM_HEADER") and event.button() == Qt.LeftButton:
                item.setExpanded(not item.isExpanded())
                self.viewport().update()
                event.accept()
                return

            if item_type == "TRACK" and event.button() == Qt.LeftButton:
                col = self.columnAt(pos.x())
                track: Optional[Track] = item.data(0, Qt.UserRole)
                p = self.parent()

                if col == 0 and track and hasattr(p, "toggle_single_track_exclusion"):
                    p.toggle_single_track_exclusion(track)
                    event.accept()
                    return

                if col == 7 and track:
                    if hasattr(p, "delegate") and track.track_id in p.delegate.pending_album_moves:
                        p.cancel_pending_album_move(track)
                    self.editItem(item, 7)
                    event.accept()
                    return

                if col == 8 and track:
                    if hasattr(p, "delegate") and track.track_id in p.delegate.pending_artist_moves:
                        p.cancel_pending_artist_move(track)
                    self.editItem(item, 8)
                    event.accept()
                    return

        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:
        pos = event.pos()
        item = self.itemAt(pos)
        if item and item.data(0, Qt.UserRole + 1) == "TRACK":
            col = self.columnAt(pos.x())
            track = item.data(0, Qt.UserRole)
            p = self.parent()
            if track and hasattr(p, "delegate"):
                if col == 7 and track.track_id in p.delegate.pending_album_moves:
                    self.viewport().setCursor(Qt.PointingHandCursor)
                    super().mouseMoveEvent(event)
                    return
                elif col == 8 and track.track_id in p.delegate.pending_artist_moves:
                    self.viewport().setCursor(Qt.PointingHandCursor)
                    super().mouseMoveEvent(event)
                    return
        self.viewport().unsetCursor()
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            selected = self.get_selected_tracks()
            if selected:
                self.set_tracks_excluded_batch(selected, True)
                event.accept()
                return
        elif event.key() == Qt.Key_Insert:
            selected = self.get_selected_tracks()
            if selected:
                self.set_tracks_excluded_batch(selected, False)
                event.accept()
                return
        super().keyPressEvent(event)


class TrackListWidget(QWidget):
    """Виджет отображения и навигации по дискографии."""
    selection_changed = Signal(list)
    batch_tracks_toggled = Signal(list, bool)
    preview_toggled = Signal(bool)
    show_excluded_toggled = Signal(bool)
    track_metadata_changed = Signal(Track, str, object)
    album_transfer_committed = Signal(Track, str)
    album_artist_transfer_committed = Signal(Track, str)

    COLUMNS_DEF = [
        ("СТАТУС", 0, True),
        ("№", 1, True),
        ("НАЗВАНИЕ ТРЕКА", 2, True),
        ("ГОД", 3, True),
        ("ЖАНР", 4, True),
        ("ИМЯ ФАЙЛА", 5, False),
        ("ИСПОЛНИТЕЛЬ", 6, True),
        ("АЛЬБОМ", 7, True),
        ("АЛЬБОМНЫЙ ИСП.", 8, False),
    ]

    def __init__(self, settings_repo: ISettingsRepository, parent=None):
        super().__init__(parent)
        self._settings = settings_repo
        self.preview_enabled: bool = True
        self.show_excluded: bool = True
        self._tracks: List[Track] = []
        self._search_tokens: List[str] = []

        self._sort_col = 1
        self._sort_order = Qt.AscendingOrder
        self._is_restoring = False

        self._is_editing: bool = False
        self._pending_refresh: bool = False

        self._init_ui()
        self._setup_album_timer()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tree = CustomTreeWidget(self)
        self.tree.setColumnCount(len(self.COLUMNS_DEF))
        self.tree.setHeaderLabels([name for name, _, _ in self.COLUMNS_DEF])

        self.delegate = TrackEditorDelegate(self)
        self.delegate.track_edited.connect(self._on_track_field_edited)
        self.delegate.album_change_requested.connect(self._start_album_transfer_timer)
        self.delegate.album_artist_change_requested.connect(self._start_artist_transfer_timer)
        self.delegate.editor_opened.connect(self._on_editor_opened)
        self.delegate.editor_closed.connect(self._on_editor_closed)

        self.tree.setItemDelegate(self.delegate)

        header = self.tree.header()
        header.setSectionsMovable(True)
        header.setStretchLastSection(False)
        self.tree.setSortingEnabled(False)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self._sort_col, self._sort_order)

        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree.setIndentation(0)
        self.tree.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._open_tree_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

        for _, idx, _ in self.COLUMNS_DEF:
            header.setSectionResizeMode(idx, QHeaderView.Interactive)

        header.resizeSection(0, 85)
        header.resizeSection(1, 50)
        header.resizeSection(2, 240)
        header.resizeSection(3, 60)
        header.resizeSection(4, 95)
        header.resizeSection(5, 160)
        header.resizeSection(6, 140)
        header.resizeSection(7, 180)
        header.resizeSection(8, 140)

        for _, idx, is_default in self.COLUMNS_DEF:
            if not is_default:
                self.tree.setColumnHidden(idx, True)

        self.restore_column_settings()
        header.sectionClicked.connect(self._on_header_section_clicked)
        header.sectionResized.connect(self._on_column_layout_changed)
        header.sectionMoved.connect(self._on_column_layout_changed)

        layout.addWidget(self.tree)

        self.btn_gear = QToolButton(header)
        self.btn_gear.setText("⚙")
        self.btn_gear.setToolTip("Настройка отображаемых колонок")
        self.btn_gear.setCursor(Qt.PointingHandCursor)
        self.btn_gear.clicked.connect(self._show_column_chooser_menu)
        header.installEventFilter(self)

    def save_column_settings(self) -> None:
        if self._is_restoring:
            return
        widths = {idx: self.tree.header().sectionSize(idx) for _, idx, _ in self.COLUMNS_DEF}
        hidden = {idx: self.tree.isColumnHidden(idx) for _, idx, _ in self.COLUMNS_DEF}
        sort_val = self._sort_order.value if hasattr(self._sort_order, "value") else int(self._sort_order)
        self._settings.save_tracklist_columns(widths, hidden, self._sort_col, sort_val)

    def restore_column_settings(self) -> None:
        self._is_restoring = True
        data = self._settings.load_tracklist_columns()
        if not data:
            self._is_restoring = False
            return

        for col_idx, is_hidden in data.get("hidden", {}).items():
            self.tree.setColumnHidden(col_idx, is_hidden)

        for col_idx, width in data.get("widths", {}).items():
            if width > 15:
                self.tree.header().resizeSection(col_idx, width)

        saved_sort_col = data.get("sort_col")
        saved_sort_order = data.get("sort_order")
        if saved_sort_col is not None:
            try:
                self._sort_col = int(saved_sort_col)
                self._sort_order = Qt.SortOrder(int(saved_sort_order))
                self.tree.header().setSortIndicator(self._sort_col, self._sort_order)
            except Exception:
                pass

        self._is_restoring = False

    def set_search_query(self, query: str) -> None:
        cleaned = _normalize_text(query)
        self._search_tokens = cleaned.split() if cleaned else []
        self.refresh_display()

    def _matches_search(self, t: Track, meta) -> bool:
        if not self._search_tokens:
            return True

        corpus_parts = [
            meta.title,
            t.source_path.stem,
            t.source_path.name,
            t.normalized_title,
            meta.artist,
            meta.album_artist,
            t.effective_artist,
            meta.album,
            t.effective_album,
            meta.genre,
            str(meta.year or ""),
            meta.comment,
            " ".join(t.detected_feats),
            " ".join(t.detected_version_tags)
        ]
        normalized_corpus = _normalize_text(" ".join(filter(None, corpus_parts)))

        for token in self._search_tokens:
            if token not in normalized_corpus:
                return False
        return True

    def _setup_album_timer(self) -> None:
        self.album_anim_timer = QTimer(self)
        self.album_anim_timer.setInterval(100)
        self.album_anim_timer.timeout.connect(self._on_album_timer_tick)

    def _start_album_transfer_timer(self, track: Track, target_album: str) -> None:
        self.delegate.pending_album_moves[track.track_id] = {
            "track": track,
            "target_album": target_album,
            "orig_album": track.effective_album,
            "start_time": time.time(),
            "duration": 5.0
        }
        if not self.album_anim_timer.isActive():
            self.album_anim_timer.start()
        self.tree.viewport().update()

    def _start_artist_transfer_timer(self, track: Track, target_artist: str) -> None:
        self.delegate.pending_artist_moves[track.track_id] = {
            "track": track,
            "target_artist": target_artist,
            "orig_artist": track.metadata.album_artist or track.effective_artist,
            "start_time": time.time(),
            "duration": 5.0
        }
        if not self.album_anim_timer.isActive():
            self.album_anim_timer.start()
        self.tree.viewport().update()

    def cancel_pending_album_move(self, track: Track) -> bool:
        if track and track.track_id in self.delegate.pending_album_moves:
            del self.delegate.pending_album_moves[track.track_id]
            if not self.has_pending_moves() and self.album_anim_timer.isActive():
                self.album_anim_timer.stop()
            self.tree.viewport().update()
            return True
        return False

    def cancel_pending_artist_move(self, track: Track) -> bool:
        if track and track.track_id in self.delegate.pending_artist_moves:
            del self.delegate.pending_artist_moves[track.track_id]
            if not self.has_pending_moves() and self.album_anim_timer.isActive():
                self.album_anim_timer.stop()
            self.tree.viewport().update()
            return True
        return False

    def cancel_all_pending_moves(self) -> bool:
        had_moves = bool(self.delegate.pending_album_moves or self.delegate.pending_artist_moves)
        self.delegate.pending_album_moves.clear()
        self.delegate.pending_artist_moves.clear()
        if self.album_anim_timer.isActive():
            self.album_anim_timer.stop()
        self.tree.viewport().update()
        return had_moves

    def has_pending_moves(self) -> bool:
        return bool(self.delegate.pending_album_moves or self.delegate.pending_artist_moves)

    def _on_column_layout_changed(self, *args) -> None:
        self.save_column_settings()

    def _on_editor_opened(self, *args) -> None:
        self._is_editing = True

    def _on_editor_closed(self, *args) -> None:
        self._is_editing = False
        if self._pending_refresh:
            self._pending_refresh = False
            QTimer.singleShot(30, self.refresh_display)

    def _on_album_timer_tick(self) -> None:
        now = time.time()
        completed_albums = []
        completed_artists = []

        for track_id, info in list(self.delegate.pending_album_moves.items()):
            if (now - info["start_time"]) >= info["duration"]:
                completed_albums.append(track_id)

        for track_id, info in list(self.delegate.pending_artist_moves.items()):
            if (now - info["start_time"]) >= info["duration"]:
                completed_artists.append(track_id)

        for track_id in completed_albums:
            info = self.delegate.pending_album_moves.pop(track_id)
            self.album_transfer_committed.emit(info["track"], info["target_album"])

        for track_id in completed_artists:
            info = self.delegate.pending_artist_moves.pop(track_id)
            self.album_artist_transfer_committed.emit(info["track"], info["target_artist"])

        if not self.has_pending_moves():
            self.album_anim_timer.stop()

        self.tree.viewport().update()

    def get_selected_tracks(self) -> List[Track]:
        selected: List[Track] = []
        for it in self.tree.selectedItems():
            itype = it.data(0, Qt.UserRole + 1)
            if itype == "TRACK":
                t = it.data(0, Qt.UserRole)
                if t and t not in selected:
                    selected.append(t)
            elif itype in ("ALBUM_HEADER", "ARTIST_HEADER"):
                for t in it.data(0, Qt.UserRole + 12) or []:
                    if t not in selected:
                        selected.append(t)
        return selected

    def _on_selection_changed(self) -> None:
        self.tree.viewport().update()
        self.selection_changed.emit(self.get_selected_tracks())

    def _on_track_field_edited(self, track: Track, field_name: str, new_value: object) -> None:
        self.track_metadata_changed.emit(track, field_name, new_value)
        self.refresh_display()

    def load_tracks(self, tracks: List[Track]) -> None:
        self._tracks = tracks
        self.delegate.set_tracks_context(tracks)
        self.refresh_display()

    def _get_album_family_key(self, alb_name: str) -> str:
        cleaned = re.sub(r"[\(\[].*?[\)\]]", "", str(alb_name))
        cleaned = re.sub(r"\+\s*\d+.*", "", cleaned)
        cleaned = re.sub(r"[^a-z0-9а-яё]", "", cleaned.lower())
        return cleaned or alb_name.lower().strip()

    def _get_album_sort_key(
        self,
        alb_item_tuple: Tuple[str, List[Track]],
        family_earliest_years: Dict[str, int]
    ) -> tuple:
        alb_name, trk_list = alb_item_tuple
        family_key = self._get_album_family_key(alb_name)
        family_base_year = family_earliest_years.get(family_key, 9999)

        edition_years = [t.metadata.year for t in trk_list if t.metadata.year and t.metadata.year > 0]
        edition_year = min(edition_years) if edition_years else family_base_year

        tier = 0
        lowered = alb_name.lower()
        if any(marker in lowered for marker in ("single", "сингл", "ep", "maxi")):
            tier = 3
        elif any(marker in lowered for marker in ("best", "лучшее", "collection", "greatest", "hits", "сборник")):
            tier = 2
        elif any(marker in lowered for marker in ("bonus", "бонус", "deluxe", "remaster", "reissue", "+")):
            tier = 1

        col = self._sort_col
        if col == 3:
            return (edition_year, family_key, tier, alb_name.lower())
        elif col == 7:
            return (family_key, tier, edition_year, alb_name.lower())
        elif col == 0:
            return (tier, family_base_year, family_key)

        return (family_base_year, family_key, tier, edition_year, alb_name.lower())

    def refresh_display(self) -> None:
        if self._is_editing:
            self._pending_refresh = True
            return

        expanded_states: Dict[str, bool] = {}
        for i in range(self.tree.topLevelItemCount()):
            art_it = self.tree.topLevelItem(i)
            art_name = art_it.data(0, Qt.UserRole + 10)
            if art_name:
                expanded_states[f"ART::{art_name}"] = art_it.isExpanded()

            for j in range(art_it.childCount()):
                alb_it = art_it.child(j)
                alb_name = alb_it.data(0, Qt.UserRole + 10)
                if alb_name:
                    expanded_states[f"ALB::{art_name}::{alb_name}"] = alb_it.isExpanded()

        self.tree.clear()
        if not self._tracks:
            return

        self.delegate.set_tracks_context(self._tracks)
        discography: Dict[str, Dict[str, List[Track]]] = {}

        for t in self._tracks:
            if not self.show_excluded and t.is_excluded_from_export:
                continue

            meta = t.export_metadata if (self.preview_enabled and t.export_metadata) else t.metadata
            art = meta.album_artist or meta.artist or t.effective_artist

            if self.preview_enabled and t.export_metadata and t.export_metadata.album:
                alb = t.export_metadata.album
            else:
                alb = t.master_album if t.master_album else t.effective_album

            if not self._matches_search(t, meta):
                continue

            discography.setdefault(art, {}).setdefault(alb, []).append(t)

        sorted_artists = sorted(discography.keys(), key=lambda s: s.lower())
        is_desc = (self._sort_order == Qt.DescendingOrder)

        for art_idx, art in enumerate(sorted_artists):
            albums_dict = discography[art]
            all_art_tracks = [t for alb_tracks in albums_dict.values() for t in alb_tracks]
            all_art_excluded = all(t.is_excluded_from_export for t in all_art_tracks)

            art_item = QTreeWidgetItem()
            art_item.setData(0, Qt.UserRole + 1, "ARTIST_HEADER")
            art_item.setData(0, Qt.UserRole + 3, all_art_excluded)
            art_item.setData(0, Qt.UserRole + 10, art)
            art_item.setData(0, Qt.UserRole + 11, f"{len(albums_dict)} альб. • {len(all_art_tracks)} трек.")
            art_item.setData(0, Qt.UserRole + 12, all_art_tracks)
            art_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            art_item.setFirstColumnSpanned(True)
            self.tree.addTopLevelItem(art_item)

            family_earliest_years: Dict[str, int] = {}
            for alb_name, trk_list in albums_dict.items():
                f_key = self._get_album_family_key(alb_name)
                years = [t.metadata.year for t in trk_list if t.metadata.year and t.metadata.year > 0]
                if years:
                    min_y = min(years)
                    family_earliest_years[f_key] = min(family_earliest_years.get(f_key, 9999), min_y)

            sorted_albums = sorted(
                albums_dict.items(),
                key=lambda item: self._get_album_sort_key(item, family_earliest_years),
                reverse=(is_desc if self._sort_col in (0, 3, 7) else False)
            )

            for alb, group_tracks in sorted_albums:
                display_tracks = list(group_tracks)
                display_tracks.sort(key=self._get_track_sort_key, reverse=is_desc)

                first = group_tracks[0]
                year_val = first.metadata.year

                has_year_already = bool(year_val and re.search(rf"\b{year_val}\b", str(alb)))
                if has_year_already or not year_val:
                    album_display_title = alb
                else:
                    album_display_title = f"{alb} ({year_val})"

                album_status = self._resolve_album_status(group_tracks)
                all_album_excluded = all(t.is_excluded_from_export for t in group_tracks)

                active_count = sum(1 for t in group_tracks if not t.is_excluded_from_export)
                total_count = len(group_tracks)
                count_str = f"{active_count}/{total_count} треков" if 0 < active_count < total_count else f"{total_count} треков"

                alb_item = QTreeWidgetItem()
                alb_item.setData(0, Qt.UserRole + 1, "ALBUM_HEADER")
                alb_item.setData(0, Qt.UserRole + 2, album_status)
                alb_item.setData(0, Qt.UserRole + 3, all_album_excluded)
                alb_item.setData(0, Qt.UserRole + 10, album_display_title)
                alb_item.setData(0, Qt.UserRole + 11, count_str)
                alb_item.setData(0, Qt.UserRole + 12, group_tracks)
                alb_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                alb_item.setFirstColumnSpanned(True)
                art_item.addChild(alb_item)

                for idx, t in enumerate(display_tracks, start=1):
                    t_meta = t.export_metadata if (self.preview_enabled and t.export_metadata) else t.metadata

                    # Всегда актуальное имя трека
                    fname_str = t.current_filename

                    trk_no = t_meta.track_number or idx
                    tot_no = t_meta.total_tracks or len(group_tracks)
                    tr_num_str = f"{trk_no}/{tot_no}"
                    status_label = t.duplicate_status.name

                    row_values = [
                        status_label,
                        tr_num_str,
                        t_meta.title or t.source_path.stem,
                        str(t_meta.year or ""),
                        t_meta.genre or "",
                        fname_str,
                        t_meta.artist or "",
                        t_meta.album or "",
                        t_meta.album_artist or ""
                    ]

                    item = QTreeWidgetItem(row_values)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                    item.setData(0, Qt.UserRole, t)
                    item.setData(0, Qt.UserRole + 1, "TRACK")
                    item.setData(0, Qt.UserRole + 2, t.duplicate_status)
                    item.setData(0, Qt.UserRole + 3, t.is_excluded_from_export)
                    alb_item.addChild(item)

                if all_album_excluded:
                    alb_item.setExpanded(False)
                else:
                    prev_state = expanded_states.get(f"ALB::{art}::{album_display_title}", True)
                    alb_item.setExpanded(prev_state)

            art_prev = expanded_states.get(f"ART::{art}", True)
            art_item.setExpanded(art_prev and not all_art_excluded)

            if art_idx < len(sorted_artists) - 1:
                spacer = QTreeWidgetItem()
                spacer.setData(0, Qt.UserRole + 1, "ARTIST_SPACER")
                spacer.setFlags(Qt.NoItemFlags)
                spacer.setFirstColumnSpanned(True)
                self.tree.addTopLevelItem(spacer)

    def eventFilter(self, watched, event) -> bool:
        if watched == self.tree.header():
            if event.type() in (QEvent.Resize, QEvent.LayoutRequest, QEvent.Show):
                h = self.tree.header()
                btn_w = 28
                self.btn_gear.setGeometry(h.width() - btn_w, 0, btn_w, h.height())
                self.btn_gear.raise_()
        return super().eventFilter(watched, event)

    def _on_header_section_clicked(self, logical_index: int) -> None:
        if self._sort_col == logical_index:
            self._sort_order = Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self._sort_col = logical_index
            self._sort_order = Qt.AscendingOrder

        self.tree.header().setSortIndicator(self._sort_col, self._sort_order)
        self.save_column_settings()
        self.refresh_display()

    def _show_column_chooser_menu(self) -> None:
        menu = QMenu(self)
        menu.setTitle("Отображаемые столбцы")
        for name, col_idx, _ in self.COLUMNS_DEF:
            action = QAction(name, menu)
            action.setCheckable(True)
            action.setChecked(not self.tree.isColumnHidden(col_idx))
            action.toggled.connect(lambda checked, idx=col_idx: self._set_column_visibility(idx, checked))
            menu.addAction(action)
        pos = self.btn_gear.mapToGlobal(QPoint(0, self.btn_gear.height()))
        menu.exec(pos)

    def _set_column_visibility(self, col_idx: int, visible: bool) -> None:
        self.tree.setColumnHidden(col_idx, not visible)
        self.save_column_settings()

    def _open_tree_context_menu(self, pos: QPoint) -> None:
        selected_tracks = self.get_selected_tracks()
        if not selected_tracks:
            return

        menu = QMenu(self)
        all_excluded = all(t.is_excluded_from_export for t in selected_tracks)

        count_str = f" ({len(selected_tracks)} треков)"
        if all_excluded:
            act_toggle = QAction(f"♻ Восстановить выделенные альбомы/треки{count_str}", menu)
            act_toggle.triggered.connect(lambda: self.set_tracks_excluded_batch(selected_tracks, False))
        else:
            act_toggle = QAction(f"🗑 Исключить выделенные альбомы/треки{count_str}", menu)
            act_toggle.triggered.connect(lambda: self.set_tracks_excluded_batch(selected_tracks, True))

        menu.addAction(act_toggle)
        menu.exec(self.tree.mapToGlobal(pos))

    def set_tracks_excluded_batch(self, tracks: List[Track], state: bool) -> None:
        for t in tracks:
            t.is_excluded_from_export = state
        self.batch_tracks_toggled.emit(tracks, state)
        self.refresh_display()

    def toggle_single_track_exclusion(self, track: Track) -> None:
        self.set_tracks_excluded_batch([track], not track.is_excluded_from_export)

    def set_preview_enabled(self, state: bool) -> None:
        self.preview_enabled = state
        self.preview_toggled.emit(state)
        self.refresh_display()

    def set_show_excluded(self, state: bool) -> None:
        self.show_excluded = state
        self.show_excluded_toggled.emit(state)
        self.refresh_display()

    def _resolve_album_status(self, group_tracks: List[Track]) -> DuplicateStatus:
        dup_count = sum(1 for t in group_tracks if t.duplicate_status == DuplicateStatus.DUPLICATE)
        remix_count = sum(1 for t in group_tracks if t.duplicate_status == DuplicateStatus.REMIX)
        total = len(group_tracks)
        if dup_count == total:
            return DuplicateStatus.DUPLICATE
        if remix_count == total:
            return DuplicateStatus.REMIX
        return DuplicateStatus.ORIGINAL

    def _get_track_sort_key(self, t: Track):
        meta = t.export_metadata if (self.preview_enabled and t.export_metadata) else t.metadata
        col = self._sort_col
        if col == 0:
            return (t.duplicate_status.name, meta.track_number or 0)
        if col == 1:
            return (meta.track_number or 0, meta.title or "")
        if col == 2:
            return (meta.title or t.source_path.stem).lower()
        if col == 3:
            return (meta.year or 0, meta.track_number or 0)
        if col == 4:
            return (meta.genre or "").lower()
        if col == 5:
            return t.source_path.name.lower()
        if col == 6:
            return (meta.artist or "").lower()
        if col == 7:
            return (meta.album or "").lower()
        return 0