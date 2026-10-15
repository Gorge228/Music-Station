"""
Сервис экспорта компактного текстового треклиста фонотеки со статусами.
"""
from typing import List
from pathlib import Path
from core.domain.models import Track


class AIListExporter:
    """Генератор текстовых списков треков фонотеки со статусами."""

    @staticmethod
    def generate_prompt_list(tracks: List[Track], output_file: Path) -> None:
        lines = []
        for track in tracks:
            if track.is_excluded_from_export:
                continue

            status_str = f"[{track.duplicate_status.name}]"
            year_str = f" ({track.metadata.year})" if track.metadata.year else ""

            # ФОРМАТ: [СТАТУС] Исполнитель — Альбом (Год) — Название
            line = (
                f"{status_str:<12} {track.effective_artist} — {track.effective_album}{year_str} — "
                f"{track.metadata.title or track.source_path.stem}"
            )
            lines.append(line)

        lines.sort()
        output_file.write_text("\n".join(lines), encoding="utf-8")