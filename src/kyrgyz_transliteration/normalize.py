"""Нормализация кириллического ввода перед транслитерацией.

Реальный кыргызский текст редко бывает «чистым»: ө, ү и ң набирают буквами
соседних алфавитов (ѳ, ɵ, ö, ü, ҥ, ӊ), в слова попадают латинские
буквы-двойники (Тaлаc, Чyй), ударения и декомпозированные формы (й как
и + бреве), невидимые символы (мягкий перенос, нулевой пробел), казахские,
узбекские и таджикские буквы, римские цифры из кириллических Х и І. Движок
транслитерирует посимвольно и такие символы пропускал бы насквозь — в
результате вместо букв ``a-z`` получались бы ``ѳ``, ``ö`` или ``\\u0301``.

:func:`normalize_cyrillic` приводит всё это к обычной кыргызской кириллице,
не трогая ничего, что кириллицей не является: латинские слова, цифры,
пунктуация, эмодзи и прочие алфавиты проходят насквозь, как и раньше.
Для «чистого» текста функция — быстрая проверка и возврат той же строки.

    >>> normalize_cyrillic("дѳңгѳлѳк")
    'дөңгөлөк'
    >>> normalize_cyrillic("Тaлаc")        # латинские a и c внутри кириллицы
    'Талас'
    >>> normalize_cyrillic("ХХІ кылым")    # римские цифры кириллицей
    'XXI кылым'
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, FrozenSet, List, Match

from .schemes import CYRILLIC_LETTERS

__all__ = [
    "CYRILLIC_EXTRAS",
    "LATIN_HOMOGLYPHS",
    "LATIN_LOOKALIKES",
    "normalize_cyrillic",
]

#: Буквы кириллицы вне кыргызского алфавита -> кыргызские буквы, которыми
#: записывают тот же звук. Ключи — в нижнем регистре.
CYRILLIC_EXTRAS: Dict[str, str] = {
    # казахский / узбекский / таджикский / башкирский / татарский / каракалпакский
    "ә": "а", "ғ": "г", "қ": "к", "ұ": "у", "һ": "х", "і": "и", "ў": "у", "ҳ": "х",
    "ҷ": "ж", "ӣ": "и", "ӯ": "у", "ҙ": "з", "ҫ": "с", "ҡ": "к", "җ": "ж",
    "ҥ": "ң", "ӊ": "ң", "ӈ": "ң",
    # двойники ө / ү с других раскладок
    "ѳ": "ө", "ӧ": "ө", "ӫ": "ө", "ӱ": "ү", "ӳ": "ү",
    # украинский / белорусский / русинский
    "є": "е", "ї": "и", "ґ": "г",
    # сербский / македонский
    "ј": "й", "љ": "ль", "њ": "нь", "ђ": "дж", "ћ": "ч", "џ": "дж", "ѕ": "дз",
    "ѓ": "г", "ќ": "к",
    # дореформенный русский / церковнославянский
    "ѣ": "е", "ѵ": "и", "ѷ": "и", "ѡ": "о", "ѻ": "о", "ѽ": "о", "ѿ": "от",
    "ѧ": "я", "ѩ": "я", "ѫ": "у", "ѭ": "ю", "ѥ": "е", "ѯ": "кс", "ѱ": "пс",
    "ѹ": "у", "ꙋ": "у", "ҁ": "", "ҍ": "", "ꙿ": "",
    # буквы с диакритикой (алтайский, марийский, удмуртский, чувашский, ...)
    "ӑ": "а", "ӓ": "а", "ӕ": "ае", "ӗ": "е", "ѐ": "е", "ѝ": "и", "ӥ": "и",
    "ӂ": "ж", "ӝ": "ж", "ӟ": "з", "ӵ": "ч", "ӹ": "ы", "ӭ": "э", "ӛ": "а", "ҋ": "й",
    # буквы с нижними выносными, крюками, хвостами, штрихами
    "ҕ": "г", "ӷ": "г", "ӻ": "г", "ҝ": "к", "ҟ": "к", "ӄ": "к", "ԟ": "к", "ԛ": "к",
    "ҧ": "п", "ԥ": "п", "ҏ": "р", "ҭ": "т", "ҵ": "ц", "ҹ": "ч", "ҽ": "ч", "ҿ": "ч",
    "ӌ": "ч", "ӡ": "з", "ҩ": "х", "ӽ": "х", "ӿ": "х", "ԧ": "х", "ӆ": "л", "ԓ": "л",
    "ԡ": "л", "ԯ": "л", "ԕ": "л", "ӎ": "м", "ԣ": "н", "ԩ": "н", "ԝ": "в", "ԗ": "р",
    "ԑ": "з", "ԙ": "я", "ԁ": "д", "ԃ": "дж", "ԅ": "з", "ԇ": "дз", "ԉ": "л",
    "ԋ": "н", "ԍ": "с", "ԏ": "т", "ԫ": "дж", "ԭ": "ч",
    # палочка (U+04CF): в кыргызском тексте только как замена I / l
    "ӏ": "и",
    # Cyrillic Extended-C (варианты начертания) и фонетические буквы
    "ᲀ": "в", "ᲁ": "д", "ᲂ": "о", "ᲃ": "с", "ᲄ": "т", "ᲅ": "т", "ᲆ": "ъ", "ᲇ": "е",
    "ᲈ": "у", "ᲊ": "т", "ᴫ": "л", "ᵸ": "н", "ꚜ": "ъ", "ꚝ": "ь",
    # Cyrillic Extended-B (старославянский, исторический абхазский)
    "ꙁ": "з", "ꙃ": "з", "ꙅ": "з", "ꙇ": "и", "ꙉ": "ч", "ꙍ": "о", "ꙏ": "ъ", "ꙑ": "ы",
    "ꙓ": "е", "ꙕ": "ю", "ꙗ": "я", "ꙙ": "я", "ꙛ": "у", "ꙝ": "я", "ꙟ": "н", "ꙡ": "ц",
    "ꙣ": "д", "ꙥ": "л", "ꙧ": "м", "ꙩ": "о", "ꙫ": "о", "ꙭ": "о", "ꙮ": "о",
    "ꚁ": "д", "ꚃ": "дз", "ꚅ": "ж", "ꚇ": "ч", "ꚉ": "дз", "ꚋ": "т", "ꚍ": "т", "ꚏ": "ц",
    "ꚑ": "ц", "ꚓ": "ч", "ꚕ": "х", "ꚗ": "ш", "ꚙ": "о", "ꚛ": "о",
}

#: Некириллические буквы, которыми внутри кириллического слова записывают
#: ө, ү, ң (и казахское ә): латинские умляуты, IPA, греческая тета.
LATIN_LOOKALIKES: Dict[str, str] = {
    "ö": "ө", "ɵ": "ө", "ø": "ө", "θ": "ө",
    "ü": "ү", "ÿ": "ү",
    "ñ": "ң", "ŋ": "ң", "ƞ": "ң",
    "ə": "а",
}

#: Латинские буквы, начертание которых совпадает с кириллическими (UTS #39).
#: Остальные латинские буквы (d f g j l n q r s u v w z ...) двойников не
#: имеют: их присутствие означает настоящее латинское слово.
LATIN_HOMOGLYPHS: Dict[str, str] = {
    "a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х", "y": "у", "i": "и",
    "k": "к", "m": "м", "t": "т", "h": "н", "b": "ь",
    "A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н", "K": "К", "M": "М", "O": "О",
    "P": "Р", "T": "Т", "X": "Х", "Y": "Ү", "I": "І",
}

# Невидимые форматирующие символы: мягкий перенос, нулевые пробелы и
# соединители, word joiner, BOM, монгольский разделитель, соединитель графем.
_INVISIBLES: FrozenSet[str] = frozenset("­​‌‍⁠﻿᠎͏")

_CYRILLIC_BLOCKS = "Ѐ-ԯᲀ-᲏ᴫᵸꙀ-ꚟ"
_WORD_RE = re.compile(r"[^\W\d_]+")

_KYRGYZ = set(CYRILLIC_LETTERS) | set(CYRILLIC_LETTERS.upper())

# Римские цифры, набранные кириллицей: ХХ кылым, ХІХ кылым, ІV чакырылыш.
_ROMAN_RE = re.compile(r"^(?=[XVILCDM])M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
_ROMAN_TOKEN_RE = re.compile(r"(?<![^\W\d_])[XVILCDMХІӀ]{2,}(?![^\W\d_])")
_ROMAN_CYRILLIC = str.maketrans({"Х": "X", "І": "I", "Ӏ": "I"})

# Градусы Цельсия кириллической С: 25°С.
_CELSIUS_RE = re.compile("(?<=[°º˚])С")

# Апостроф на месте ъ/ь перед йотированной гласной (об'ект, под’езд) —
# машинописная и OCR-орфография. Апостроф-разделитель суффикса (КТРК'да,
# Facebook'тан) под правило не попадает: после него не идёт е/ё/ю/я/и, либо
# перед ним не кириллическая согласная.
_HARD_SIGN_APOSTROPHE_RE = re.compile(
    "(?<=[бвгджзклмнпрстфхцчшщБВГДЖЗКЛМНПРСТФХЦЧШЩ])['’ʼʻʹʺ`´](?=[еёюяиЕЁЮЯИ])"
)

# Быстрая проверка: есть ли в тексте хоть что-то, требующее нормализации.
_SUSPICIOUS_RE = re.compile(
    "[̀-ͯ҃-҉᪰-᫿᷀-᷿⃐-⃿ⷠ-ⷿ꙯-ꙿ︠-︯]"
    "|[" + "".join(sorted(_INVISIBLES)) + "]"
    "|(?![" + re.escape(CYRILLIC_LETTERS + CYRILLIC_LETTERS.upper()) + "])[" + _CYRILLIC_BLOCKS + "]"
    "|[A-Za-zÀ-ɏəɵΘθϴ][" + _CYRILLIC_BLOCKS + "]"
    "|[" + _CYRILLIC_BLOCKS + "][A-Za-zÀ-ɏəɵΘθϴ]"
    "|['’ʼʻʹʺ`´][еёюяиЕЁЮЯИ]"
    "|[°º˚]С"
    "|(?<![^\\W\\d_])[XVILCDMХІӀ]*[ХІӀ][XVILCDMХІӀ]*(?![^\\W\\d_])"
)


def _is_cyrillic(char: str) -> bool:
    """Символ из кириллических блоков Unicode (те же диапазоны, что ``_CYRILLIC_BLOCKS``)."""
    code = ord(char)
    return (
        0x0400 <= code <= 0x052F
        or 0xA640 <= code <= 0xA69F
        or 0x1C80 <= code <= 0x1C8F
        or code == 0x1D2B
        or code == 0x1D78
    )


def _fix_roman(match: Match[str]) -> str:
    token = match.group()
    if not re.search("[ХІӀ]", token):
        return token
    latin = token.translate(_ROMAN_CYRILLIC)
    return latin if _ROMAN_RE.match(latin) else token


def _recase(original: str, replacement: str, word_caps: bool) -> str:
    """Регистр замены по регистру исходной буквы (Љ -> Ль, ЉУБЉАНА -> ЛЬУБЛЬАНА)."""
    if not replacement or not original.isupper():
        return replacement
    if word_caps or len(replacement) == 1:
        return replacement.upper()
    return replacement[0].upper() + replacement[1:]


def _fold_characters(text: str) -> str:
    """NFC, буквы соседних алфавитов, ударения и невидимые символы."""
    text = unicodedata.normalize("NFC", text)
    out: List[str] = []
    prev_cyrillic = False
    length = len(text)
    word_caps = False
    word_end = -1
    for index, char in enumerate(text):
        if char in _INVISIBLES:
            follow = index + 1
            while follow < length and text[follow] in _INVISIBLES:
                follow += 1
            if prev_cyrillic and follow < length and _is_cyrillic(text[follow]):
                continue  # невидимка между двумя кириллическими буквами
            out.append(char)
            continue
        if unicodedata.category(char).startswith("M"):
            if prev_cyrillic:
                continue  # ударение, титло, седиль после кириллицы: буквы не меняют
            out.append(char)
            continue
        if _is_cyrillic(char):
            if char not in _KYRGYZ:
                lowered = char.lower()
                extra = CYRILLIC_EXTRAS.get(lowered)
                if extra is None:
                    base = unicodedata.normalize("NFD", lowered)[0]
                    extra = base if base in _KYRGYZ else None
                if extra is not None:
                    if index > word_end:
                        match = _WORD_RE.match(text, index)
                        word = match.group() if match else char
                        word_end = index + len(word) - 1
                        letters = [c for c in word if c.isupper() or c.islower()]
                        word_caps = len(letters) > 1 and all(c.isupper() for c in letters)
                    char = _recase(char, extra, word_caps)
            out.append(char)
            prev_cyrillic = True
            continue
        out.append(char)
        prev_cyrillic = False
    return "".join(out)


def _repair_word(word: str) -> str:
    """Латинские двойники внутри кириллического слова -> кириллица."""
    cyrillic = sum(1 for char in word if _is_cyrillic(char))
    if not cyrillic:
        return word  # чисто латинское слово (Facebook, iPhone, HP) не трогаем
    chars: List[str] = []
    for char in word:
        lowered = char.lower()
        replacement = LATIN_LOOKALIKES.get(lowered)
        if replacement is None:
            chars.append(char)
        else:
            chars.append(replacement.upper() if char.isupper() else replacement)
    word = "".join(chars)
    latin = [char for char in word if "a" <= char.lower() <= "z"]
    # Чинить можно, только когда все латинские буквы — двойники и кириллица
    # явно преобладает или латинская буква одна: «HPге», «TOPтун», «Ошpa»
    # остаются как есть.
    if (
        latin
        and all(char in LATIN_HOMOGLYPHS for char in latin)
        and (cyrillic > len(latin) or len(latin) == 1)
    ):
        word = "".join(LATIN_HOMOGLYPHS.get(char, char) for char in word)
    return word


def normalize_cyrillic(text: str) -> str:
    """Привести кириллицу текста к стандартным буквам кыргызского алфавита.

    Что делается (только там, где это касается кириллических слов):

    1. римские цифры из кириллических Х/І становятся латинскими (ХХ -> XX);
    2. градусы «°С» с кириллической С -> «°C»;
    3. текст приводится к NFC (и + бреве -> й, е + диерезис -> ё);
    4. буквы кириллицы вне кыргызского алфавита заменяются кыргызскими
       (ә -> а, қ -> к, ѳ -> ө, ҥ -> ң, љ -> ль, ...);
    5. ударения и другие комбинируемые знаки после кириллической буквы
       отбрасываются;
    6. невидимые символы (мягкий перенос, нулевой пробел, BOM) между двумя
       кириллическими буквами удаляются;
    7. апостроф на месте ъ/ь перед е/ё/ю/я/и убирается (об'ект -> обект);
    8. в словах, где есть кириллица, латинские двойники заменяются:
       ö/ɵ/θ -> ө, ü -> ү, ñ/ŋ -> ң всегда, а a/c/e/o/p/x/y/H/B/... — только
       когда все латинские буквы слова — двойники и кириллица преобладает.

    Чисто латинские слова, цифры, пунктуация, эмодзи и другие алфавиты не
    меняются. Для текста без подозрительных символов функция возвращает ту
    же строку почти мгновенно.

        >>> normalize_cyrillic("Кыргы\\u0301з")
        'Кыргыз'
        >>> normalize_cyrillic("Facebook'тан iPhone")
        "Facebook'тан iPhone"
    """
    if not text or not _SUSPICIOUS_RE.search(text):
        return text
    text = _ROMAN_TOKEN_RE.sub(_fix_roman, text)
    text = _CELSIUS_RE.sub("C", text)
    text = _fold_characters(text)
    text = _HARD_SIGN_APOSTROPHE_RE.sub("", text)

    repaired: Dict[str, str] = {}  # слова в тексте повторяются: чиним каждое один раз

    def repair(match: Match[str]) -> str:
        word = match.group()
        fixed = repaired.get(word)
        if fixed is None:
            fixed = repaired[word] = _repair_word(word)
        return fixed

    return _WORD_RE.sub(repair, text)
