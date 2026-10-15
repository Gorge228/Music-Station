"""
Интерактивный делегат табличных ячеек треклиста.
Инкапсулирует таймер отложенного переноса трека в другой альбом,
выпадающие списки (с умным поиском) и сигналы блокировки.
"""
import time
from typing import List, Dict, Optional, Set
from PySide6.QtWidgets import (
    QStyledItemDelegate, QComboBox, QStyle, QWidget, QCompleter
)
from PySide6.QtCore import Qt, QRectF, QSize, Signal
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QFont

from core.domain.models import Track
from core.domain.enums import DuplicateStatus
from ui.theme import STATUS_COLORS
from ui.panels.tag_editor_panel import GENRE_CATALOG


class TrackEditorDelegate(QStyledItemDelegate):
    track_edited = Signal(Track, str, object)
    album_change_requested = Signal(Track, str)
    album_artist_change_requested = Signal(Track, str)
    album_move_cancelled = Signal(Track)
    editor_opened = Signal()
    editor_closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_tracks: List[Track] = []
        self.pending_album_moves: Dict[str, dict] = {}
        self.pending_artist_moves: Dict[str, dict] = {}

    def set_tracks_context(self, tracks: List[Track]) -> None:
        self.all_tracks = tracks

    def sizeHint(self, option, index):
        col0 = index.siblingAtColumn(0)
        item_type = col0.data(Qt.UserRole + 1)
        if item_type in ("ARTIST_SPACER", "ALBUM_SPACER"):
            return QSize(0, 16)
        if item_type in ("ARTIST_HEADER", "ALBUM_HEADER"):
            return QSize(0, 32)
        return super().sizeHint(option, index)

    def paint(self, painter: QPainter, option, index):
        col0 = index.siblingAtColumn(0)
        item_type = col0.data(Qt.UserRole + 1)

        if item_type in ("ARTIST_HEADER", "ALBUM_HEADER", "ARTIST_SPACER", "ALBUM_SPACER"):
            return

        track: Optional[Track] = col0.data(Qt.UserRole)
        status = col0.data(Qt.UserRole + 2) or DuplicateStatus.ORIGINAL
        is_excluded = col0.data(Qt.UserRole + 3) is True
        col = index.column()

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#2B3545"))

        if col == 0 and item_type == "TRACK":
            rect = option.rect
            badge_w, badge_h = 70.0, 18.0
            badge_x = rect.x() + (rect.width() - badge_w) / 2.0
            badge_y = rect.y() + (rect.height() - badge_h) / 2.0
            badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)
            status_color = QColor(STATUS_COLORS.get(status, "#7F8C8D"))

            if is_excluded:
                painter.setBrush(QBrush(QColor("#22242B")))
                painter.setPen(QPen(QColor("#4B5260"), 1))
                painter.drawRoundedRect(badge_rect, 3, 3)
                painter.setPen(QColor("#6A7180"))
            else:
                fill_color = QColor(status_color)
                fill_color.setAlpha(45)
                painter.setBrush(QBrush(fill_color))
                painter.setPen(QPen(status_color, 1))
                painter.drawRoundedRect(badge_rect, 3, 3)
                painter.setPen(status_color.lighter(120))

            f_badge = QFont(painter.font())
            f_badge.setBold(True)
            f_badge.setPointSize(9)
            f_badge.setStrikeOut(is_excluded)
            painter.setFont(f_badge)
            painter.drawText(badge_rect, Qt.AlignCenter, index.data(Qt.DisplayRole) or "")
            painter.restore()
            return

        track_key = track.track_id if track else None
        active_moves = (
            self.pending_album_moves if col == 7 else
            (self.pending_artist_moves if col == 8 else None)
        )

        if active_moves and track_key in active_moves:
            move_info = active_moves[track_key]
            elapsed = time.time() - move_info["start_time"]
            remaining = max(0.0, move_info["duration"] - elapsed)
            ratio = remaining / move_info["duration"]

            rect = option.rect
            painter.setPen(QColor("#F39C12"))
            font = QFont(painter.font())
            font.setBold(True)
            painter.setFont(font)
            target_val = move_info.get("target_album") or move_info.get("target_artist")
            txt = f"➜ {target_val} ({remaining:.1f}с)"
            painter.drawText(rect.adjusted(6, 0, -84, -3), Qt.AlignVCenter | Qt.AlignLeft, txt)

            cancel_rect = QRectF(rect.right() - 78, rect.y() + 4, 72, rect.height() - 8)
            painter.setBrush(QBrush(QColor("#C0392B")))
            painter.setPen(QPen(QColor("#E74C3C"), 1))
            painter.drawRoundedRect(cancel_rect, 3, 3)

            f_cancel = QFont(painter.font())
            f_cancel.setPointSize(9)
            f_cancel.setBold(True)
            painter.setFont(f_cancel)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(cancel_rect, Qt.AlignCenter, "✕ Отмена")

            line_y = rect.bottom() - 2.5
            line_w = (rect.width() - 8) * ratio
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#E67E22")))
            painter.drawRoundedRect(QRectF(rect.x() + 4, line_y, line_w, 2.5), 1, 1)

            painter.restore()
            return

        font = QFont(painter.font())
        font.setStrikeOut(is_excluded)
        painter.setFont(font)
        painter.setPen(QColor("#626875") if is_excluded else QColor("#DCE0E6"))

        text = index.data(Qt.DisplayRole) or ""
        text_rect = option.rect.adjusted(6, 0, -6, 0)
        align = Qt.AlignVCenter | (Qt.AlignCenter if col in (1, 3) else Qt.AlignLeft)
        painter.drawText(text_rect, align, text)
        painter.restore()

    def createEditor(self, parent: QWidget, option, index):
        col0 = index.siblingAtColumn(0)
        if col0.data(Qt.UserRole + 1) != "TRACK":
            return None

        track: Optional[Track] = col0.data(Qt.UserRole)
        if not track or index.column() not in (2, 3, 4, 6, 7, 8):
            return None

        if index.column() == 7 and track.track_id in self.pending_album_moves:
            return None
        if index.column() == 8 and track.track_id in self.pending_artist_moves:
            return None

        cb = QComboBox(parent)
        cb.setEditable(True)

        # Интеллектуальный фильтр на лету (ищет в любом месте слова)
        completer = QCompleter(cb.model(), cb)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        cb.setCompleter(completer)

        if cb.lineEdit():
            cb.lineEdit().selectAll()

        self.editor_opened.emit()
        return cb

    def destroyEditor(self, editor: QWidget, index) -> None:
        self.editor_closed.emit()
        super().destroyEditor(editor, index)

    def setEditorData(self, editor: QWidget, index):
        if not isinstance(editor, QComboBox):
            super().setEditorData(editor, index)
            return

        col0 = index.siblingAtColumn(0)
        track: Track = col0.data(Qt.UserRole)
        col = index.column()

        editor.blockSignals(True)
        editor.clear()

        if col == 6:  # Исполнитель
            album_artist = track.metadata.album_artist or track.effective_artist
            artist_variants: Set[str] = {"Various Artists"}
            for t in self.all_tracks:
                if t.metadata.artist:
                    artist_variants.add(t.metadata.artist.strip())

            editor.addItem(album_artist)
            for var in sorted(artist_variants, key=lambda s: s.lower()):
                if editor.findText(var) == -1:
                    editor.addItem(var)
            editor.setEditText(track.metadata.artist or album_artist)

        elif col == 8:  # Исполнитель альбома
            orig_artist = (track.metadata.artist or track.effective_artist or "").strip()
            cur_alb_art = (track.metadata.album_artist or orig_artist).strip()

            if orig_artist:
                editor.addItem(orig_artist)
            if editor.findText("Various Artists") == -1:
                editor.addItem("Various Artists")

            all_alb_artists = sorted({
                (t.metadata.album_artist or "").strip()
                for t in self.all_tracks
                if (t.metadata.album_artist or "").strip()
            }, key=lambda s: s.lower())

            for aa in all_alb_artists:
                if editor.findText(aa) == -1:
                    editor.addItem(aa)

            editor.setEditText(cur_alb_art)

        elif col == 2:  # Название
            versions: Set[str] = set()
            target_nuc = track.normalized_title

            for t in self.all_tracks:
                title_val = (t.metadata.title or "").strip()
                if not title_val:
                    continue
                if target_nuc and t.normalized_title == target_nuc:
                    versions.add(title_val)

            cur_title = track.metadata.title or track.source_path.stem
            if cur_title:
                versions.add(cur_title.strip())

            for v in sorted(versions, key=lambda s: s.lower()):
                editor.addItem(v)

            editor.setEditText(cur_title)

        elif col == 4:  # Жанр
            cur_genre = track.metadata.genre or ""
            if cur_genre and cur_genre not in GENRE_CATALOG:
                editor.addItem(cur_genre)
            for g in GENRE_CATALOG:
                editor.addItem(g)
            editor.setEditText(cur_genre)

        elif col == 3:  # Год
            years = {
                t.metadata.year for t in self.all_tracks
                if t.effective_artist == track.effective_artist and t.metadata.year
            }
            for y in sorted(years, reverse=True):
                editor.addItem(str(y))
            editor.setEditText(str(track.metadata.year or ""))

        elif col == 7:  # Альбом
            art_key = (track.metadata.album_artist or track.effective_artist).strip().lower()
            current_artist_albums = set()
            all_albums = set()

            for t in self.all_tracks:
                alb = t.master_album or t.metadata.album or t.effective_album
                if alb and alb.strip():
                    clean_alb = alb.strip()
                    all_albums.add(clean_alb)
                    t_art_key = (t.metadata.album_artist or t.effective_artist).strip().lower()
                    if t_art_key == art_key:
                        current_artist_albums.add(clean_alb)

            added = set()
            for a in sorted(current_artist_albums, key=lambda s: s.lower()):
                editor.addItem(a)
                added.add(a)

            for a in sorted(all_albums - added, key=lambda s: s.lower()):
                editor.addItem(a)

            editor.setEditText(track.effective_album)

        editor.blockSignals(False)

    def setModelData(self, editor: QWidget, model, index):
        if not isinstance(editor, QComboBox):
            super().setModelData(editor, model, index)
            return

        new_text = editor.currentText().strip()
        col0 = index.siblingAtColumn(0)
        track: Track = col0.data(Qt.UserRole)
        col = index.column()

        if col == 2 and new_text and new_text != track.metadata.title:
            self.track_edited.emit(track, "title", new_text)
        elif col == 3:
            val = int(new_text) if new_text.isdigit() else None
            if val != track.metadata.year:
                self.track_edited.emit(track, "year", val)
        elif col == 4 and new_text != track.metadata.genre:
            self.track_edited.emit(track, "genre", new_text)
        elif col == 6 and new_text and new_text != track.metadata.artist:
            self.track_edited.emit(track, "artist", new_text)
        elif col == 7 and new_text and new_text != track.effective_album:
            self.album_change_requested.emit(track, new_text)
        elif col == 8 and new_text and new_text != (track.metadata.album_artist or track.effective_artist):
            self.album_artist_change_requested.emit(track, new_text)