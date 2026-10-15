# models.py
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from .enums import AudioFormat, DuplicateStatus


@dataclass
class AudioMetadata:
    title: str = ""
    artist: str = ""
    album_artist: str = ""
    album: str = ""
    year: Optional[int] = None
    genre: str = ""
    track_number: Optional[int] = None
    total_tracks: Optional[int] = None
    disc_number: Optional[int] = None
    total_discs: Optional[int] = None
    comment: str = ""
    duration_seconds: float = 0.0
    bitrate: Optional[int] = None
    lyrics: str = ""

    def clone(self) -> "AudioMetadata":
        return AudioMetadata(
            title=self.title,
            artist=self.artist,
            album_artist=self.album_artist,
            album=self.album,
            year=self.year,
            genre=self.genre,
            track_number=self.track_number,
            total_tracks=self.total_tracks,
            disc_number=self.disc_number,
            total_discs=self.total_discs,
            comment=self.comment,
            duration_seconds=self.duration_seconds,
            bitrate=self.bitrate,
            lyrics=self.lyrics,
        )


@dataclass
class Track:
    source_path: Path
    file_format: AudioFormat
    file_size_bytes: int
    metadata: AudioMetadata

    track_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    normalized_title: str = ""
    detected_feats: List[str] = field(default_factory=list)
    detected_version_tags: List[str] = field(default_factory=list)
    is_karaoke: bool = False
    master_album: str = ""
    duplicate_status: DuplicateStatus = DuplicateStatus.ORIGINAL
    original_track_ref: Optional["Track"] = None

    is_excluded_from_export: bool = False
    target_relative_path: Optional[Path] = None
    export_metadata: Optional[AudioMetadata] = None

    initial_metadata: Optional[AudioMetadata] = None
    custom_filename: Optional[str] = None

    # Хранение обложки в памяти (для работы без обязательной немедленной записи на диск)
    custom_cover_bytes: Optional[bytes] = None
    is_cover_deleted: bool = False

    def __hash__(self) -> int:
        return hash(self.track_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Track):
            return False
        return self.track_id == other.track_id

    @property
    def effective_artist(self) -> str:
        return self.metadata.album_artist or self.metadata.artist or "Unknown Artist"

    @property
    def effective_album(self) -> str:
        return self.metadata.album or "Unknown Album"

    @property
    def current_filename(self) -> str:
        if self.custom_filename:
            return self.custom_filename
        if self.target_relative_path:
            return self.target_relative_path.name
        return self.source_path.name

    def set_custom_filename(self, name: str) -> None:
        if not name:
            return
        clean_name = name.strip()
        if not Path(clean_name).suffix:
            clean_name += self.source_path.suffix
        self.custom_filename = clean_name
        if self.target_relative_path:
            self.target_relative_path = self.target_relative_path.with_name(clean_name)