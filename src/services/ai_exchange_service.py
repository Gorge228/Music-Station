"""
Сервис формирования структурированных промптов для нейросетей и парсинга ответов.
"""
import re
from typing import List, Dict, Tuple
from core.domain.models import Track
from core.domain.enums import DuplicateStatus


class AIExchangeService:
    """Генератор промптов музыкального аудита и парсер ответов нейросетей."""

    @classmethod
    def generate_prompt_payload(cls, tracks: List[Track], root_folder_name: str) -> str:
        total_count = len(tracks)
        lines = [
            f"=== ТРЕКЛИСТ ФОНОТЕКИ: {root_folder_name.upper()} (ВСЕГО ТРЕКОВ: {total_count}) ===",
            "Формат строки: [В плане: x/ ] | [ID] | СТАТУС | Исполнитель | Альбом | Год | № | Название | Жанр",
            "-" * 90
        ]

        for idx, t in enumerate(tracks, start=1):
            chk = "[ ]" if t.is_excluded_from_export else "[x]"
            meta = t.export_metadata or t.metadata
            status = t.duplicate_status.name
            artist = meta.artist or t.effective_artist
            album = meta.album or t.effective_album
            year = str(meta.year or "")
            tr_num = str(meta.track_number or "")
            title = meta.title or t.source_path.stem
            genre = meta.genre or "Unknown"

            lines.append(f"{chk} | [ID:{idx:03d}] | {status:<9} | {artist} | {album} | {year} | {tr_num} | {title} | {genre}")

        lines.append("-" * 90)
        lines.append(cls._get_prompt_instructions(root_folder_name, total_count))
        return "\n".join(lines)

    @classmethod
    def parse_and_apply_ai_response(cls, response_text: str, tracks: List[Track]) -> Tuple[int, List[str]]:
        track_map: Dict[int, Track] = {idx: t for idx, t in enumerate(tracks, start=1)}
        updated_count = 0
        errors: List[str] = []

        row_pattern = re.compile(
            r"^\s*\[([ xXvV✓+\-0])\]\s*\|\s*\[ID:(\d+)\]\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]+)\|\s*([^|\n\r]+)",
            re.MULTILINE
        )

        found_ids = set()

        for match in row_pattern.finditer(response_text):
            chk_raw, id_raw, status_raw, artist, album, year_raw, trk_raw, title, genre = match.groups()

            track_id = int(id_raw)
            if track_id not in track_map:
                continue

            found_ids.add(track_id)
            track = track_map[track_id]

            # 1. Чекбокс активности в плане
            track.is_excluded_from_export = chk_raw.strip().lower() not in ("x", "v", "✓", "+", "1")

            # 2. Статус
            st_clean = status_raw.strip().upper()
            if "DUP" in st_clean:
                track.duplicate_status = DuplicateStatus.DUPLICATE
            elif "FEAT" in st_clean:
                track.duplicate_status = DuplicateStatus.FEAT
            elif "REMIX" in st_clean:
                track.duplicate_status = DuplicateStatus.REMIX
            elif "KARAOKE" in st_clean:
                track.duplicate_status = DuplicateStatus.KARAOKE
            else:
                track.duplicate_status = DuplicateStatus.ORIGINAL

            # 3. Метаданные
            track.metadata.artist = artist.strip()
            track.metadata.album = album.strip()
            track.metadata.title = title.strip()
            track.metadata.genre = genre.strip()

            year_match = re.search(r"\b(19\d\d|20\d\d)\b", year_raw.strip())
            track.metadata.year = int(year_match.group(1)) if year_match else None

            trk_match = re.search(r"\b\d+\b", trk_raw.strip())
            track.metadata.track_number = int(trk_match.group(0)) if trk_match else None

            updated_count += 1

        if updated_count == 0:
            errors.append("Не удалось распознать строки треклиста. Проверьте разделители '|' и наличие [ID:XXX].")
        elif len(found_ids) < len(tracks):
            errors.append(f"Внимание: нейросеть пропустила {len(tracks) - len(found_ids)} треков.")

        return updated_count, errors

    @staticmethod
    def _get_prompt_instructions(folder_name: str, total_count: int) -> str:
        return f"""
ИНСТРУКЦИЯ ДЛЯ НЕЙРОСЕТИ:
1. Очисти названия альбомов от годов и приписок. Год указывай СТРОГО в колонке «Год».
2. Поставь [ ] для статуса DUPLICATE (повторы треков из сборников).
3. Определи жанры корректно по стилю исполнителя.
4. Верни ровно {total_count} строк в исходном формате с сохранением [ID:XXX]!
"""