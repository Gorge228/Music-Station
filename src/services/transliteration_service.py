
"""
Сервис двунаправленной транслитерации текста.
Реализует контракт ITransliterationService (DIP).
"""
from core.domain.enums import TranslitMode
from core.interfaces.transliteration import ITransliterationService


class TransliterationService(ITransliterationService):
    """
    Надежный сервис перевода кириллических символов в латиницу и обратно.
    Учитывает многобуквенные сочетания (Щ, Ш, Ч, Ю, Я).
    """

    _CYR_TO_LAT = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
        "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "Yo",
        "Ж": "Zh", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M",
        "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T", "У": "U",
        "Ф": "F", "Х": "Kh", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh", "Щ": "Shch",
        "Ъ": "", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "Yu", "Я": "Ya"
    }

    # Порядок пар важен: длинные сочетания заменяются первыми (shch -> щ, затем sh -> ш)
    _LAT_TO_CYR_PAIRS = [
        ("shch", "щ"), ("Shch", "Щ"), ("SHCH", "Щ"),
        ("yo", "ё"), ("Yo", "Ё"), ("YO", "Ё"),
        ("zh", "ж"), ("Zh", "Ж"), ("ZH", "Ж"),
        ("kh", "х"), ("Kh", "Х"), ("KH", "Х"),
        ("ts", "ц"), ("Ts", "Ц"), ("TS", "Ц"),
        ("ch", "ч"), ("Ch", "Ч"), ("CH", "Ч"),
        ("sh", "ш"), ("Sh", "Ш"), ("SH", "Ш"),
        ("yu", "ю"), ("Yu", "Ю"), ("YU", "Ю"),
        ("ya", "я"), ("Ya", "Я"), ("YA", "Я"),
        ("a", "а"), ("b", "б"), ("v", "в"), ("g", "г"), ("d", "д"), ("e", "е"),
        ("z", "з"), ("i", "и"), ("y", "ы"), ("k", "к"), ("l", "л"), ("m", "м"),
        ("n", "н"), ("o", "о"), ("p", "п"), ("r", "р"), ("s", "с"), ("t", "т"),
        ("u", "у"), ("f", "ф"),
        ("A", "А"), ("B", "Б"), ("V", "В"), ("G", "Г"), ("D", "Д"), ("E", "Е"),
        ("Z", "З"), ("I", "И"), ("Y", "Ы"), ("K", "К"), ("L", "Л"), ("M", "М"),
        ("N", "Н"), ("O", "О"), ("P", "П"), ("R", "Р"), ("S", "С"), ("T", "Т"),
        ("U", "У"), ("F", "Ф")
    ]

    def transform(self, text: str, mode: TranslitMode) -> str:
        if not text or mode == TranslitMode.OFF:
            return text

        if mode == TranslitMode.CYRILLIC_TO_LATIN:
            return "".join(self._CYR_TO_LAT.get(char, char) for char in text)

        if mode == TranslitMode.LATIN_TO_CYRILLIC:
            result = text
            for lat, cyr in self._LAT_TO_CYR_PAIRS:
                result = result.replace(lat, cyr)
            return result

        return text