"""Транслитерация кыргызского языка: кириллица <-> английская латиница.

    >>> from kyrgyz_transliteration import to_latin, to_cyrillic, slugify
    >>> to_latin("Кыргыз Республикасы")
    'Kyrgyz Respublikasy'
    >>> to_cyrillic("Kyrgyz Respublikasy")
    'Кыргыз Республикасы'
    >>> slugify("Ысык-Көл")
    'ysyk-kol'

Английская латиница не различает ө и о, ү и у, ң и н, поэтому обратно они
восстанавливаются по списку кыргызских слов — он включён по умолчанию:

    >>> to_latin("дөңгөлөк")
    'dongolok'
    >>> to_cyrillic("dongolok")
    'дөңгөлөк'

Ввод чистится от «грязной» кириллицы: двойники ө/ү/ң с других раскладок,
латинские буквы внутри кириллических слов, ударения и невидимые символы
не мешают получить чистые буквы a-z:

    >>> to_latin("дѳңгѳлѳк Тaлаc Кыргы\\u0301з")
    'dongolok Talas Kyrgyz'
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple, Union

from .core import Table, apply_table, match_case
from .normalize import _WORD_RE, _is_cyrillic, normalize_cyrillic
from .restore import (
    Wordlist,
    ascii_key,
    builtin_names,
    builtin_wordlist,
    restore_words,
)
from .schemes import (
    CYRILLIC_LETTERS,
    DEFAULT_SCHEME,
    SCHEMES,
    Scheme,
    UnknownSchemeError,
    get_scheme,
    list_schemes,
    register_scheme,
)

__version__ = "0.3.0"

__all__ = [
    "CYRILLIC_LETTERS",
    "DEFAULT_SCHEME",
    "SCHEMES",
    "Scheme",
    "Table",
    "UnknownSchemeError",
    "Wordlist",
    "__version__",
    "alphabet_table",
    "apply_table",
    "ascii_key",
    "builtin_names",
    "builtin_wordlist",
    "detect_script",
    "get_scheme",
    "list_schemes",
    "match_case",
    "normalize_cyrillic",
    "register_scheme",
    "restore_words",
    "slugify",
    "to_cyrillic",
    "to_latin",
    "transliterate",
]

SchemeArg = Union[str, Scheme]
WordlistArg = Union[None, bool, Wordlist]

# × (U+00D7) и ÷ (U+00F7) — знаки, а не буквы.
_LATIN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ɏ]")
# Адреса, почта, хэштеги и упоминания — идентификаторы, их не транслитерируем.
_URLISH_RE = re.compile(
    r"(?:https?://|ftp://|www\.)\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+|(?<!\w)[@#][\w_]+"
)


def _check_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError(f"ожидается строка, получено {type(text).__name__}")
    return text


def _resolve_wordlist(wordlist: WordlistArg) -> Optional[Wordlist]:
    """Какой словарь использовать: ``None``/``True`` — встроенный, ``False`` — никакой.

    Сравнение идёт по тождеству, чтобы пустой :class:`Wordlist` (он ложен как
    пустой контейнер) не был принят за ``False``.
    """
    if wordlist is None or wordlist is True:
        return builtin_wordlist()
    if wordlist is False:
        return None
    return wordlist


def to_latin(text: str, scheme: SchemeArg = DEFAULT_SCHEME, *, normalize: bool = True) -> str:
    """Перевести кыргызский текст с кириллицы на английскую латиницу.

    :param normalize: привести «грязную» кириллицу к стандартной перед
        транслитерацией (см. :func:`normalize_cyrillic`): двойники ө/ү/ң,
        латинские буквы внутри кириллических слов, ударения, невидимые
        символы, буквы соседних алфавитов. ``False`` — транслитерировать
        строго посимвольно.

        >>> to_latin("Манас атанын ак сарайы")
        'Manas atanyn ak saraiy'
        >>> to_latin("Ысык-Көл", scheme="bgn_ascii")
        'Ysyk-Kol'
        >>> to_latin("кыйын")
        'kyiyn'
        >>> to_latin("Айгүл Жумагулова", scheme="passport")
        'Aigul Zhumagulova'
    """
    text = _check_text(text)
    if normalize:
        text = normalize_cyrillic(text)
    return apply_table(text, get_scheme(scheme).forward_table())


def _to_cyrillic_chunk(text: str, scheme: Scheme, words: Optional[Wordlist]) -> str:
    if words is not None:
        text = restore_words(text, words, scheme)
    return apply_table(text, scheme.reverse_table())


def to_cyrillic(
    text: str,
    scheme: SchemeArg = DEFAULT_SCHEME,
    wordlist: WordlistArg = None,
) -> str:
    """Перевести кыргызский текст с английской латиницы на кириллицу.

    :param wordlist: чем восстанавливать ө, ү и ң, которых в английской
        латинице нет: ``None`` или ``True`` — встроенным списком частотных
        кыргызских слов, ``False`` — ничем (только правилами схемы), или свой
        :class:`Wordlist`. Слова из словаря восстанавливаются целиком,
        остальные разбираются правилами схемы.

    Адреса сайтов, электронной почты, хэштеги и упоминания (``@user``)
    остаются как есть.

        >>> to_cyrillic("Manas atanyn ak saraiy")
        'Манас атанын ак сарайы'
        >>> to_cyrillic("Manas atanyn ak sarayy")   # старое написание тоже понимается
        'Манас атанын ак сарайы'
        >>> to_cyrillic("dongolok")
        'дөңгөлөк'
        >>> to_cyrillic("dongolok", wordlist=False)
        'донголок'
        >>> to_cyrillic("Toluk maalymat: https://www.gov.kg/ky")
        'Толук маалымат: https://www.gov.kg/ky'
    """
    text = _check_text(text)
    resolved = get_scheme(scheme)
    words = _resolve_wordlist(wordlist)
    result: List[str] = []
    position = 0
    for match in _URLISH_RE.finditer(text):
        result.append(_to_cyrillic_chunk(text[position : match.start()], resolved, words))
        result.append(match.group())
        position = match.end()
    result.append(_to_cyrillic_chunk(text[position:], resolved, words))
    return "".join(result)


def _script_word_counts(text: str, normalize: bool) -> Tuple[int, int]:
    """Сколько в тексте кириллических и латинских слов (адреса не считаются)."""
    text = _URLISH_RE.sub(" ", text)
    if normalize:
        text = normalize_cyrillic(text)
    cyrillic_words = latin_words = 0
    for match in _WORD_RE.finditer(text):
        word = match.group()
        cyrillic = sum(map(_is_cyrillic, word))
        latin = len(_LATIN_RE.findall(word))
        if cyrillic and cyrillic >= latin:
            cyrillic_words += 1
        elif latin:
            latin_words += 1
    return cyrillic_words, latin_words


def detect_script(text: str, *, normalize: bool = True) -> str:
    """Определить письменность текста.

    Возвращает ``"cyrillic"``, ``"latin"``, ``"mixed"`` или ``"unknown"``.
    Считаются слова, а не буквы: адреса сайтов и почты не учитываются, а
    слово с латинскими двойниками внутри кириллицы считается кириллическим.

        >>> detect_script("Бишкек")
        'cyrillic'
        >>> detect_script("Bishkek")
        'latin'
        >>> detect_script("Бишкек Bishkek")
        'mixed'
        >>> detect_script("2026")
        'unknown'
    """
    cyrillic, latin = _script_word_counts(_check_text(text), normalize)
    if not cyrillic and not latin:
        return "unknown"
    if cyrillic and latin:
        minority = min(cyrillic, latin) / float(cyrillic + latin)
        if minority > 0.25:
            return "mixed"
    return "cyrillic" if cyrillic >= latin else "latin"


def transliterate(
    text: str,
    scheme: SchemeArg = DEFAULT_SCHEME,
    direction: str = "auto",
    wordlist: WordlistArg = None,
    *,
    normalize: bool = True,
) -> str:
    """Транслитерировать текст в заданном направлении.

    :param direction: ``"latin"``, ``"cyrillic"`` или ``"auto"``. В последнем
        случае текст, в котором есть хоть одно кириллическое слово, переводится
        в латиницу (латинские слова — бренды, адреса — проходят насквозь), а
        текст без кириллицы — в кириллицу.
    :param wordlist: см. :func:`to_cyrillic`; используется только при переводе
        на кириллицу.
    :param normalize: см. :func:`to_latin`.

        >>> transliterate("Бишкек")
        'Bishkek'
        >>> transliterate("Bishkek")
        'Бишкек'
        >>> transliterate("dongolok")
        'дөңгөлөк'
        >>> transliterate("iPhone 15 Pro Max сатылат")
        'iPhone 15 Pro Max satylat'
    """
    text = _check_text(text)
    if direction == "latin":
        return to_latin(text, scheme, normalize=normalize)
    if direction == "cyrillic":
        return to_cyrillic(text, scheme, wordlist)
    if direction != "auto":
        raise ValueError(
            f"direction должен быть 'auto', 'latin' или 'cyrillic', получено {direction!r}"
        )
    cyrillic, latin = _script_word_counts(text, normalize)
    if cyrillic:
        return to_latin(text, scheme, normalize=normalize)
    if latin:
        return to_cyrillic(text, scheme, wordlist)
    return text


def slugify(
    text: str,
    separator: str = "-",
    scheme: SchemeArg = DEFAULT_SCHEME,
    *,
    normalize: bool = True,
) -> str:
    """Сделать из текста ASCII-слаг для URL, файлов и идентификаторов.

        >>> slugify("Ысык-Көл облусу")
        'ysyk-kol-oblusu'
        >>> slugify("Жалал-Абад", separator="_")
        'jalal_abad'
        >>> slugify("№5 мектеп")
        'no5-mektep'
    """
    latin = to_latin(text, scheme, normalize=normalize)
    latin = unicodedata.normalize("NFKD", latin)
    latin = "".join(char for char in latin if not unicodedata.combining(char)).lower()
    slug = re.sub(r"[^a-z0-9]+", lambda _: separator, latin)
    if separator:
        slug = slug.strip(separator)
    return slug


def alphabet_table(scheme: SchemeArg = DEFAULT_SCHEME) -> List[Tuple[str, str]]:
    """Таблица соответствий схемы: список пар (кириллица, латиница).

        >>> alphabet_table()[7]
        ('ж', 'j')
        >>> alphabet_table("bgn_ascii")[15]
        ('ң', 'ng')
        >>> alphabet_table("passport")[10]
        ('й', 'i')
    """
    mapping: Dict[str, str] = get_scheme(scheme).mapping
    return [(letter, mapping.get(letter, "")) for letter in CYRILLIC_LETTERS]
