"""
Сервис управления историей действий (Undo / Redo) по паттерну Memento.
Фиксирует состояние фонотеки пачками, предотвращая лавинообразное засорение стека.
"""
from typing import List, Dict, Optional
from dataclasses import dataclass

from core.domain.models import Track, AudioMetadata
from core.domain.enums import DuplicateStatus


@dataclass(frozen=True)
class TrackSnapshot:
    """Неизменяемый снимок состояния отдельного трека."""
    metadata: AudioMetadata
    is_excluded: bool
    duplicate_status: DuplicateStatus
    master_album: str


@dataclass
class HistoryStep:
    """Шаг истории с описанием операции и снимками состояния затронутых треков."""
    description: str
    snapshots: Dict[str, TrackSnapshot]  # Ключ — стабильный track_id


class HistoryService:
    """Потокобезопасный менеджер истории отмен и повторов."""

    def __init__(self, max_depth: int = 40):
        self._max_depth = max_depth
        self._undo_stack: List[HistoryStep] = []
        self._redo_stack: List[HistoryStep] = []

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def record_state(self, tracks: List[Track], description: str = "Действие") -> None:
        """Сохраняет текущий снимок переданных треков перед выполнением мутации."""
        if not tracks:
            return

        snapshots: Dict[str, TrackSnapshot] = {}
        for t in tracks:
            snapshots[t.track_id] = TrackSnapshot(
                metadata=t.metadata.clone(),
                is_excluded=t.is_excluded_from_export,
                duplicate_status=t.duplicate_status,
                master_album=t.master_album
            )

        step = HistoryStep(description=description, snapshots=snapshots)
        self._undo_stack.append(step)

        if len(self._undo_stack) > self._max_depth:
            self._undo_stack.pop(0)

        self._redo_stack.clear()

    def undo(self, tracks: List[Track]) -> Optional[str]:
        """Откатывает состояние фонотеки назад на один шаг."""
        if not self.can_undo():
            return None

        # Фиксируем текущее состояние в стек Redo
        current_snapshots = {
            t.track_id: TrackSnapshot(
                metadata=t.metadata.clone(),
                is_excluded=t.is_excluded_from_export,
                duplicate_status=t.duplicate_status,
                master_album=t.master_album
            )
            for t in tracks
        }
        previous_step = self._undo_stack.pop()
        self._redo_stack.append(HistoryStep(description=previous_step.description, snapshots=current_snapshots))

        self._restore_tracks(tracks, previous_step.snapshots)
        return previous_step.description

    def redo(self, tracks: List[Track]) -> Optional[str]:
        """Возвращает отмененное действие вперед."""
        if not self.can_redo():
            return None

        current_snapshots = {
            t.track_id: TrackSnapshot(
                metadata=t.metadata.clone(),
                is_excluded=t.is_excluded_from_export,
                duplicate_status=t.duplicate_status,
                master_album=t.master_album
            )
            for t in tracks
        }
        next_step = self._redo_stack.pop()
        self._undo_stack.append(HistoryStep(description=next_step.description, snapshots=current_snapshots))

        self._restore_tracks(tracks, next_step.snapshots)
        return next_step.description

    def clear(self) -> None:
        """Сбрасывает стек истории (при открытии нового каталога)."""
        self._undo_stack.clear()
        self._redo_stack.clear()

    @staticmethod
    def _restore_tracks(tracks: List[Track], snapshots: Dict[str, TrackSnapshot]) -> None:
        for t in tracks:
            snap = snapshots.get(t.track_id)
            if snap:
                t.metadata = snap.metadata.clone()
                t.is_excluded_from_export = snap.is_excluded
                t.duplicate_status = snap.duplicate_status
                t.master_album = snap.master_album