"""
Панель настройки параметров перекодирования с полной поддержкой режимов CBR и VBR.
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox, QCheckBox, QComboBox, QLabel
)
from core.domain.enums import AudioFormat
from core.interfaces.transcoder import EncodeSettings


class ConverterPanel(QWidget):
    """Панель выбора выходных форматов звука, режимов CBR/VBR, частоты и громкости."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.chk_enable_transcode = QCheckBox("Включить перекодирование при экспорте")
        self.chk_enable_transcode.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.chk_enable_transcode)

        self.box_params = QGroupBox("Параметры аудио")
        form = QFormLayout(self.box_params)
        form.setSpacing(8)

        # 1. Нормализация
        self.chk_loudnorm = QCheckBox("Нормализация громкости (EBU R128: -14 LUFS)")
        form.addRow("", self.chk_loudnorm)

        # 2. Формат
        self.combo_format = QComboBox()
        self.combo_format.addItem("MP3 (.mp3)", AudioFormat.MP3)
        self.combo_format.addItem("AAC (.m4a)", AudioFormat.AAC)
        self.combo_format.addItem("FLAC (.flac)", AudioFormat.FLAC)
        self.combo_format.addItem("WAV (.wav)", AudioFormat.WAV)
        self.combo_format.addItem("OGG Vorbis (.ogg)", AudioFormat.OGG)
        self.combo_format.addItem("Opus (.opus)", AudioFormat.OPUS)
        self.combo_format.addItem("Apple Lossless (.m4a)", AudioFormat.ALAC)
        self.combo_format.addItem("WMA (.wma)", AudioFormat.WMA)
        self.combo_format.currentIndexChanged.connect(self._on_format_or_mode_changed)
        form.addRow(QLabel("Целевой формат:"), self.combo_format)

        # 3. Режим битрейта (CBR vs VBR)
        self.lbl_rate_mode = QLabel("Режим битрейта:")
        self.combo_rate_mode = QComboBox()
        self.combo_rate_mode.addItem("Постоянный битрейт (CBR)", False)
        self.combo_rate_mode.addItem("Переменный битрейт (VBR)", True)
        self.combo_rate_mode.currentIndexChanged.connect(self._on_format_or_mode_changed)
        form.addRow(self.lbl_rate_mode, self.combo_rate_mode)

        # 4. Значение битрейта (для CBR)
        self.lbl_cbr_bitrate = QLabel("Битрейт (CBR):")
        self.combo_cbr_bitrate = QComboBox()
        for b in [320, 256, 224, 192, 160, 128, 96, 64]:
            self.combo_cbr_bitrate.addItem(f"{b} kbps", b)
        form.addRow(self.lbl_cbr_bitrate, self.combo_cbr_bitrate)

        # 5. Качество VBR (для VBR)
        self.lbl_vbr_quality = QLabel("Качество (VBR):")
        self.combo_vbr_quality = QComboBox()
        self.combo_vbr_quality.addItem("V0 (~245 kbps, наилучшее)", 0)
        self.combo_vbr_quality.addItem("V1 (~225 kbps, отличное)", 1)
        self.combo_vbr_quality.addItem("V2 (~190 kbps, стандарт)", 2)
        self.combo_vbr_quality.addItem("V3 (~175 kbps, хорошее)", 3)
        self.combo_vbr_quality.addItem("V4 (~165 kbps, среднее)", 4)
        self.combo_vbr_quality.addItem("V5 (~130 kbps, экономное)", 5)
        self.combo_vbr_quality.addItem("V6 (~115 kbps, низкое)", 6)
        form.addRow(self.lbl_vbr_quality, self.combo_vbr_quality)

        # 6. Частота дискретизации
        self.combo_sample_rate = QComboBox()
        self.combo_sample_rate.addItem("Исходная (без изменений)", None)
        self.combo_sample_rate.addItem("44 100 Hz (Audio CD)", 44100)
        self.combo_sample_rate.addItem("48 000 Hz (Studio)", 48000)
        self.combo_sample_rate.addItem("88 200 Hz (Hi-Res)", 88200)
        self.combo_sample_rate.addItem("96 000 Hz (Hi-Res Studio)", 96000)
        self.combo_sample_rate.addItem("192 000 Hz (Master)", 192000)
        form.addRow(QLabel("Частота дискретизации:"), self.combo_sample_rate)

        # 7. Формат сэмплов
        self.combo_sample_fmt = QComboBox()
        self.combo_sample_fmt.addItem("Исходный (автоматически)", None)
        self.combo_sample_fmt.addItem("16-bit (Integer - s16)", "s16")
        self.combo_sample_fmt.addItem("24-bit (Integer - s24)", "s24")
        self.combo_sample_fmt.addItem("32-bit (Integer - s32)", "s32")
        self.combo_sample_fmt.addItem("32-bit Float (flt)", "flt")
        form.addRow(QLabel("Формат сэмплов:"), self.combo_sample_fmt)

        # 8. Каналы
        self.combo_channels = QComboBox()
        self.combo_channels.addItem("Исходные (без изменений)", None)
        self.combo_channels.addItem("2.0 Стерео (Stereo)", 2)
        self.combo_channels.addItem("1.0 Моно (Mono)", 1)
        self.combo_channels.addItem("5.1 Surround (6 каналов)", 6)
        form.addRow(QLabel("Каналы аудио:"), self.combo_channels)

        layout.addWidget(self.box_params)
        layout.addStretch()
        self.box_params.setEnabled(False)
        self._on_format_or_mode_changed()

    def _on_enable_toggled(self, checked: bool) -> None:
        self.box_params.setEnabled(checked)

    def _on_format_or_mode_changed(self) -> None:
        fmt = self.combo_format.currentData()
        is_vbr = self.combo_rate_mode.currentData()
        is_lossless = fmt in (AudioFormat.FLAC, AudioFormat.WAV, AudioFormat.ALAC)

        # Lossless форматы не имеют настройки битрейта
        self.combo_rate_mode.setEnabled(not is_lossless)
        self.lbl_rate_mode.setEnabled(not is_lossless)

        # Видимость и доступность CBR / VBR контролов
        show_cbr = (not is_lossless) and (not is_vbr)
        show_vbr = (not is_lossless) and is_vbr

        self.lbl_cbr_bitrate.setVisible(show_cbr)
        self.combo_cbr_bitrate.setVisible(show_cbr)

        self.lbl_vbr_quality.setVisible(show_vbr)
        self.combo_vbr_quality.setVisible(show_vbr)

    def get_encode_settings(self) -> Optional[EncodeSettings]:
        if not self.chk_enable_transcode.isChecked():
            return None

        target_fmt = self.combo_format.currentData() or AudioFormat.MP3
        is_vbr = bool(self.combo_rate_mode.currentData())

        return EncodeSettings(
            target_format=target_fmt,
            is_vbr=is_vbr,
            bitrate_kbps=self.combo_cbr_bitrate.currentData() or 320,
            vbr_quality=self.combo_vbr_quality.currentData() if is_vbr else 0,
            normalize_volume=self.chk_loudnorm.isChecked(),
            sample_rate_hz=self.combo_sample_rate.currentData(),
            sample_format=self.combo_sample_fmt.currentData(),
            channels=self.combo_channels.currentData()
        )