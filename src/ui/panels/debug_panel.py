"""
Инспектор отладки трека и вычисленных сигнатур дедупликации.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from core.domain.models import Track


class TrackDebugPanel(QWidget):
    """Отображает внутреннее состояние трека для аудита алгоритмов."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

    def inspect_track(self, track: Track) -> None:
        if not track:
            self.log_view.setPlainText("Трек не выбран.")
            return

        text = [
            "=== ИНСПЕКТОР ТРЕКА ===",
            f"ID сущности: {track.track_id}",
            f"Файл: {track.source_path.name}",
            f"Размер: {track.file_size_bytes} байт",
            f"Формат: {track.file_format.name}",
            f"Статус дубликата: {track.duplicate_status.name}",
            f"Караоке / Минус: {track.is_karaoke}",
            f"Ядерное название: {track.normalized_title}",
            f"Определенные версии: {track.detected_version_tags}",
            f"Определенные фиты: {track.detected_feats}",
            f"Master-альбом: {track.master_album}",
            f"Путь назначения: {track.target_relative_path}"
        ]
        self.log_view.setPlainText("\n".join(text))