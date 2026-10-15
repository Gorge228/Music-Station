"""
Полнофункциональная панель расширенного редактирования метаданных и управления обложками.
Включает синхронизацию выпадающих списков со всей фонотекой и защиту мульти-выбора.
"""
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any, Set
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QScrollArea,
    QComboBox, QLineEdit, QTextEdit, QLabel, QPushButton, QFileDialog,
    QCheckBox, QMenu, QApplication, QCompleter
)
from PySide6.QtCore import Qt, Signal, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QAction

from core.domain.models import Track
from ui.dialogs.cover_gallery_dialog import CoverGalleryDialog
from ui.theme import COVER_DROP_QSS, PRIMARY_BTN_QSS

logger = logging.getLogger("MusicFormator")

GENRE_CATALOG = [
    "Rock", "Pop Rock", "Alternative Rock", "Indie Rock", "Hard Rock", "Punk Rock",
    "Post-Punk", "Horror Punk", "Psychedelic Rock", "Progressive Rock", "Grunge",
    "Garage Rock", "Shoegaze", "Folk Rock", "Rock 'n' Roll", "Rock Ballad", "Acoustic",
    "Ska-Punk", "Heavy Metal", "Thrash Metal", "Death Metal", "Black Metal",
    "Symphonic Metal", "Nu Metal", "Metalcore", "Power Metal", "Gothic Metal",
    "Industrial Metal", "Pop", "Traditional Pop", "Synth-Pop", "K-Pop", "Indie Pop",
    "Dance-Pop", "Estrada", "Disco", "Eurodance", "Chanson", "Russian Chanson",
    "French Chanson", "Bard Music", "Urban Romance", "Hip-Hop", "Rap",
    "Old School Hip-Hop", "Trap", "Boom Bap", "Lofi Hip-Hop", "Drill", "Cloud Rap",
    "Rap Rock", "House", "Deep House", "Tech House", "Techno", "Drum and Bass",
    "Trance", "Ambient", "Synthwave", "Dubstep", "Breakbeat", "R&B",
    "Contemporary R&B", "Soul", "Neo-Soul", "Funk", "Blues", "Delta Blues",
    "Chicago Blues", "Jazz", "Swing", "Bebop", "Jazz Fusion", "Folk", "Reggae",
    "Ska", "Classical", "Soundtrack", "Instrumental"
]

MULTIPLE_VALUES_PLACEHOLDER = "<Разные значения>"


class CoverDropLabel(QLabel):
    cover_changed = Signal(bytes)
    cover_cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedSize(180, 180)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(COVER_DROP_QSS)

        self._cover_bytes: Optional[bytes] = None
        self._current_artist: str = ""
        self._current_album: str = ""
        self._library_covers: List[dict] = []

        self._set_empty_placeholder()

    def _set_empty_placeholder(self) -> None:
        self._cover_bytes = None
        self.setPixmap(QPixmap())
        self.setText("🖼 Нажмите ЛКМ\nдля выбора из каталога\nили перетащите файл\n(ПКМ — меню)")

    def set_cover_bytes(self, data: Optional[bytes]) -> None:
        if not data:
            self._set_empty_placeholder()
            return

        self._cover_bytes = data
        pix = QPixmap()
        if pix.loadFromData(data):
            scaled = pix.scaled(176, 176, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled)
            self.setText("")
        else:
            self._set_empty_placeholder()

    def get_cover_bytes(self) -> Optional[bytes]:
        return self._cover_bytes

    def set_library_context(
        self,
        current_artist: str = "",
        current_album: str = "",
        covers: Optional[List[dict]] = None
    ) -> None:
        self._current_artist = current_artist
        self._current_album = current_album
        self._library_covers = covers or []

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.open_cover_dialog()
            event.accept()
            return
        if event.button() == Qt.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def open_cover_dialog(self) -> None:
        dlg = CoverGalleryDialog(
            parent=self.window(),
            current_artist=self._current_artist,
            current_album=self._current_album,
            covers=self._library_covers
        )
        if dlg.exec():
            chosen = dlg.get_selected_cover_bytes()
            if chosen:
                self._apply_chosen_cover(chosen)

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        act_gallery = QAction("🖼 Выбрать из каталога фонотеки...", menu)
        act_gallery.triggered.connect(self.open_cover_dialog)
        menu.addAction(act_gallery)

        act_load = QAction("📂 Загрузить из файла...", menu)
        act_load.triggered.connect(self.load_from_file)
        menu.addAction(act_load)

        act_paste = QAction("📋 Вставить из буфера обмена", menu)
        act_paste.triggered.connect(self.paste_from_clipboard)
        menu.addAction(act_paste)

        if self._cover_bytes:
            menu.addSeparator()
            act_save = QAction("💾 Сохранить обложку в файл...", menu)
            act_save.triggered.connect(self.save_to_file)
            menu.addAction(act_save)

            act_del = QAction("🗑 Удалить обложку", menu)
            act_del.triggered.connect(self.clear_cover)
            menu.addAction(act_del)

        menu.exec(pos)

    def load_from_file(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Выбрать обложку", "", "Изображения (*.jpg *.jpeg *.png *.webp *.bmp)"
        )
        if f:
            try:
                self._apply_chosen_cover(Path(f).read_bytes())
            except Exception as e:
                logger.error(f"Не удалось открыть файл обложки: {e}")

    def paste_from_clipboard(self) -> bool:
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()

        img = clipboard.image()
        if not img.isNull():
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            img.save(buf, "PNG")
            self._apply_chosen_cover(bytes(ba))
            return True

        pix = clipboard.pixmap()
        if not pix.isNull():
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            pix.save(buf, "PNG")
            self._apply_chosen_cover(bytes(ba))
            return True

        if mime and mime.hasUrls():
            for url in mime.urls():
                f_path = Path(url.toLocalFile())
                if f_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                    try:
                        self._apply_chosen_cover(f_path.read_bytes())
                        return True
                    except Exception:
                        pass
        return False

    def save_to_file(self) -> None:
        if not self._cover_bytes:
            return
        f, _ = QFileDialog.getSaveFileName(self, "Сохранить обложку", "cover.jpg", "JPEG (*.jpg);;PNG (*.png)")
        if f:
            try:
                Path(f).write_bytes(self._cover_bytes)
            except Exception as e:
                logger.error(f"Ошибка сохранения обложки: {e}")

    def clear_cover(self) -> None:
        self._set_empty_placeholder()
        self.cover_cleared.emit()

    def _apply_chosen_cover(self, data: bytes) -> None:
        if not data:
            self.clear_cover()
            return

        pix = QPixmap()
        if pix.loadFromData(data):
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            if data.startswith(b"\x89PNG"):
                pix.save(buf, "PNG")
            else:
                pix.save(buf, "JPEG", 95)
            normalized_bytes = bytes(ba)
            self.set_cover_bytes(normalized_bytes)
            self.cover_changed.emit(normalized_bytes)
        else:
            self.set_cover_bytes(data)
            self.cover_changed.emit(data)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                f_path = Path(urls[0].toLocalFile())
                if f_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                    try:
                        self._apply_chosen_cover(f_path.read_bytes())
                        event.acceptProposedAction()
                        return
                    except Exception:
                        pass
        elif event.mimeData().hasImage():
            img = event.mimeData().imageData()
            if img:
                ba = QByteArray()
                buf = QBuffer(ba)
                buf.open(QIODevice.WriteOnly)
                img.save(buf, "PNG")
                self._apply_chosen_cover(bytes(ba))
                event.acceptProposedAction()


class TagEditorPanel(QWidget):
    apply_tags_requested = Signal(dict, bool)
    renumber_requested = Signal(list, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_tracks: List[Track] = []
        self._all_library_tracks: List[Track] = []
        self._cover_reader: Optional[Callable[[Path], Optional[bytes]]] = None
        self._cover_deleted_flag: bool = False
        self._cached_covers: List[dict] = []
        self._initial_edit_filename: str = ""

        self._init_ui()

    def set_cover_reader(self, reader: Callable[[Path], Optional[bytes]]) -> None:
        self._cover_reader = reader

    def set_library_context(self, all_tracks: List[Track]) -> None:
        self._all_library_tracks = all_tracks
        self.refresh_cover_cache(all_tracks, self._cover_reader)
        if self._current_tracks:
            self.set_track_data(self._current_tracks)

    def refresh_cover_cache(self, tracks: List[Track], reader: Optional[Callable[[Path], Optional[bytes]]]) -> None:
        if not reader or not tracks:
            return

        seen_albums = set()
        covers = []

        for t in tracks:
            alb = t.effective_album
            art = t.metadata.album_artist or t.effective_artist
            key = (art.lower(), alb.lower())
            if key in seen_albums:
                continue
            seen_albums.add(key)

            try:
                data = t.custom_cover_bytes if t.custom_cover_bytes else reader(t.source_path)
                if data and not t.is_cover_deleted:
                    pix = QPixmap()
                    if pix.loadFromData(data):
                        covers.append({
                            "artist": art,
                            "album": alb,
                            "bytes": data,
                            "pixmap": pix
                        })
            except Exception:
                pass

        self._cached_covers = covers

    def _get_library_suggestions(self, current_artist: str = "") -> dict:
        clean_art = current_artist.strip().lower()

        artists: Set[str] = {"Various Artists"}
        album_artists: Set[str] = {"Various Artists"}
        genres = set(GENRE_CATALOG)
        years = set()
        artist_albums = set()
        other_albums = set()

        for t in self._all_library_tracks:
            t_art = (t.metadata.artist or "").strip()
            t_alb_art = (t.metadata.album_artist or t.effective_artist or "").strip()
            t_alb = (t.master_album or t.metadata.album or t.effective_album or "").strip()
            t_genre = (t.metadata.genre or "").strip()
            t_year = t.metadata.year

            if t_art:
                artists.add(t_art)
            if t_alb_art:
                album_artists.add(t_alb_art)
            if t_genre:
                genres.add(t_genre)
            if t_year:
                years.add(str(t_year))

            if t_alb:
                if clean_art and (t_alb_art.lower() == clean_art or t_art.lower() == clean_art):
                    artist_albums.add(t_alb)
                else:
                    other_albums.add(t_alb)

        sorted_artists = sorted(artists, key=lambda s: s.lower())
        sorted_album_artists = sorted(album_artists, key=lambda s: s.lower())
        sorted_genres = sorted(genres, key=lambda s: s.lower())
        sorted_years = sorted(years, key=lambda s: int(s) if s.isdigit() else 0, reverse=True)

        prioritized_albums = (
            sorted(artist_albums, key=lambda s: s.lower()) +
            sorted(other_albums - artist_albums, key=lambda s: s.lower())
        )

        return {
            "artists": sorted_artists,
            "album_artists": sorted_album_artists,
            "albums": prioritized_albums,
            "genres": sorted_genres,
            "years": sorted_years
        }

    def _fill_combo(
        self,
        combo: QComboBox,
        current_val: str,
        suggestions: List[str],
        is_multiple: bool = False
    ) -> None:
        combo.blockSignals(True)
        combo.clear()

        # Настраиваем умный фильтр для поиска подстроки при вводе
        completer = QCompleter(suggestions, combo)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        combo.setCompleter(completer)

        if is_multiple:
            combo.addItem(MULTIPLE_VALUES_PLACEHOLDER)
            combo.setEditText(MULTIPLE_VALUES_PLACEHOLDER)
        else:
            if current_val:
                combo.addItem(current_val)
                combo.setEditText(current_val)

        for item in suggestions:
            clean_item = str(item).strip()
            if clean_item and combo.findText(clean_item) == -1:
                combo.addItem(clean_item)

        # ЖЕСТКАЯ ЗАЩИТА: Запрет автоподстановки первого значения при пустых полях трека!
        if not is_multiple:
            if current_val:
                combo.setEditText(current_val)
            else:
                combo.setCurrentIndex(-1)
                combo.setEditText("")

        if combo.lineEdit():
            combo.lineEdit().setAlignment(Qt.AlignCenter)

        combo.blockSignals(False)

    def _sync_album_suggestions(self, artist_name: str) -> None:
        if not artist_name or artist_name == MULTIPLE_VALUES_PLACEHOLDER:
            return

        sugg = self._get_library_suggestions(artist_name)
        current_alb_text = self.combo_album.currentText()

        self.combo_album.blockSignals(True)
        self.combo_album.clear()

        if current_alb_text:
            self.combo_album.addItem(current_alb_text)

        for alb in sugg["albums"]:
            if self.combo_album.findText(alb) == -1:
                self.combo_album.addItem(alb)

        self.combo_album.setEditText(current_alb_text)
        if self.combo_album.lineEdit():
            self.combo_album.lineEdit().setAlignment(Qt.AlignCenter)
        self.combo_album.blockSignals(False)

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignTop)

        self.lbl_mode_info = QLabel("Трек не выбран")
        layout.addWidget(self.lbl_mode_info)

        row_content = QHBoxLayout()
        row_content.setSpacing(10)
        row_content.setAlignment(Qt.AlignTop)

        col_cover = QVBoxLayout()
        col_cover.setAlignment(Qt.AlignTop)

        box_cover = QGroupBox("Обложка")
        box_cover.setFixedWidth(206)
        l_cov = QVBoxLayout(box_cover)
        l_cov.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        l_cov.setContentsMargins(6, 6, 6, 6)
        l_cov.setSpacing(6)

        self.cover_label = CoverDropLabel()
        self.cover_label.cover_changed.connect(lambda: setattr(self, "_cover_deleted_flag", False))
        self.cover_label.cover_cleared.connect(lambda: setattr(self, "_cover_deleted_flag", True))
        l_cov.addWidget(self.cover_label, alignment=Qt.AlignCenter)

        self.chk_album_cover = QCheckBox("Обложка альбома")
        self.chk_album_cover.setChecked(True)
        l_cov.addWidget(self.chk_album_cover, alignment=Qt.AlignCenter)

        col_cover.addWidget(box_cover)

        self.btn_renumber = QPushButton("🔢 Обновить нумерацию")
        self.btn_renumber.setFixedHeight(30)
        self.btn_renumber.setToolTip("Перенумеровать все треки данного альбома по порядку (1..N)")
        self.btn_renumber.clicked.connect(self._on_renumber_clicked)
        col_cover.addWidget(self.btn_renumber)

        col_cover.addStretch()
        row_content.addLayout(col_cover)

        box_meta = QGroupBox("Метаданные")
        grid = QGridLayout(box_meta)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(5)
        grid.setColumnMinimumWidth(0, 115)

        grid.addWidget(self._make_label("Имя файла:"), 0, 0, Qt.AlignCenter)
        self.edit_filename = QLineEdit()
        self.edit_filename.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.edit_filename, 0, 1, 1, 3)

        grid.addWidget(self._make_label("Трек №:"), 1, 0, Qt.AlignCenter)
        row_numbers = QHBoxLayout()
        row_numbers.setSpacing(4)
        row_numbers.addStretch()

        self.edit_track_num = QLineEdit()
        self.edit_track_num.setFixedWidth(42)
        self.edit_track_num.setAlignment(Qt.AlignCenter)
        row_numbers.addWidget(self.edit_track_num)
        row_numbers.addWidget(QLabel("/"))

        self.edit_total_tracks = QLineEdit()
        self.edit_total_tracks.setFixedWidth(42)
        self.edit_total_tracks.setAlignment(Qt.AlignCenter)
        row_numbers.addWidget(self.edit_total_tracks)

        row_numbers.addSpacing(18)
        row_numbers.addWidget(self._make_label("Диск №:"))

        self.edit_disc_num = QLineEdit()
        self.edit_disc_num.setFixedWidth(42)
        self.edit_disc_num.setAlignment(Qt.AlignCenter)
        row_numbers.addWidget(self.edit_disc_num)
        row_numbers.addWidget(QLabel("/"))

        self.edit_total_discs = QLineEdit()
        self.edit_total_discs.setFixedWidth(42)
        self.edit_total_discs.setAlignment(Qt.AlignCenter)
        row_numbers.addWidget(self.edit_total_discs)

        row_numbers.addStretch()
        grid.addLayout(row_numbers, 1, 1, 1, 3)

        grid.addWidget(self._make_label("Название:"), 2, 0, Qt.AlignCenter)
        self.combo_title = QComboBox()
        self.combo_title.setEditable(True)
        grid.addWidget(self.combo_title, 2, 1, 1, 3)

        grid.addWidget(self._make_label("Исполнитель:"), 3, 0, Qt.AlignCenter)
        self.combo_artist = QComboBox()
        self.combo_artist.setEditable(True)
        self.combo_artist.currentTextChanged.connect(self._sync_album_suggestions)
        grid.addWidget(self.combo_artist, 3, 1, 1, 3)

        grid.addWidget(self._make_label("Альбом:"), 4, 0, Qt.AlignCenter)
        self.combo_album = QComboBox()
        self.combo_album.setEditable(True)
        grid.addWidget(self.combo_album, 4, 1, 1, 3)

        grid.addWidget(self._make_label("Год:"), 5, 0, Qt.AlignCenter)
        row_year_genre = QHBoxLayout()
        row_year_genre.setSpacing(6)

        self.combo_year = QComboBox()
        self.combo_year.setEditable(True)
        self.combo_year.setFixedWidth(80)
        row_year_genre.addWidget(self.combo_year)

        row_year_genre.addSpacing(6)
        row_year_genre.addWidget(self._make_label("Жанр:"))
        self.combo_genre = QComboBox()
        self.combo_genre.setEditable(True)
        row_year_genre.addWidget(self.combo_genre, stretch=1)
        grid.addLayout(row_year_genre, 5, 1, 1, 3)

        grid.addWidget(self._make_label("Исп. альбома:"), 6, 0, Qt.AlignCenter)
        self.combo_album_artist = QComboBox()
        self.combo_album_artist.setEditable(True)
        grid.addWidget(self.combo_album_artist, 6, 1, 1, 3)

        grid.addWidget(self._make_label("Комментарий:"), 7, 0, Qt.AlignCenter | Qt.AlignTop)
        self.edit_comment = QTextEdit()
        self.edit_comment.setFixedHeight(75)
        grid.addWidget(self.edit_comment, 7, 1, 1, 3)

        grid.addWidget(self._make_label("Текст песни:"), 8, 0, Qt.AlignCenter | Qt.AlignTop)
        self.edit_lyrics = QTextEdit()
        self.edit_lyrics.setFixedHeight(160)
        grid.addWidget(self.edit_lyrics, 8, 1, 1, 3)

        row_content.addWidget(box_meta, stretch=1)
        layout.addLayout(row_content)

        for cb in [self.combo_title, self.combo_artist, self.combo_album,
                   self.combo_genre, self.combo_year, self.combo_album_artist]:
            if cb.lineEdit():
                cb.lineEdit().setAlignment(Qt.AlignCenter)

        layout.addSpacing(4)
        self.chk_disk_save = QCheckBox("Сохранять сразу в файлы на диске")
        layout.addWidget(self.chk_disk_save)

        self.btn_apply = QPushButton("✓ Применить изменения")
        self.btn_apply.setFixedHeight(34)
        self.btn_apply.setStyleSheet(PRIMARY_BTN_QSS)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        layout.addWidget(self.btn_apply)

        scroll.setWidget(container)
        root.addWidget(scroll)
        self.setEnabled(False)

    @staticmethod
    def _make_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        return lbl

    def set_track_data(self, tracks: List[Track]) -> None:
        self._current_tracks = tracks
        self._cover_deleted_flag = False

        if not tracks:
            self.setEnabled(False)
            self.lbl_mode_info.setText("Трек не выбран")
            self.cover_label.set_cover_bytes(None)
            self._clear_all_fields()
            return

        self.setEnabled(True)
        is_single = (len(tracks) == 1)
        first = tracks[0]
        meta = first.metadata

        current_art = first.metadata.album_artist or first.effective_artist
        current_alb = first.effective_album
        self.cover_label.set_library_context(current_art, current_alb, self._cached_covers)

        if first.is_cover_deleted:
            self.cover_label.set_cover_bytes(None)
        elif first.custom_cover_bytes:
            self.cover_label.set_cover_bytes(first.custom_cover_bytes)
        elif self._cover_reader:
            try:
                self.cover_label.set_cover_bytes(self._cover_reader(first.source_path))
            except Exception:
                self.cover_label.set_cover_bytes(None)

        alb_key = (first.master_album or first.effective_album or "").strip().lower()
        art_key = (first.metadata.album_artist or first.effective_artist or "").strip().lower()
        album_track_count = sum(
            1 for t in self._all_library_tracks
            if (t.master_album or t.effective_album or "").strip().lower() == alb_key
            and (t.metadata.album_artist or t.effective_artist or "").strip().lower() == art_key
        )

        if not is_single:
            self.lbl_mode_info.setText(f"📁 Пакетное редактирование ({len(tracks)} треков)")

            self.edit_filename.setEnabled(False)
            self.edit_filename.setText(f"<Выбрано треков: {len(tracks)}>")
            self._initial_edit_filename = ""

            self.combo_title.setEnabled(False)
            self.combo_title.clear()
            self.combo_title.setEditText("<Разные названия треков>")

            self.edit_track_num.setEnabled(False)
            self.edit_track_num.setText("-")

            artists = {t.metadata.artist for t in tracks if t.metadata.artist}
            albums = {t.metadata.album for t in tracks if t.metadata.album}
            album_artists = {t.metadata.album_artist for t in tracks if t.metadata.album_artist}
            genres = {t.metadata.genre for t in tracks if t.metadata.genre}
            years = {str(t.metadata.year) for t in tracks if t.metadata.year}
            comments = {t.metadata.comment for t in tracks if t.metadata.comment}

            tot_trks = {
                (t.metadata.total_tracks or (t.export_metadata.total_tracks if t.export_metadata else None))
                for t in tracks
            }
            tot_trks.discard(None)

            if len(tot_trks) == 1:
                self.edit_total_tracks.setText(str(tot_trks.pop()))
            elif album_track_count > 0 and len({t.effective_album for t in tracks}) == 1:
                self.edit_total_tracks.setText(str(album_track_count))
            else:
                self.edit_total_tracks.setText("")

            disc_nums = {t.metadata.disc_number for t in tracks if t.metadata.disc_number}
            self.edit_disc_num.setText(str(disc_nums.pop()) if len(disc_nums) == 1 else "")

            tot_discs = {t.metadata.total_discs for t in tracks if t.metadata.total_discs}
            self.edit_total_discs.setText(str(tot_discs.pop()) if len(tot_discs) == 1 else "")

            self.edit_comment.setPlainText(comments.pop() if len(comments) == 1 else "")
            self.edit_comment.setAlignment(Qt.AlignCenter)

            self.edit_lyrics.setEnabled(False)
            self.edit_lyrics.clear()
            self.edit_lyrics.setPlaceholderText("<Текст песен доступен для одного трека>")

            common_art = list(artists)[0] if len(artists) == 1 else ""
            common_alb = list(albums)[0] if len(albums) == 1 else ""
            common_alb_art = list(album_artists)[0] if len(album_artists) == 1 else ""
            common_genre = list(genres)[0] if len(genres) == 1 else ""
            common_year = list(years)[0] if len(years) == 1 else ""

            sugg = self._get_library_suggestions(common_art)

            self._fill_combo(self.combo_artist, common_art, sugg["artists"], is_multiple=(len(artists) != 1))
            self._fill_combo(self.combo_album, common_alb, sugg["albums"], is_multiple=(len(albums) != 1))
            self._fill_combo(self.combo_album_artist, common_alb_art, sugg["album_artists"],
                             is_multiple=(len(album_artists) != 1))
            self._fill_combo(self.combo_genre, common_genre, sugg["genres"], is_multiple=(len(genres) != 1))
            self._fill_combo(self.combo_year, common_year, sugg["years"], is_multiple=(len(years) != 1))

        else:
            current_fn = first.current_filename
            self._initial_edit_filename = current_fn

            self.lbl_mode_info.setText(f"🎵 Редактирование трека: {current_fn}")
            self.edit_filename.setEnabled(True)
            self.edit_filename.setText(current_fn)

            self.combo_title.setEnabled(True)
            self.edit_track_num.setEnabled(True)

            eff_total = (
                meta.total_tracks
                or (first.export_metadata.total_tracks if first.export_metadata else None)
                or (album_track_count if album_track_count > 0 else None)
            )
            eff_num = meta.track_number or (first.export_metadata.track_number if first.export_metadata else None)

            self.edit_track_num.setText(str(eff_num) if eff_num else "")
            self.edit_total_tracks.setText(str(eff_total) if eff_total else "")
            self.edit_disc_num.setText(str(meta.disc_number) if meta.disc_number else "")
            self.edit_total_discs.setText(str(meta.total_discs) if meta.total_discs else "")

            self.edit_comment.setPlainText(meta.comment or "")
            self.edit_comment.setAlignment(Qt.AlignCenter)

            self.edit_lyrics.setEnabled(True)
            self.edit_lyrics.setPlainText(meta.lyrics or "")
            self.edit_lyrics.setAlignment(Qt.AlignCenter)

            self.combo_title.clear()
            versions: Set[str] = set()
            target_nuc = first.normalized_title

            for t in self._all_library_tracks:
                title_val = (t.metadata.title or "").strip()
                if not title_val:
                    continue
                if target_nuc and t.normalized_title == target_nuc:
                    versions.add(title_val)

            cur_title = meta.title or first.source_path.stem
            if cur_title:
                versions.add(cur_title.strip())

            versions_list = sorted(versions, key=lambda s: s.lower())
            self._fill_combo(self.combo_title, cur_title, versions_list, is_multiple=False)

            current_track_art = meta.artist or current_art
            current_track_alb = meta.album or current_alb
            current_track_alb_art = meta.album_artist or current_art

            sugg = self._get_library_suggestions(current_track_art)

            self._fill_combo(self.combo_artist, current_track_art, sugg["artists"], is_multiple=False)
            self._fill_combo(self.combo_album, current_track_alb, sugg["albums"], is_multiple=False)
            self._fill_combo(self.combo_album_artist, current_track_alb_art, sugg["album_artists"], is_multiple=False)
            self._fill_combo(self.combo_genre, meta.genre or "", sugg["genres"], is_multiple=False)
            self._fill_combo(self.combo_year, str(meta.year or ""), sugg["years"], is_multiple=False)

    def _clear_all_fields(self) -> None:
        self.edit_filename.clear()
        self.edit_track_num.clear()
        self.edit_total_tracks.clear()
        self.edit_disc_num.clear()
        self.edit_total_discs.clear()
        self.combo_title.clear()
        self.combo_artist.clear()
        self.combo_album.clear()
        self.combo_album_artist.clear()
        self.combo_genre.clear()
        self.combo_year.clear()
        self.edit_comment.clear()
        self.edit_lyrics.clear()

    def update_live_field(self, track: Track, field_name: str, new_value: object) -> None:
        if not self._current_tracks or track not in self._current_tracks:
            return

        is_single = (len(self._current_tracks) == 1)
        val_str = str(new_value or "")

        if field_name == "title" and is_single:
            self.combo_title.setEditText(val_str)
        elif field_name == "artist":
            self.combo_artist.setEditText(val_str)
        elif field_name == "album_artist":
            self.combo_album_artist.setEditText(val_str)
        elif field_name == "album":
            self.combo_album.setEditText(val_str)
        elif field_name == "genre":
            self.combo_genre.setEditText(val_str)
        elif field_name == "year":
            self.combo_year.setEditText(val_str)
        elif field_name == "comment":
            self.edit_comment.setPlainText(val_str)
            self.edit_comment.setAlignment(Qt.AlignCenter)
        elif field_name == "lyrics" and is_single:
            self.edit_lyrics.setPlainText(val_str)
            self.edit_lyrics.setAlignment(Qt.AlignCenter)
        elif field_name == "track_number":
            self.edit_track_num.setText(val_str)
        elif field_name == "total_tracks":
            self.edit_total_tracks.setText(val_str)
        elif field_name == "disc_number":
            self.edit_disc_num.setText(val_str)
        elif field_name == "total_discs":
            self.edit_total_discs.setText(val_str)

    def _on_apply_clicked(self) -> None:
        if not self._current_tracks:
            return

        is_single = (len(self._current_tracks) == 1)

        year_text = self.combo_year.currentText().strip()
        year_val = int(year_text) if year_text.isdigit() else None

        tr_num_text = self.edit_track_num.text().strip()
        tr_num_val = int(tr_num_text) if tr_num_text.isdigit() else None

        tr_tot_text = self.edit_total_tracks.text().strip()
        tr_tot_val = int(tr_tot_text) if tr_tot_text.isdigit() else None

        disc_num_text = self.edit_disc_num.text().strip()
        disc_num_val = int(disc_num_text) if disc_num_text.isdigit() else None

        disc_tot_text = self.edit_total_discs.text().strip()
        disc_tot_val = int(disc_tot_text) if disc_tot_text.isdigit() else None

        data: Dict[str, Any] = {
            "cover": self.cover_label.get_cover_bytes(),
            "cover_deleted": self._cover_deleted_flag,
            "is_album_cover": self.chk_album_cover.isChecked()
        }

        art_text = self.combo_artist.currentText().strip()
        if art_text != MULTIPLE_VALUES_PLACEHOLDER:
            data["artist"] = art_text

        alb_art_text = self.combo_album_artist.currentText().strip()
        if alb_art_text != MULTIPLE_VALUES_PLACEHOLDER:
            data["album_artist"] = alb_art_text

        alb_text = self.combo_album.currentText().strip()
        if alb_text != MULTIPLE_VALUES_PLACEHOLDER:
            data["album"] = alb_text

        gen_text = self.combo_genre.currentText().strip()
        if gen_text != MULTIPLE_VALUES_PLACEHOLDER:
            data["genre"] = gen_text

        if year_text != MULTIPLE_VALUES_PLACEHOLDER:
            data["year"] = year_val

        comm_text = self.edit_comment.toPlainText().strip()
        if comm_text != MULTIPLE_VALUES_PLACEHOLDER:
            data["comment"] = comm_text

        if tr_tot_val is not None:
            data["total_tracks"] = tr_tot_val
        if disc_num_val is not None:
            data["disc_number"] = disc_num_val
        if disc_tot_val is not None:
            data["total_discs"] = disc_tot_val

        if is_single:
            data["title"] = self.combo_title.currentText().strip()
            data["track_number"] = tr_num_val
            data["lyrics"] = self.edit_lyrics.toPlainText().strip()

            custom_fn = self.edit_filename.text().strip()
            if custom_fn and custom_fn != getattr(self, "_initial_edit_filename", ""):
                data["filename"] = custom_fn

        self.apply_tags_requested.emit(data, self.chk_disk_save.isChecked())

    def _on_renumber_clicked(self) -> None:
        if not self._current_tracks:
            return
        first = self._current_tracks[0]
        alb_key = (first.master_album or first.effective_album or "").strip().lower()
        art_key = (first.metadata.album_artist or first.effective_artist or "").strip().lower()

        album_tracks = [
            t for t in self._all_library_tracks
            if (t.master_album or t.effective_album or "").strip().lower() == alb_key
            and (t.metadata.album_artist or t.effective_artist or "").strip().lower() == art_key
        ]
        targets = album_tracks if album_tracks else self._current_tracks
        self.renumber_requested.emit(targets, self.chk_disk_save.isChecked())