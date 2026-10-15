"""
Сервис планирования целевых путей, очистки имен и подготовки экспортных метаданных.
Единая точка ответственности за пути и санитизацию имен файлов/папок.
"""
import re
from pathlib import Path
from typing import List, Dict, Optional, Set

from core.domain.models import Track
from core.domain.enums import GroupingMode, FlatNumberingStyle, TranslitMode
from core.interfaces.transliteration import ITransliterationService
from core.interfaces.normalizer import ITrackNormalizer


class PathPlannerService:
    def __init__(
        self,
        translit_service: ITransliterationService,
        normalizer: Optional[ITrackNormalizer] = None
    ):
        self._translit = translit_service
        self._normalizer = normalizer

    @staticmethod
    def sanitize(name: str) -> str:
        """Публичный метод безопасной очистки строки от запрещенных символов ФС."""
        if not name:
            return "Unknown"
        cleaned = re.sub(r'[\\/*?:"<>|]', "", str(name)).strip()
        return cleaned or "Unknown"

    # Алиас для обратной совместимости
    _sanitize = sanitize

    def plan_paths_and_metadata(
        self,
        tracks: List[Track],
        source_root: Path,
        grouping_mode: GroupingMode,
        track_template_str: str = "{index:02d} - {title}",
        album_template_str: str = "[{year}] {album}",
        flat_numbering: FlatNumberingStyle = FlatNumberingStyle.KEEP_ALBUM_INDEX,
        translit_mode: TranslitMode = TranslitMode.OFF,
        translit_metadata: bool = False,
        clean_title_index: bool = True,
        add_template_to_title: bool = False,
        strip_title_numbers: bool = False,
        apply_template_to_album_tag: bool = False,
        clean_feats: bool = False,
        clear_lyrics: bool = False,
        clean_title_junk: bool = True,
        embed_track_number: bool = True,
        formatting_enabled: bool = True,
    ) -> None:
        if not tracks:
            return

        # ----------------------------------------------------------------------
        # РЕЖИМ 1: Форматирование ВЫКЛЮЧЕНО (чистые пути без транслита и шаблонов)
        # ----------------------------------------------------------------------
        if not formatting_enabled:
            for t in tracks:
                base_art = self.sanitize(t.metadata.album_artist or t.effective_artist or "Unknown Artist")
                alb_name = self.sanitize(t.effective_album or "Unknown Album")
                fname = t.custom_filename if t.custom_filename else t.source_path.name

                if grouping_mode == GroupingMode.BY_METADATA:
                    t.target_relative_path = Path(base_art) / Path(alb_name) / fname
                elif grouping_mode in (GroupingMode.PLAYLIST, GroupingMode.FLAT_PLAYLIST):
                    t.target_relative_path = Path(alb_name) / fname
                elif grouping_mode == GroupingMode.AS_IS:
                    try:
                        rel_parent = t.source_path.parent.relative_to(source_root)
                        t.target_relative_path = rel_parent / fname
                    except Exception:
                        t.target_relative_path = Path(fname)
                else:  # FLAT
                    t.target_relative_path = Path(fname)

                t.export_metadata = t.metadata.clone()
            return

        # ----------------------------------------------------------------------
        # РЕЖИМ 2: Форматирование ВКЛЮЧЕНО (шаблоны, нумерация, очистка мусора)
        # ----------------------------------------------------------------------
        artist_album_chrono = self._calculate_album_chronology(tracks)

        # Группировка альбомов и вычисление единого года (чтобы треки разных годов не дробили релиз)
        album_groups: Dict[tuple, List[Track]] = {}
        for t in tracks:
            base_art = re.split(r"(?i)\s+(?:feat\.?|ft\.?|и|&|with|and)\s+", t.effective_artist)[0].strip()
            alb_name = t.master_album if t.master_album else t.effective_album
            key = (base_art, alb_name)
            album_groups.setdefault(key, []).append(t)

        album_canonical_years: Dict[tuple, Optional[int]] = {}
        for key, alb_tracks in album_groups.items():
            years = [t.metadata.year for t in alb_tracks if t.metadata.year and t.metadata.year > 0]
            album_canonical_years[key] = max(set(years), key=years.count) if years else None

        # Динамическая нумерация только активных треков
        calculated_indices: Dict[str, tuple] = {}
        for key, alb_tracks in album_groups.items():
            active_in_album = [t for t in alb_tracks if not t.is_excluded_from_export]
            active_in_album.sort(key=lambda x: (
                0 if x.effective_album == (x.master_album or x.effective_album) else 1,
                x.metadata.track_number or 999,
                str(x.source_path.name)
            ))
            total_active = len(active_in_album)

            for idx, t in enumerate(active_in_album, start=1):
                calculated_indices[t.track_id] = (idx, total_active)

            for t in alb_tracks:
                if t.track_id not in calculated_indices:
                    calculated_indices[t.track_id] = (
                        t.metadata.track_number or 0,
                        total_active or len(alb_tracks)
                    )

        global_idx = 1
        for t in tracks:
            base_art = re.split(r"(?i)\s+(?:feat\.?|ft\.?|и|&|with|and)\s+", t.effective_artist)[0].strip()
            art_folder = self.sanitize(base_art)
            alb_name = t.master_album if t.master_album else t.effective_album

            canonical_year = album_canonical_years.get((base_art, alb_name)) or t.metadata.year
            chrono_i = artist_album_chrono.get((base_art, alb_name), 1)
            formatted_album = self.format_album_name(alb_name, canonical_year, album_template_str, chrono_i)

            calc_num, calc_tot = calculated_indices.get(
                t.track_id, (t.metadata.track_number or 1, t.metadata.total_tracks or 1)
            )

            if flat_numbering == FlatNumberingStyle.CONTINUOUS_GLOBAL:
                effective_idx = global_idx if not t.is_excluded_from_export else (t.metadata.track_number or 0)
            else:
                effective_idx = calc_num

            # Очистка названия: если есть нормализатор — убираем интернет-мусор, сохраняя числа вроде "18 мне уже"
            raw_title = t.metadata.title or t.source_path.stem
            if clean_title_junk and self._normalizer:
                clean_title = self._normalizer.clean_track_title(raw_title)
            else:
                clean_title = self._strip_track_prefix(raw_title)

            if t.custom_filename:
                filename_stem = Path(t.custom_filename).stem
                ext = Path(t.custom_filename).suffix or t.source_path.suffix
            else:
                filename_stem = self._apply_track_naming(
                    template=track_template_str,
                    index=effective_idx,
                    title=clean_title,
                    artist=base_art,
                    embed_number=embed_track_number
                )
                ext = t.source_path.suffix

            # Транслит путей ТОЛЬКО если translit_mode != OFF
            if translit_mode != TranslitMode.OFF:
                art_folder = self._translit.transform(art_folder, translit_mode)
                formatted_album = self._translit.transform(formatted_album, translit_mode)
                filename_stem = self._translit.transform(filename_stem, translit_mode)

            # Маршрутизация папок
            if grouping_mode == GroupingMode.BY_METADATA:
                t.target_relative_path = Path(art_folder) / Path(formatted_album) / f"{filename_stem}{ext}"
            elif grouping_mode in (GroupingMode.PLAYLIST, GroupingMode.FLAT_PLAYLIST):
                playlist_folder = self.sanitize(alb_name)
                t.target_relative_path = Path(playlist_folder) / f"{filename_stem}{ext}"
            elif grouping_mode == GroupingMode.AS_IS:
                try:
                    rel_parent = t.source_path.parent.relative_to(source_root)
                    t.target_relative_path = rel_parent / f"{filename_stem}{ext}"
                except Exception:
                    t.target_relative_path = Path(f"{filename_stem}{ext}")
            else:  # FLAT
                t.target_relative_path = Path(f"{filename_stem}{ext}")

            # Формирование экспортных тегов
            exp_meta = t.metadata.clone()
            exp_meta.track_number = effective_idx
            exp_meta.total_tracks = calc_tot
            exp_meta.album = formatted_album if apply_template_to_album_tag else alb_name

            if strip_title_numbers:
                exp_meta.title = clean_title
            elif add_template_to_title:
                exp_meta.title = f"{effective_idx:02d}. {clean_title}" if effective_idx else clean_title
            else:
                exp_meta.title = clean_title

            if clean_feats:
                exp_meta.artist = exp_meta.album_artist or base_art

            if clear_lyrics:
                exp_meta.lyrics = ""

            if translit_metadata and translit_mode != TranslitMode.OFF:
                exp_meta.title = self._translit.transform(exp_meta.title, translit_mode)
                exp_meta.artist = self._translit.transform(exp_meta.artist, translit_mode)
                exp_meta.album = self._translit.transform(exp_meta.album, translit_mode)
                exp_meta.album_artist = self._translit.transform(exp_meta.album_artist, translit_mode)

            t.export_metadata = exp_meta

            if not t.is_excluded_from_export:
                global_idx += 1

    def _apply_track_naming(
        self,
        template: str,
        index: int,
        title: str,
        artist: str,
        embed_number: bool = True
    ) -> str:
        clean_title = self.sanitize(title)
        clean_artist = self.sanitize(artist)

        if not embed_number:
            if "{artist}" in template and "{title}" in template:
                return self.sanitize(f"{clean_artist} - {clean_title}")
            return self.sanitize(clean_title)

        try:
            name = template.format(index=index, title=clean_title, artist=clean_artist)
            return self.sanitize(name)
        except Exception:
            return f"{index:02d} - {clean_title}"

    @classmethod
    def format_album_name(cls, album_name: str, year: Optional[int], template: str, chrono_idx: int = 1) -> str:
        clean_album = cls.sanitize(album_name)
        if not template or template == "{album}":
            return clean_album

        y_str = str(year) if year and year > 0 else ""
        base_name = re.sub(rf"[\(\[]?\b{y_str}\b[\)\]]?", "", clean_album).strip(" -_") if y_str else clean_album
        if not base_name:
            base_name = clean_album

        try:
            res = template.format(year=y_str, album=base_name, chrono_idx=chrono_idx)
            return cls.sanitize(res).strip(" -_")
        except Exception:
            return f"[{y_str}] {base_name}" if y_str else base_name

    def _calculate_album_chronology(self, tracks: List[Track]) -> Dict[tuple, int]:
        artist_albums: Dict[str, Set[str]] = {}
        album_years: Dict[tuple, int] = {}

        for t in tracks:
            base_art = re.split(r"(?i)\s+(?:feat\.?|ft\.?|и|&|with|and)\s+", t.effective_artist)[0].strip()
            alb = t.master_album or t.effective_album
            artist_albums.setdefault(base_art, set()).add(alb)
            year = t.metadata.year if t.metadata.year else 9999
            album_years[(base_art, alb)] = min(album_years.get((base_art, alb), 9999), year)

        chrono_dict: Dict[tuple, int] = {}
        for artist, albums in artist_albums.items():
            sorted_albums = sorted(albums, key=lambda a: album_years.get((artist, a), 9999))
            for idx, a in enumerate(sorted_albums, start=1):
                chrono_dict[(artist, a)] = idx
        return chrono_dict

    @staticmethod
    def _strip_track_prefix(title: str) -> str:
        cleaned = re.sub(r"^(?:\[?\d+\]?[\.\-_/]+\s*|\(\d+\)\s*|0\d+\s+)", "", str(title)).strip()
        return cleaned or str(title)