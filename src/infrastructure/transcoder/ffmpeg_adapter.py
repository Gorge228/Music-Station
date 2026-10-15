"""
Адаптер кодировщика FFmpeg.
Реализует IAudioTranscoder. Перехватывает stderr при сбоях для полноценной отладки.
"""
import subprocess
import logging
from pathlib import Path
from core.domain.enums import AudioFormat
from core.interfaces.transcoder import IAudioTranscoder, EncodeSettings

logger = logging.getLogger("MusicFormator")


class FFmpegTranscoder(IAudioTranscoder):
    """Преобразователь аудиопотоков через системный вызов FFmpeg."""

    def transcode(self, source: Path, destination: Path, settings: EncodeSettings) -> None:
        # -map 0:a:0 выбирает первый основной аудиопоток источника
        cmd = ["ffmpeg", "-y", "-i", str(source), "-map", "0:a:0"]

        # 1. Фильтр громкости EBU R128
        if settings.normalize_volume:
            cmd.extend(["-af", "loudnorm=I=-14:LRA=11:TP=-1.5"])

        # 2. Каналы
        if settings.channels is not None and settings.channels > 0:
            cmd.extend(["-ac", str(settings.channels)])

        # 3. Частота дискретизации (Sample Rate)
        if settings.sample_rate_hz is not None and settings.sample_rate_hz > 0:
            cmd.extend(["-ar", str(settings.sample_rate_hz)])

        fmt = settings.target_format
        sfmt = settings.sample_format

        # 4. Выбор аудиокодека и битрейта
        if fmt == AudioFormat.MP3:
            cmd.extend(["-c:a", "libmp3lame"])
            if settings.is_vbr:
                cmd.extend(["-q:a", str(settings.vbr_quality)])
            else:
                cmd.extend(["-b:a", f"{settings.bitrate_kbps}k"])

        elif fmt == AudioFormat.AAC:
            cmd.extend(["-c:a", "aac"])
            if settings.is_vbr:
                aac_q = max(0.5, 2.0 - (settings.vbr_quality * 0.25))
                cmd.extend(["-q:a", str(aac_q)])
            else:
                cmd.extend(["-b:a", f"{settings.bitrate_kbps}k"])

        elif fmt == AudioFormat.OGG:
            cmd.extend(["-c:a", "libvorbis"])
            if settings.is_vbr:
                ogg_q = max(1, 9 - settings.vbr_quality)
                cmd.extend(["-q:a", str(ogg_q)])
            else:
                cmd.extend(["-b:a", f"{settings.bitrate_kbps}k"])

        elif fmt == AudioFormat.OPUS:
            cmd.extend(["-c:a", "libopus"])
            if settings.is_vbr:
                opus_b = max(64, 256 - (settings.vbr_quality * 32))
                cmd.extend(["-vbr", "on", "-b:a", f"{opus_b}k"])
            else:
                cmd.extend(["-vbr", "off", "-b:a", f"{settings.bitrate_kbps}k"])

        elif fmt == AudioFormat.WMA:
            cmd.extend(["-c:a", "wmav2", "-b:a", f"{settings.bitrate_kbps}k"])

        elif fmt == AudioFormat.FLAC:
            cmd.extend(["-c:a", "flac"])
            if sfmt in ("s16", "16"):
                cmd.extend(["-sample_fmt", "s16"])
            elif sfmt in ("s24", "24", "s32", "32"):
                cmd.extend(["-sample_fmt", "s32"])

        elif fmt == AudioFormat.ALAC:
            cmd.extend(["-c:a", "alac"])
            if sfmt in ("s16", "16"):
                cmd.extend(["-sample_fmt", "s16p"])
            elif sfmt in ("s24", "24", "s32", "32"):
                cmd.extend(["-sample_fmt", "s32p"])

        elif fmt == AudioFormat.WAV:
            if sfmt in ("s24", "24"):
                cmd.extend(["-c:a", "pcm_s24le"])
            elif sfmt in ("s32", "32"):
                cmd.extend(["-c:a", "pcm_s32le"])
            elif sfmt in ("flt", "f32"):
                cmd.extend(["-c:a", "pcm_f32le"])
            else:
                cmd.extend(["-c:a", "pcm_s16le"])
        else:
            cmd.extend(["-c:a", "copy"])

        cmd.append(str(destination))

        try:
            logger.debug(f"Запуск FFmpeg: {' '.join(cmd)}")
            # Захватываем stderr для возможности диагностики ошибки
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
        except FileNotFoundError:
            raise RuntimeError("Кодировщик FFmpeg не найден в системе (проверьте переменную окружения PATH)!")
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode("utf-8", errors="replace").strip() if e.stderr else str(e)
            logger.error(f"FFmpeg вернул ошибку при обработке {source.name}:\n{err_msg}")
            raise RuntimeError(f"Сбой FFmpeg при конвертации '{source.name}': {err_msg}")