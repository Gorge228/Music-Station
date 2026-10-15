"""
Интерактивная сетка выбора обложек из имеющихся в фонотеке файлов.
"""
from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QScrollArea, QWidget, QGridLayout, QFrame, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFontMetrics

from ui.theme import COVER_CARD_QSS


class CoverCard(QFrame):
    """Карточка обложки 180x180 px с подписью автора и альбома."""
    clicked = Signal(bytes)

    def __init__(self, cover_info: dict, parent=None):
        super().__init__(parent)
        self._data = cover_info["bytes"]
        self.setFixedSize(194, 238)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(COVER_CARD_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.lbl_img = QLabel()
        self.lbl_img.setFixedSize(180, 180)
        self.lbl_img.setAlignment(Qt.AlignCenter)

        pix = cover_info.get("pixmap")
        if pix and not pix.isNull():
            scaled = pix.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.lbl_img.setPixmap(scaled)
        else:
            self.lbl_img.setText("Нет изображения")

        layout.addWidget(self.lbl_img)

        fm = QFontMetrics(self.font())
        art_str = fm.elidedText(cover_info.get("artist", "Unknown"), Qt.ElideRight, 178)
        alb_str = fm.elidedText(cover_info.get("album", "Unknown"), Qt.ElideRight, 178)

        lbl_art = QLabel(art_str)
        lbl_art.setAlignment(Qt.AlignCenter)

        lbl_alb = QLabel(alb_str)
        lbl_alb.setAlignment(Qt.AlignCenter)

        layout.addWidget(lbl_art)
        layout.addWidget(lbl_alb)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._data)
        super().mouseReleaseEvent(event)


class CoverGalleryDialog(QDialog):
    """Модальное окно галереи обложек всей фонотеки с динамической сеткой."""

    def __init__(
        self,
        parent=None,
        current_artist: str = "",
        current_album: str = "",
        covers: Optional[List[dict]] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("Выбор обложки из фонотеки")
        self.setModal(True)

        self._all_covers = covers or []
        self._current_artist = current_artist
        self._current_album = current_album
        self.selected_cover_bytes: Optional[bytes] = None

        self._init_ui()
        self._populate_filters()
        self._rebuild_grid()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(QLabel("Фильтр фонотеки:"))

        self.combo_filter = QComboBox()
        self.combo_filter.currentIndexChanged.connect(self._on_filter_changed)
        header.addWidget(self.combo_filter)
        header.addStretch()

        self.lbl_counter = QLabel()
        header.addWidget(self.lbl_counter)
        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(10, 10, 10, 10)
        self.grid.setSpacing(12)
        self.scroll.setWidget(self.container)

        root.addWidget(self.scroll, stretch=1)

        footer = QHBoxLayout()
        footer.addWidget(QLabel("Нажмите ЛКМ на карточку для выбора • Esc — отмена"))
        footer.addStretch()

        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)

        root.addLayout(footer)

    def _populate_filters(self) -> None:
        self.combo_filter.blockSignals(True)
        self.combo_filter.clear()
        self.combo_filter.addItem(f"⭐ Все обложки фонотеки ({len(self._all_covers)})", "ALL")

        if self._current_artist:
            art_matches = sum(1 for c in self._all_covers if c["artist"].lower() == self._current_artist.lower())
            if art_matches > 0:
                self.combo_filter.addItem(f"🎤 Текущий автор: «{self._current_artist}» ({art_matches})", "CURRENT_ARTIST")

        if self._current_album:
            alb_matches = sum(1 for c in self._all_covers if c["album"].lower() == self._current_album.lower())
            if alb_matches > 0:
                self.combo_filter.addItem(f"💿 Текущий альбом: «{self._current_album}» ({alb_matches})", "CURRENT_ALBUM")

        unique_artists = sorted({c["artist"] for c in self._all_covers if c["artist"]}, key=lambda s: s.lower())
        if len(unique_artists) > 1:
            for art in unique_artists:
                count = sum(1 for c in self._all_covers if c["artist"].lower() == art.lower())
                self.combo_filter.addItem(f"👤 {art} ({count})", f"ARTIST:{art}")

        self.combo_filter.blockSignals(False)

    def _on_filter_changed(self) -> None:
        self._rebuild_grid()

    def _get_filtered_covers(self) -> List[dict]:
        data = self.combo_filter.currentData()
        if not data or data == "ALL":
            return self._all_covers
        if data == "CURRENT_ARTIST":
            return [c for c in self._all_covers if c["artist"].lower() == self._current_artist.lower()]
        if data == "CURRENT_ALBUM":
            return [c for c in self._all_covers if c["album"].lower() == self._current_album.lower()]
        if isinstance(data, str) and data.startswith("ARTIST:"):
            art = data.split("ARTIST:", 1)[1]
            return [c for c in self._all_covers if c["artist"].lower() == art.lower()]
        return self._all_covers

    def _rebuild_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        covers = self._get_filtered_covers()
        total = len(covers)
        self.lbl_counter.setText(f"Найдено: {total}")

        if total == 0:
            lbl_empty = QLabel("В выбранной категории нет обложек")
            lbl_empty.setAlignment(Qt.AlignCenter)
            self.grid.addWidget(lbl_empty, 0, 0)
            self.resize(500, 360)
            return

        cols = 3 if total <= 9 else (4 if total <= 16 else 5)
        for idx, cov in enumerate(covers):
            row = idx // cols
            col = idx % cols
            card = CoverCard(cov, self.container)
            card.clicked.connect(self._on_card_selected)
            self.grid.addWidget(card, row, col)

        card_w, card_h = 206, 250
        dialog_w = cols * card_w + 44
        visible_rows = min((total + cols - 1) // cols, 3)
        dialog_h = min(visible_rows * card_h + 110, 860)
        self.resize(dialog_w, dialog_h)

    def _on_card_selected(self, data: bytes) -> None:
        self.selected_cover_bytes = data
        self.accept()

    def get_selected_cover_bytes(self) -> Optional[bytes]:
        return self.selected_cover_bytes