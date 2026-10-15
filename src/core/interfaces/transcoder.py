"""Контракт аудио-транскодера (конвертера звука)."""
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from core.domain.enums import AudioFormat


@dataclass(frozen=True)
class EncodeSettings:
    """Неизменяемый набор параметров конвертации аудиопотока."""
    target_format: AudioFormat
    is_vbr: bool = False
    bitrate_kbps: int = 320
    vbr_quality: int = 0                  # 0 (максимальное качество) .. 9 (минимальное)
    normalize_volume: bool = False        # EBU R128 (-14 LUFS)
    sample_rate_hz: Optional[int] = None  # Частота дискретизации (Гц), None — как в источнике
    sample_format: Optional[str] = None   # "s16", "s24", "s32", "flt", None — как в источнике
    channels: Optional[int] = None        # 1 — Mono, 2 — Stereo, 6 — 5.1


class IAudioTranscoder(ABC):
    """Интерфейс внешнего кодировщика аудиофайлов."""

    @abstractmethod
    def transcode(self, source: Path, destination: Path, settings: EncodeSettings) -> None:
        """
        Перекодирует файл source в целевой destination согласно settings.
        При ошибках процесса транскодирования выбрасывает RuntimeError с логом.
        """
        pass