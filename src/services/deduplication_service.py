"""
Сервис интеллектуальной дедупликации фонотеки и управления мастер-релизами.
"""
import re
from typing import List, Dict, Tuple, Sequence, Optional
from dataclasses import dataclass, field
from core.domain.models import Track
from core.domain.enums import DuplicateStatus
from core.interfaces.normalizer import ITrackNormalizer
import logging

logger = logging.getLogger("MusicFormator")


@dataclass(frozen=True)
class DeduplicationRules:
    single_patterns: Sequence[str] = field(default_factory=lambda: [
        r"(?i)\b(?:single|сингл|ep|еп|maxi|макси|maxi-single|макси-сингл)\b",
        r"(?i)[\(\[]\s*(?:single|сингл|ep|еп|maxi)\s*[\)\]]"
    ])
    compilation_markers: Sequence[str] = field(default_factory=lambda: [
        "best", "лучшее", "collection", "greatest", "hits", "сборник", "various", "remixes", "хиты"
    ])
    bonus_markers: Sequence[str] = field(default_factory=lambda: [
        "bonus", "бонус", "deluxe", "remaster", "reissue", "edition", "extended",
        "special", "maschina", "vol", "limited", "переиздание", "юбилейное",
        "новые песни", "новый трек", "new tracks"
    ])


class DeduplicationService:
    def __init__(self, normalizer: ITrackNormalizer, rules: DeduplicationRules = DeduplicationRules()):
        self._normalizer = normalizer
        self._rules = rules
        self._album_track_counts: Dict[Tuple[str, str], int] = {}

    def process_library(
            self,
            tracks: List[Track],
            merge_duplicate_albums: bool = False,
            merge_singles: bool = False
    ) -> None:
        if not tracks:
            return

        self._album_track_counts.clear()
        for t in tracks:
            art_k = self._normalizer.super_clean(self._get_base_artist(t))
            alb_k = t.effective_album.strip().lower()
            self._album_track_counts[(art_k, alb_k)] = self._album_track_counts.get((art_k, alb_k), 0) + 1

        self._process_album_duplicates(tracks, merge_duplicate_albums)

        # СЛИЯНИЕ СИНГЛОВ (Агрессивное)
        if merge_singles:
            for t in tracks:
                art_k = self._normalizer.super_clean(self._get_base_artist(t))
                alb_k = t.effective_album.strip().lower()
                track_count = self._album_track_counts.get((art_k, alb_k), 1)

                tier = self._get_release_tier(t.effective_album)
                master_tier = self._get_release_tier(t.master_album)

                # Объединяем, если 1-2 трека (но не сборник/переиздание) ИЛИ если есть слово Single/EP
                if tier == 3 or master_tier == 3 or (track_count <= 2 and tier not in (1, 2)):
                    t.master_album = "Singles"

        self._assign_hierarchical_track_statuses(tracks)

    def _get_release_tier(self, album_name: str) -> int:
        if not album_name or not album_name.strip():
            return 4
        lowered = album_name.lower().strip()

        for pattern in self._rules.single_patterns:
            if re.search(pattern, lowered):
                return 3

        if re.search(r"\+\s*\d+\s*(нов|песн|трек|bonus|track)", lowered):
            return 1
        if any(m in lowered for m in self._rules.compilation_markers):
            return 2
        if any(m in lowered for m in self._rules.bonus_markers):
            return 1
        return 0

    def _get_title_priority(self, track: Track) -> int:
        if track.is_karaoke:
            return 6

        title_lower = (track.metadata.title or "").lower()
        versions_lower = [v.lower() for v in track.detected_version_tags]

        is_remix = any(
            k in title_lower or any(k in v for v in versions_lower)
            for k in ("remix", "megamix", "club mix", "dub", "vip", "live", "concert",
                      "bootleg", "mashup", "rework", "cover", "tribute", "demo", "session")
        )
        if is_remix:
            return 5

        if track.detected_feats or re.search(r"(?i)\b(?:feat\.?|ft\.?|featuring|с\s+уч\.?|при\s+уч\.?|дуэт)\b",
                                             title_lower):
            return 4

        if any(k in title_lower or any(k in v for v in versions_lower) for k in
               ("radio edit", "radio mix", "single edit", "single version")):
            return 3

        if any(k in title_lower or any(k in v for v in versions_lower) for k in ("acoustic", "акустика", "unplugged")):
            return 2

        if any(k in title_lower or any(k in v for v in versions_lower) for k in
               ("original mix", "full edit", "full version", "album version", "extended")):
            return 1

        if track.detected_version_tags:
            return 5

        return 0

    def _calculate_track_weight(self, track: Track) -> tuple:
        title_prio = self._get_title_priority(track)
        year = track.metadata.year if (track.metadata.year and track.metadata.year > 0) else 9999

        art_k = self._normalizer.super_clean(self._get_base_artist(track))
        alb_k = track.effective_album.strip().lower()
        track_count = self._album_track_counts.get((art_k, alb_k), 1)
        is_full_album = 0 if track_count > 4 else 1

        album_tier = self._get_release_tier(track.effective_album)
        is_from_master = 0 if getattr(track, "_is_master_album", False) else 1

        track_num = track.metadata.track_number or 999
        name_length = len(track.metadata.title or "")

        return (
            title_prio,
            year,
            is_full_album,
            album_tier,
            is_from_master,
            track_num,
            name_length
        )

    def _get_version_signature(self, track: Track) -> tuple:
        prio = self._get_title_priority(track)
        if prio == 0:
            return ("ORIGINAL",)
        if prio == 1:
            return ("EXTENDED",)
        if prio == 2:
            return ("ACOUSTIC",)
        if prio == 3:
            return ("RADIO",)
        if prio == 4:
            clean_feats = tuple(sorted(self._normalizer.super_clean(f) for f in track.detected_feats))
            return ("FEAT", clean_feats)
        if prio == 5:
            clean_vers = tuple(sorted(self._normalizer.super_clean(v) for v in track.detected_version_tags))
            return ("REMIX", clean_vers)
        return ("KARAOKE",)

    def _assign_hierarchical_track_statuses(self, tracks: List[Track]) -> None:
        song_families: Dict[Tuple[str, str], List[Track]] = {}
        for t in tracks:
            art_k = self._normalizer.super_clean(self._get_base_artist(t))
            key = (art_k, t.normalized_title)
            song_families.setdefault(key, []).append(t)

        for (art_k, nuc_title), family in song_families.items():
            if len(family) == 1:
                t = family[0]
                prio = self._get_title_priority(t)
                if prio == 6:
                    t.duplicate_status = DuplicateStatus.KARAOKE
                elif prio == 5:
                    t.duplicate_status = DuplicateStatus.REMIX
                elif prio == 4:
                    t.duplicate_status = DuplicateStatus.FEAT
                else:
                    t.duplicate_status = DuplicateStatus.ORIGINAL
                t.original_track_ref = None
                continue

            family.sort(key=self._calculate_track_weight)

            master_track = family[0]
            master_prio = self._get_title_priority(master_track)
            if master_prio == 6:
                master_track.duplicate_status = DuplicateStatus.KARAOKE
            elif master_prio == 5:
                master_track.duplicate_status = DuplicateStatus.REMIX
            elif master_prio == 4:
                master_track.duplicate_status = DuplicateStatus.FEAT
            else:
                master_track.duplicate_status = DuplicateStatus.ORIGINAL
            master_track.original_track_ref = None

            version_registry: Dict[tuple, Track] = {}
            master_sig = self._get_version_signature(master_track)
            version_registry[master_sig] = master_track

            for other_track in family[1:]:
                sig = self._get_version_signature(other_track)
                prio = self._get_title_priority(other_track)

                if sig in version_registry:
                    other_track.duplicate_status = DuplicateStatus.DUPLICATE
                    other_track.original_track_ref = version_registry[sig]
                else:
                    if prio == 6:
                        other_track.duplicate_status = DuplicateStatus.KARAOKE
                    elif prio in (1, 2, 3, 5):
                        other_track.duplicate_status = DuplicateStatus.REMIX
                    elif prio == 4:
                        other_track.duplicate_status = DuplicateStatus.FEAT
                    else:
                        other_track.duplicate_status = DuplicateStatus.DUPLICATE
                        other_track.original_track_ref = master_track

                    version_registry[sig] = other_track

    def _process_album_duplicates(self, tracks: List[Track], merge_albums: bool) -> None:
        album_families: Dict[Tuple[str, str], List[Track]] = {}

        for t in tracks:
            art_k = self._normalizer.super_clean(self._get_base_artist(t)) or "global_collection"
            alb_clean = self._normalizer.clean_album_name(t.effective_album)
            key = (art_k, alb_clean)
            album_families.setdefault(key, []).append(t)

        for key, family in album_families.items():
            variants_dict: Dict[str, List[Track]] = {}
            for t in family:
                variants_dict.setdefault(t.effective_album, []).append(t)

            master_album_name = self._find_best_album_name(variants_dict)

            for t in family:
                t.master_album = master_album_name if merge_albums else t.effective_album
                t._is_master_album = (t.effective_album.strip().lower() == master_album_name.strip().lower())

    def _find_best_album_name(self, variants_dict: Dict[str, List[Track]]) -> str:
        def score(item: Tuple[str, List[Track]]) -> tuple:
            alb_name, trk_list = item
            tier = self._get_release_tier(alb_name)

            years = [t.metadata.year for t in trk_list if t.metadata.year and t.metadata.year > 0]
            earliest_year = min(years) if years else 9999

            is_full_album = 0 if len(trk_list) > 4 and tier == 0 else 1
            has_brackets = 1 if ("(" in alb_name or ")" in alb_name or "[" in alb_name or "]" in alb_name) else 0
            has_plus = 1 if "+" in alb_name else 0

            return (
                tier,
                earliest_year,
                is_full_album,
                has_plus,
                has_brackets,
                len(alb_name)
            )

        best_variant = sorted(variants_dict.items(), key=score)[0]
        return best_variant[0]

    @staticmethod
    def _get_base_artist(track: Track) -> str:
        artist_raw = track.metadata.album_artist or track.effective_artist
        return re.split(r"(?i)\s+(?:feat\.?|ft\.?|и|&|with|and)\s+", artist_raw)[0].strip()