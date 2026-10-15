"""
Низкоуровневый адаптер метаданных Mutagen.
Поддерживает MP3, MP4, FLAC, OGG, OPUS.
Автоматически распознает и восстанавливает битые кодировки (CP1251 -> Latin-1).
"""
import base64
import re
import logging
from pathlib import Path
from typing import Optional, Tuple

import mutagen
from mutagen.id3 import (
    ID3, TIT2, TPE1, TPE2, TALB, TDRC, TCON, TRCK, TPOS, COMM, APIC, USLT, ID3NoHeaderError
)
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus

from core.domain.models import AudioMetadata
from core.domain.enums import AudioFormat
from core.interfaces.metadata import IMetadataReader, IMetadataWriter
from core.interfaces.cover_art import ICoverArtHandler

logger = logging.getLogger("MusicFormator")


def fix_mojibake(text: str) -> str:
    """
    Автоматически восстанавливает русский текст из кракозябр вида:
    'Âñå âîçâðàùàåòñÿ' -> 'Все возвращается'
    """
    if not text or not isinstance(text, str):
        return ""
    try:
        # Пытаемся забрать «сырые» байты через latin1 и расшифровать в правильный cp1251
        raw_bytes = text.encode("latin1")
        decoded = raw_bytes.decode("cp1251")

        cyrillic_count = len(re.findall(r"[а-яА-ЯёЁ]", decoded))
        mojibake_count = len(re.findall(r"[\u00C0-\u00FF]", text))

        # Если в результате декодирования появились русские буквы,
        # а в исходнике были кракозябры из верхней таблицы Latin-1
        if cyrillic_count > 0 and (cyrillic_count >= mojibake_count * 0.7):
            return decoded
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text


class MutagenMetadataHandler(IMetadataReader, IMetadataWriter, ICoverArtHandler):
    """Адаптер для чтения и записи тегов и обложек через библиотеку mutagen."""

    def supports(self, path: Path) -> bool:
        fmt = AudioFormat.from_extension(path.suffix)
        return fmt in (
            AudioFormat.MP3, AudioFormat.FLAC, AudioFormat.M4A,
            AudioFormat.ALAC, AudioFormat.AAC, AudioFormat.OGG,
            AudioFormat.OPUS
        )

    # --------------------------------------------------------------------------
    # ЧТЕНИЕ ТЕГОВ (IMetadataReader)
    # --------------------------------------------------------------------------
    def read(self, path: Path) -> AudioMetadata:
        ext = path.suffix.lower()
        meta = AudioMetadata()

        try:
            if ext in (".m4a", ".mp4", ".aac", ".alac"):
                self._read_mp4(path, meta)
            elif ext == ".mp3":
                self._read_mp3(path, meta)
            elif ext == ".flac":
                self._read_flac(path, meta)
            elif ext == ".ogg":
                self._read_ogg(path, meta)
            elif ext == ".opus":
                self._read_opus(path, meta)
            else:
                self._read_generic(path, meta)
        except Exception as e:
            logger.warning(f"Ошибка при чтении тегов из {path.name}: {e}")

        if not meta.title:
            meta.title = fix_mojibake(path.stem)

        return meta

    def _read_mp4(self, path: Path, meta: AudioMetadata) -> None:
        audio = MP4(str(path))
        tags = audio.tags or {}

        meta.title = self._get_first_str(tags.get("\xa9nam"))
        meta.artist = self._get_first_str(tags.get("\xa9ART"))
        meta.album_artist = self._get_first_str(tags.get("aART"))
        meta.album = self._get_first_str(tags.get("\xa9alb"))
        meta.genre = self._get_first_str(tags.get("\xa9gen"))
        meta.year = self._extract_year(self._get_first_str(tags.get("\xa9day")))
        meta.comment = self._get_first_str(tags.get("\xa9cmt"))
        meta.lyrics = self._get_first_str(tags.get("\xa9lyr"))

        trkn = tags.get("trkn")
        if trkn and isinstance(trkn, list) and len(trkn) > 0:
            first_val = trkn[0]
            if isinstance(first_val, (tuple, list)):
                if len(first_val) >= 1 and first_val[0]:
                    meta.track_number = int(first_val[0])
                if len(first_val) >= 2 and first_val[1]:
                    meta.total_tracks = int(first_val[1])

        disk = tags.get("disk")
        if disk and isinstance(disk, list) and len(disk) > 0:
            first_val = disk[0]
            if isinstance(first_val, (tuple, list)):
                if len(first_val) >= 1 and first_val[0]:
                    meta.disc_number = int(first_val[0])
                if len(first_val) >= 2 and first_val[1]:
                    meta.total_discs = int(first_val[1])

        if audio.info:
            meta.duration_seconds = getattr(audio.info, "length", 0.0)
            meta.bitrate = getattr(audio.info, "bitrate", None)

    def _read_mp3(self, path: Path, meta: AudioMetadata) -> None:
        try:
            tags = ID3(str(path))
        except ID3NoHeaderError:
            tags = None

        if tags:
            meta.title = fix_mojibake(str(tags.get("TIT2", "")))
            meta.artist = fix_mojibake(str(tags.get("TPE1", "")))
            meta.album_artist = fix_mojibake(str(tags.get("TPE2", "")))
            meta.album = fix_mojibake(str(tags.get("TALB", "")))
            meta.genre = fix_mojibake(str(tags.get("TCON", "")))
            meta.year = self._extract_year(str(tags.get("TDRC", tags.get("TYER", ""))))

            trck_tag = tags.get("TRCK")
            if trck_tag:
                trck_val = trck_tag.text[0] if (hasattr(trck_tag, "text") and trck_tag.text) else str(trck_tag)
                meta.track_number, meta.total_tracks = self._parse_track_str(trck_val)

            if not meta.total_tracks:
                for txxx in tags.getall("TXXX"):
                    desc = (txxx.desc or "").lower().replace(" ", "_")
                    if desc in ("tracktotal", "totaltracks", "total_tracks") and txxx.text:
                        try:
                            meta.total_tracks = int(txxx.text[0])
                            break
                        except ValueError:
                            pass

            meta.disc_number, meta.total_discs = self._parse_track_str(str(tags.get("TPOS", "")))

            comm_tags = tags.getall("COMM")
            if comm_tags and comm_tags[0].text:
                meta.comment = fix_mojibake(str(comm_tags[0].text[0]))
            else:
                meta.comment = fix_mojibake(str(tags.get("COMM", "")))

            uslt_tags = tags.getall("USLT")
            if uslt_tags:
                meta.lyrics = fix_mojibake(str(uslt_tags[0].text))

        try:
            audio = MP3(str(path))
            if audio.info:
                meta.duration_seconds = getattr(audio.info, "length", 0.0)
                meta.bitrate = getattr(audio.info, "bitrate", None)
        except Exception:
            pass

    def _read_flac(self, path: Path, meta: AudioMetadata) -> None:
        audio = FLAC(str(path))
        tags = audio or {}

        meta.title = self._get_first_str(tags.get("title"))
        meta.artist = self._get_first_str(tags.get("artist"))
        meta.album_artist = self._get_first_str(tags.get("albumartist", tags.get("album artist")))
        meta.album = self._get_first_str(tags.get("album"))
        meta.genre = self._get_first_str(tags.get("genre"))
        meta.year = self._extract_year(self._get_first_str(tags.get("date")))
        meta.comment = self._get_first_str(tags.get("comment", tags.get("description")))
        meta.lyrics = self._get_first_str(tags.get("lyrics", tags.get("unsyncedlyrics")))
        meta.track_number, meta.total_tracks = self._parse_track_str(self._get_first_str(tags.get("tracknumber")))
        meta.disc_number, meta.total_discs = self._parse_track_str(self._get_first_str(tags.get("discnumber")))

        if not meta.total_tracks:
            for k in ("tracktotal", "totaltracks", "track_total", "total_tracks"):
                val = self._get_first_str(tags.get(k))
                if val:
                    try:
                        meta.total_tracks = int(val)
                        break
                    except ValueError:
                        pass

        if audio.info:
            meta.duration_seconds = getattr(audio.info, "length", 0.0)

    def _read_ogg(self, path: Path, meta: AudioMetadata) -> None:
        audio = OggVorbis(str(path))
        self._read_vorbis_dict(audio, meta)

    def _read_opus(self, path: Path, meta: AudioMetadata) -> None:
        audio = OggOpus(str(path))
        self._read_vorbis_dict(audio, meta)

    def _read_vorbis_dict(self, audio, meta: AudioMetadata) -> None:
        tags = audio or {}
        meta.title = self._get_first_str(tags.get("title"))
        meta.artist = self._get_first_str(tags.get("artist"))
        meta.album_artist = self._get_first_str(tags.get("albumartist", tags.get("album artist")))
        meta.album = self._get_first_str(tags.get("album"))
        meta.genre = self._get_first_str(tags.get("genre"))
        meta.year = self._extract_year(self._get_first_str(tags.get("date")))
        meta.comment = self._get_first_str(tags.get("comment", tags.get("description")))
        meta.lyrics = self._get_first_str(tags.get("lyrics"))
        meta.track_number, meta.total_tracks = self._parse_track_str(self._get_first_str(tags.get("tracknumber")))
        meta.disc_number, meta.total_discs = self._parse_track_str(self._get_first_str(tags.get("discnumber")))
        if audio.info:
            meta.duration_seconds = getattr(audio.info, "length", 0.0)

    def _read_generic(self, path: Path, meta: AudioMetadata) -> None:
        audio = mutagen.File(str(path))
        if not audio:
            return
        tags = getattr(audio, "tags", {}) or {}
        if hasattr(tags, "get"):
            meta.title = self._get_first_str(tags.get("title", tags.get("TIT2")))
            meta.artist = self._get_first_str(tags.get("artist", tags.get("TPE1")))
            meta.album = self._get_first_str(tags.get("album", tags.get("TALB")))

    # --------------------------------------------------------------------------
    # ЗАПИСЬ ТЕГОВ (IMetadataWriter)
    # --------------------------------------------------------------------------
    def write(self, path: Path, metadata: AudioMetadata, encoding: str = "utf-8") -> None:
        ext = path.suffix.lower()
        if ext == ".mp3":
            self._write_mp3(path, metadata, encoding)
        elif ext in (".m4a", ".mp4", ".aac", ".alac"):
            self._write_mp4(path, metadata)
        elif ext == ".flac":
            self._write_flac(path, metadata)
        elif ext == ".ogg":
            self._write_ogg(path, metadata)
        elif ext == ".opus":
            self._write_opus(path, metadata)
        else:
            raise NotImplementedError(f"Формат {ext} не поддерживает запись тегов через данный адаптер.")

    def _write_mp3(self, path: Path, metadata: AudioMetadata, encoding: str) -> None:
        try:
            tags = ID3(str(path))
        except ID3NoHeaderError:
            tags = ID3()

        id3_enc = 1 if encoding.lower() in ("utf-16", "utf16") else 3

        if metadata.title: tags["TIT2"] = TIT2(encoding=id3_enc, text=metadata.title)
        if metadata.artist: tags["TPE1"] = TPE1(encoding=id3_enc, text=metadata.artist)
        if metadata.album_artist: tags["TPE2"] = TPE2(encoding=id3_enc, text=metadata.album_artist)
        if metadata.album: tags["TALB"] = TALB(encoding=id3_enc, text=metadata.album)
        if metadata.year: tags["TDRC"] = TDRC(encoding=id3_enc, text=str(metadata.year))
        if metadata.genre: tags["TCON"] = TCON(encoding=id3_enc, text=metadata.genre)

        if metadata.track_number is not None:
            tr_str = f"{metadata.track_number}"
            if metadata.total_tracks:
                tr_str += f"/{metadata.total_tracks}"
            tags["TRCK"] = TRCK(encoding=id3_enc, text=tr_str)

        if metadata.disc_number is not None:
            dsc_str = f"{metadata.disc_number}"
            if metadata.total_discs:
                dsc_str += f"/{metadata.total_discs}"
            tags["TPOS"] = TPOS(encoding=id3_enc, text=dsc_str)

        if metadata.comment:
            tags["COMM::XXX"] = COMM(encoding=id3_enc, lang="XXX", desc="", text=metadata.comment)

        if metadata.lyrics:
            tags["USLT::XXX"] = USLT(encoding=id3_enc, lang="XXX", desc="", text=metadata.lyrics)

        tags.save(str(path), v2_version=3)

    def _write_mp4(self, path: Path, metadata: AudioMetadata) -> None:
        audio = MP4(str(path))
        if audio.tags is None:
            audio.add_tags()

        tags = audio.tags
        if metadata.title: tags["\xa9nam"] = [metadata.title]
        if metadata.artist: tags["\xa9ART"] = [metadata.artist]
        if metadata.album_artist: tags["aART"] = [metadata.album_artist]
        if metadata.album: tags["\xa9alb"] = [metadata.album]
        if metadata.year: tags["\xa9day"] = [str(metadata.year)]
        if metadata.genre: tags["\xa9gen"] = [metadata.genre]
        if metadata.comment: tags["\xa9cmt"] = [metadata.comment]
        if metadata.lyrics: tags["\xa9lyr"] = [metadata.lyrics]

        if metadata.track_number is not None:
            tags["trkn"] = [(metadata.track_number, metadata.total_tracks or 0)]
        if metadata.disc_number is not None:
            tags["disk"] = [(metadata.disc_number, metadata.total_discs or 0)]

        audio.save()

    def _write_flac(self, path: Path, metadata: AudioMetadata) -> None:
        audio = FLAC(str(path))
        self._write_vorbis_tags(audio, metadata)
        audio.save()

    def _write_ogg(self, path: Path, metadata: AudioMetadata) -> None:
        audio = OggVorbis(str(path))
        self._write_vorbis_tags(audio, metadata)
        audio.save()

    def _write_opus(self, path: Path, metadata: AudioMetadata) -> None:
        audio = OggOpus(str(path))
        self._write_vorbis_tags(audio, metadata)
        audio.save()

    @staticmethod
    def _write_vorbis_tags(audio, metadata: AudioMetadata) -> None:
        if metadata.title: audio["title"] = metadata.title
        if metadata.artist: audio["artist"] = metadata.artist
        if metadata.album_artist: audio["albumartist"] = metadata.album_artist
        if metadata.album: audio["album"] = metadata.album
        if metadata.year: audio["date"] = str(metadata.year)
        if metadata.genre: audio["genre"] = metadata.genre
        if metadata.comment: audio["comment"] = metadata.comment
        if metadata.lyrics: audio["lyrics"] = metadata.lyrics
        if metadata.track_number is not None: audio["tracknumber"] = str(metadata.track_number)
        if metadata.total_tracks is not None: audio["tracktotal"] = str(metadata.total_tracks)
        if metadata.disc_number is not None: audio["discnumber"] = str(metadata.disc_number)
        if metadata.total_discs is not None: audio["disctotal"] = str(metadata.total_discs)

    # --------------------------------------------------------------------------
    # РАБОТА С ОБЛОЖКАМИ (ICoverArtHandler)
    # --------------------------------------------------------------------------
    def read_cover(self, path: Path) -> Optional[bytes]:
        ext = path.suffix.lower()
        try:
            if ext == ".mp3":
                tags = ID3(str(path))
                apic = tags.getall("APIC")
                return apic[0].data if apic else None

            elif ext in (".m4a", ".mp4", ".alac"):
                tags = MP4(str(path)).tags
                if tags and "covr" in tags and tags["covr"]:
                    return bytes(tags["covr"][0])

            elif ext == ".flac":
                audio = FLAC(str(path))
                return audio.pictures[0].data if audio.pictures else None

            elif ext in (".ogg", ".opus"):
                audio = mutagen.File(str(path))
                if audio and "metadata_block_picture" in audio:
                    pics = audio["metadata_block_picture"]
                    if pics:
                        raw_b64 = pics[0]
                        pic = Picture(base64.b64decode(raw_b64))
                        return pic.data
        except Exception as e:
            logger.debug(f"Не удалось извлечь обложку из {path.name}: {e}")
        return None

    def write_cover(self, path: Path, cover_bytes: Optional[bytes]) -> None:
        ext = path.suffix.lower()
        try:
            if ext == ".mp3":
                try:
                    tags = ID3(str(path))
                except ID3NoHeaderError:
                    tags = ID3()
                tags.delall("APIC")
                if cover_bytes:
                    mime = "image/png" if cover_bytes.startswith(b"\x89PNG") else "image/jpeg"
                    tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=cover_bytes))
                tags.save(str(path), v2_version=3)

            elif ext in (".m4a", ".mp4", ".alac", ".aac"):
                audio = MP4(str(path))
                if audio.tags is None:
                    audio.add_tags()
                if cover_bytes:
                    fmt = MP4Cover.FORMAT_PNG if cover_bytes.startswith(b"\x89PNG") else MP4Cover.FORMAT_JPEG
                    audio.tags["covr"] = [MP4Cover(cover_bytes, imageformat=fmt)]
                else:
                    audio.tags.pop("covr", None)
                audio.save()

            elif ext == ".flac":
                audio = FLAC(str(path))
                audio.clear_pictures()
                if cover_bytes:
                    pic = self._make_flac_picture(cover_bytes)
                    audio.add_picture(pic)
                audio.save()

            elif ext in (".ogg", ".opus"):
                audio = mutagen.File(str(path))
                if audio is not None:
                    if cover_bytes:
                        pic = self._make_flac_picture(cover_bytes)
                        encoded = base64.b64encode(pic.write()).decode("ascii")
                        audio["metadata_block_picture"] = [encoded]
                    else:
                        audio.pop("metadata_block_picture", None)
                    audio.save()
        except Exception as e:
            logger.error(f"Ошибка сохранения обложки для {path.name}: {e}")

    @staticmethod
    def _make_flac_picture(cover_bytes: bytes) -> Picture:
        pic = Picture()
        pic.type = 3
        pic.mime = "image/png" if cover_bytes.startswith(b"\x89PNG") else "image/jpeg"
        pic.desc = "Cover"
        pic.data = cover_bytes
        return pic

    @staticmethod
    def _get_first_str(val) -> str:
        if val is None:
            return ""
        if isinstance(val, (list, tuple)):
            raw = str(val[0]).strip() if val else ""
        else:
            raw = str(val).strip()
        return fix_mojibake(raw)

    @staticmethod
    def _extract_year(raw: str) -> Optional[int]:
        if not raw:
            return None
        match = re.search(r"\b(19\d\d|20\d\d)\b", str(raw))
        return int(match.group(1)) if match else None

    @staticmethod
    def _parse_track_str(raw: str) -> Tuple[Optional[int], Optional[int]]:
        if not raw:
            return None, None
        cleaned = re.sub(r"[^\d/]", "", str(raw).strip())
        if not cleaned:
            return None, None
        parts = cleaned.split("/")
        try:
            num = int(parts[0]) if parts[0] else None
            tot = int(parts[1]) if len(parts) > 1 and parts[1] else None
            return num, tot
        except ValueError:
            return None, None