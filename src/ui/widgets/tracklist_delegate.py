"""
Интерактивный делегат ячеек треклиста.
Устранено дублирование методов setModelData.
"""
import time
from typing import List, Dict, Optional
from PySide6.QtWidgets import (
    QStyledItemDelegate, QComboBox, QWidget, QStyle
)
from PySide6.QtCore import Qt, QRectF, QSize, Signal
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QFont

from core.domain.models import Track
from core.domain.enums import DuplicateStatus
from ui.theme import STATUS_COLORS

GENRE_CATALOG = [
    "Rock", "Pop Rock", "Alternative Rock", "Indie Rock", "Hard Rock", "Punk Rock",
    "Post-Punk", "Metal", "Heavy Metal", "Thrash Metal", "Pop", "Synth-Pop",
    "Chanson", "Russian Chanson", "Hip-Hop", "Rap", "House", "Techno",
    "Trance", "Ambient", "R&B", "Soul", "Blues", "Jazz", "Classical", "Soundtrack"
]


class TrackEditorDelegate(QStyledItemDelegate):
    """Делегат для встроенного редактирования тегов прямо в таблице треклиста."""

    track_edited = Signal(Track, str, object)
    album_change_requested = Signal(Track, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_tracks: List[Track] = []
        self.pending_album_moves: Dict[str, dict] = {}  # Ключ — track.track_id

    def set_tracks_context(self, tracks: List[Track]) -> None:
        self.all_tracks = tracks

    def sizeHint(self, option, index):
        col0 = index.siblingAtColumn(0)
        item_type = col0.data(Qt.UserRole + 1)
        if item_type == "ALBUM_SPACER":
            return QSize(0, 16)
        if item_type == "ALBUM_HEADER":
            return QSize(0, 30)
        return super().sizeHint(option, index)

    def paint(self, painter: QPainter, option, index):
        col0 = index.siblingAtColumn(0)
        item_type = col0.data(Qt.UserRole + 1)

        if item_type in ("ALBUM_HEADER", "ALBUM_SPACER"):
            return

        track: Optional[Track] = col0.data(Qt.UserRole)
        status = col0.data(Qt.UserRole + 2) or DuplicateStatus.ORIGINAL
        is_excluded = col0.data(Qt.UserRole + 3) is True
        col = index.column()

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#2B3545"))

        # Бейдж статуса
        if col == 0 and item_type == "TRACK":
            rect = option.rect
            b_w, b_h = 70.0, 18.0
            b_x = rect.x() + (rect.width() - b_w) / 2.0
            b_y = rect.y() + (rect.height() - b_h) / 2.0
            badge_rect = QRectF(b_x, b_y, b_w, b_h)
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

            f = QFont(painter.font())
            f.setBold(True)
            f.setPointSize(9)
            f.setStrikeOut(is_excluded)
            painter.setFont(f)
            painter.drawText(badge_rect, Qt.AlignCenter, index.data(Qt.DisplayRole) or "")
            painter.restore()
            return

        # Колонка альбома при отложенном переносе
        track_key = track.track_id if track else ""
        if col == 7 and track_key in self.pending_album_moves:
            info = self.pending_album_moves[track_key]
            elapsed = time.time() - info["start_time"]
            remaining = max(0.0, info["duration"] - elapsed)
            ratio = remaining / info["duration"]

            rect = option.rect
            painter.setPen(QColor("#F39C12"))
            f = QFont(painter.font())
            f.setBold(True)
            painter.setFont(f)
            txt = f"➜ {info['target_album']} ({remaining:.1f}с) [Esc: Отмена]"
            painter.drawText(rect.adjusted(6, 0, -6, -3), Qt.AlignVCenter | Qt.AlignLeft, txt)

            line_y = rect.bottom() - 2.5
            line_w = (rect.width() - 8) * ratio
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#E67E22")))
            painter.drawRoundedRect(QRectF(rect.x() + 4, line_y, line_w, 2.5), 1, 1)
            painter.restore()
            return

        # Обычный текст ячейки
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

        if index.column() not in (2, 3, 4, 6, 7):
            return None

        cb = QComboBox(parent)
        cb.setEditable(True)
        cb.setStyleSheet("""
            QComboBox {
                background-color: #21252D;
                color: #FFFFFF;
                border: 1px solid #3B82F6;
                border-radius: 3px;
                padding: 1px 4px;
                font-size: 11px;
            }
        """)
        if cb.lineEdit():
            cb.lineEdit().selectAll()
        return cb

    def setEditorData(self, editor: QWidget, index):
        if not isinstance(editor, QComboBox):
            super().setEditorData(editor, index)
            return

        col0 = index.siblingAtColumn(0)
        track: Optional[Track] = col0.data(Qt.UserRole)
        if not track:
            return

        col = index.column()
        editor.blockSignals(True)
        editor.clear()

        # Название
        if col == 2:
            versions = {t.metadata.title.strip() for t in self.all_tracks if t.normalized_title == track.normalized_title and t.metadata.title}
            for v in sorted(versions):
                editor.addItem(v)
            editor.setEditText(track.metadata.title or track.source_path.stem)

        # Год
        elif col == 3:
            years = {str(t.metadata.year) for t in self.all_tracks if t.effective_artist == track.effective_artist and t.metadata.year}
            for y in sorted(years, reverse=True):
                editor.addItem(y)
            editor.setEditText(str(track.metadata.year or ""))

        # Жанр
        elif col == 4:
            for g in GENRE_CATALOG:
                editor.addItem(g)
            editor.setEditText(track.metadata.genre or "")

        # Исполнитель
        elif col == 6:
            art = track.effective_artist
            editor.addItem(art)
            editor.setEditText(track.metadata.artist or art)

        # Альбом
        elif col == 7:
            albums = {t.effective_album for t in self.all_tracks if t.effective_album}
            for a in sorted(albums):
                editor.addItem(a)
            editor.setEditText(track.effective_album)

        editor.blockSignals(False)

    # ИСПРАВЛЕНО: Единственный корректный метод setModelData (дубликат удален)
    def setModelData(self, editor: QWidget, model, index):
        if not isinstance(editor, QComboBox):
            super().setModelData(editor, model, index)
            return

        new_text = editor.currentText().strip()
        col0 = index.siblingAtColumn(0)
        track: Optional[Track] = col0.data(Qt.UserRole)
        if not track:
            return

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