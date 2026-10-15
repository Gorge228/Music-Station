"""
Сервис анализа и нормализации названий треков и альбомов.
Реализует контракты ITrackNormalizer и ITextCleaner (ISP).
"""
import re
from typing import Tuple, List
from core.interfaces.normalizer import ITrackNormalizer


class TrackNormalizer(ITrackNormalizer):
    """
    Парсер музыкальных названий.
    Извлекает гостевых исполнителей, теги версий и флаги минусовок,
    формируя очищенное «ядерное» название для точной дедупликации.
    """

    # Шаблоны истинной нумерации треков:
    # 1) Номер с разделителем: "01. ", "1 - ", "02_ ", "1/12 "
    # 2) Номер в скобках: "(01) ", "[1] "
    # 3) Двузначный номер с ведущим нулем и пробелом: "01 Track"
    # Обычные числа вроде "18 мне уже", "50 cent", "7 элемент" НЕ удаляются!
    PREFIX_NUM_RE = re.compile(
        r"^(?:\[?\d+\]?[\.\-_/]+\s*|\(\d+\)\s*|0\d+\s+)",
        re.IGNORECASE
    )

    # Небуквенные и нецифровые символы
    CLEAN_CHARS_RE = re.compile(r"[^a-z0-9а-яё]")

    # Маркеры караоке и минусовок
    KARAOKE_RE = re.compile(
        r"\b(karaoke|instrumental|minus|back|backing|минус|караоке|фонограмма|фоно|minusone)\b",
        re.IGNORECASE
    )

    # Версии в скобках: (Remix), [Club Mix], (Live 2004), [Acoustic]
    BRACKET_VERSION_RE = re.compile(
        r"[\(\[]\s*([^\)\]]*?\b(?:remix|megamix|mix|edit|dub|vip|live|acoustic|instrumental|"
        r"version|bootleg|mashup|rework|re-recorded|extended|orchestral|tribute|cover|session|demo)\b[^\)\]]*?)\s*[\)\]]",
        re.IGNORECASE
    )

    # Версии без скобок: "Song Name (Radio Edit)" или "Song Name Remix"
    STANDALONE_VERSION_RE = re.compile(
        r"(?:[\s\-_]+|^)\b(remix|megamix|club\s+mix|radio\s+edit|extended\s+mix|dub\s+mix|"
        r"vip\s+mix|acoustic\s+version|live\s+version|orchestral\s+version|bootleg|mashup|rework)\b",
        re.IGNORECASE
    )

    # Гостевое участие (Featuring)
    FEAT_RE = re.compile(
        r"\b(?:feat\.?|ft\.?|featuring|с\s+уч\.?|дуэт\s+с|при\s+уч\.?)\s+([^\)\]\-]+)",
        re.IGNORECASE
    )

    # Паттерны интернет-мусора и рекламы
    JUNK_PATTERNS = [
        re.compile(r"\[?\b(?:https?://)?(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_\+.~#?&//=]*\]?", re.IGNORECASE),
        re.compile(r"\b(?:vk\.com|t\.me|promodj|hitmo|zaycev|muzon|mp3party|drivemusic|zf\.fm|spaces\.ru)\S*", re.IGNORECASE),
        re.compile(r"[\(\[]\s*(?:official\s*(?:video|audio|clip|music\s*video)|lyric\s*video|клип|видеоклип|премьера(?:\s*трека)?)\s*[\)\]]", re.IGNORECASE),
        re.compile(r"[\(\[]\s*(?:320\s*kbps|128\s*kbps|256\s*kbps|flac|lossless|cd-rip|web-dl|hq|hd)\s*[\)\]]", re.IGNORECASE),
        re.compile(r"[\(\[]\s*(?:new\s*hit|новинка|хит|эксклюзив|exclusive)\s*[\)\]]", re.IGNORECASE),
    ]

    # Словарь транслитерации для формирования инвариантной сигнатуры:
    # "ё" жестко транслитерируется в "e", чтобы "алёшка" и "алешка" давали абсолютно одинаковый хэш!
    TRANSLIT_DICT = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ы": "y", "э": "e", "ю": "yu", "я": "ya", "ь": "", "ъ": ""
    }

    def super_clean(self, text: str) -> str:
        """
        Преобразует строку в чистую сигнатуру: нижний регистр, замена ё->е,
        транслитерация кириллицы и удаление всех пробелов и знаков препинания.
        """
        if not text:
            return ""
        lowered = str(text).lower().replace("ё", "е")
        transliterated = "".join(self.TRANSLIT_DICT.get(char, char) for char in lowered)
        return self.CLEAN_CHARS_RE.sub("", transliterated)

    def clean_junk(self, text: str) -> str:
        """Очищает строку от ссылок, рекламы сайтов, промо-тегов и битрейта."""
        if not text:
            return ""
        result = str(text)
        for pattern in self.JUNK_PATTERNS:
            result = pattern.sub("", result)
        # Удаляем пустые скобки, оставшиеся после очистки мусора: (), [], {}
        result = re.sub(r"[\(\[\{]\s*[\)\]\}]", "", result)
        # Схлопываем лишние пробелы, тире и подчеркивания по краям
        result = re.sub(r"\s+", " ", result).strip(" -_.\t\r\n")
        return result

    def clean_track_title(self, title: str) -> str:
        """
        Очищает название трека: убирает мусор и номера треков,
        но сохраняет числа, входящие в состав названия (например, '18 мне уже').
        """
        if not title:
            return ""
        cleaned = self.clean_junk(title)
        cleaned = self.PREFIX_NUM_RE.sub("", cleaned).strip(" -_.\t\r\n")
        return cleaned or title.strip()

    def clean_album_name(self, album: str) -> str:
        """
        Очищает название альбома от маркетингового мусора (Deluxe, Remaster, года в скобках),
        позволяя объединять переиздания с оригинальным студийным альбомом.
        """
        if not album:
            return "unknownalbum"

        cleaned = self.clean_junk(album)

        # Удаление скобок любого типа с содержимым переизданий: (1997), [2020 Remaster], [Deluxe]
        cleaned = re.sub(r"[\(\[].*?[\)\]]", "", cleaned)

        # Удаление типичных маркеров переизданий
        cleaned = re.sub(
            r"\b(maschina records|deluxe|edition|limited|reissue|remastered|remaster|best|лучшее|"
            r"collection|переиздание|юбилейное|anniversary|special edition|expanded)\b",
            "",
            cleaned,
            flags=re.IGNORECASE
        )

        # Удаление суффиксов вида "+ 4 bonus tracks"
        cleaned = re.sub(r"\+\s*\d+\s*(новые|песни|трека|bonus|песен|tracks).*", "", cleaned, flags=re.IGNORECASE)

        # Удаление отдельно стоящих годов
        cleaned = re.sub(r"\b(19\d\d|20\d\d)\b", "", cleaned)

        result = self.super_clean(cleaned)
        return result or self.super_clean(album)

    def extract_features(self, title: str, artist: str) -> Tuple[str, List[str], List[str], bool]:
        """
        Разбирает название трека на составляющие:
        - Ядерное название (nuclear_title) без фитов и версий
        - Список гостей (feats)
        - Список тегов версий (versions)
        - Флаг караоке/минусовки (is_karaoke)
        """
        # 1. Очистка от рекламы и срезание истинного порядкового индекса
        work_title = self.clean_junk(str(title))
        work_title = self.PREFIX_NUM_RE.sub("", work_title).strip()

        # 2. Детекция караоке
        is_karaoke = bool(self.KARAOKE_RE.search(work_title))

        # 3. Извлечение тегов версий
        versions: List[str] = []
        for match in self.BRACKET_VERSION_RE.finditer(work_title):
            tag = match.group(1).strip()
            if tag.lower() not in [v.lower() for v in versions]:
                versions.append(tag)

        for match in self.STANDALONE_VERSION_RE.finditer(work_title):
            tag = match.group(1).strip()
            if tag.lower() not in [v.lower() for v in versions]:
                versions.append(tag)

        # 4. Извлечение соисполнителей (Feats)
        feats: List[str] = [m.strip() for m in self.FEAT_RE.findall(work_title)]

        # 5. Вычисление ядерного названия: удаляем версии, караоке-маркеры и скобки
        temp_title = self.BRACKET_VERSION_RE.sub("", work_title)
        temp_title = self.STANDALONE_VERSION_RE.sub("", temp_title)
        temp_title = self.KARAOKE_RE.sub("", temp_title)
        temp_title = self.FEAT_RE.sub("", temp_title)
        temp_title = re.sub(r"[\(\[].*?[\)\]]", "", temp_title)

        nuclear_title = self.super_clean(temp_title)
        if not nuclear_title:
            nuclear_title = self.super_clean(work_title)

        return nuclear_title, feats, [v.lower() for v in versions], is_karaoke