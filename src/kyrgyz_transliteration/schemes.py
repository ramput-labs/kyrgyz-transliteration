"""Схемы транслитерации кыргызского языка: кириллица <-> английская латиница.

Библиотека работает только с английским алфавитом: кыргызский текст
записывается буквами ``a-z``, которые англоязычный читатель прочитает близко к
оригиналу. Турецких (``ı ş ç ğ ñ``) и научных (``ž ô ù ņ â``) алфавитов здесь
нет — они дают другое чтение и не являются английскими.

Каждая схема — это таблица «кириллица -> латиница» плюс немного метаданных.
Обратная таблица («латиница -> кириллица») строится автоматически: при
конфликтах побеждает буква, объявленная раньше (например ``и`` и ``й`` в схеме
``passport`` обе дают ``i``, обратно ``i`` читается как ``и``; ``ы`` и ``й``
в схеме ``english`` обе дают ``y``, а обратно ``y`` читается как ``ы``, если
контекстное правило не распознало в нём ``й``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern, Tuple

from .core import Table

__all__ = [
    "CYRILLIC_LETTERS",
    "DEFAULT_SCHEME",
    "MARKER_SHORT_I",
    "MARKER_TE",
    "SCHEMES",
    "Scheme",
    "UnknownSchemeError",
    "get_scheme",
    "list_schemes",
    "register_scheme",
]

#: Кыргызский алфавит (36 букв) в алфавитном порядке.
CYRILLIC_LETTERS = "абвгдеёжзийклмнңоөпрстуүфхцчшщъыьэюя"

#: Схема, используемая по умолчанию.
DEFAULT_SCHEME = "english"

# Служебные маркеры контекстных правил (см. core._apply_contextual). Это
# символы из области частного использования Unicode: в обычном тексте их нет.
MARKER_SHORT_I = ""  # y (или i), который читается как «й»
MARKER_TE = ""  # t в сочетании «тс», которое не является «ц»
MARKER_I = ""  # й, который пишется латиницей как «i» (рядом с ы)
MARKER_YE = ""  # е после ъ/ь: пишется «ye» (подъезд -> podyezd)
MARKER_E = ""  # e, которое читается как «э» внутри слова (ээ)
MARKER_TSE = ""  # t в «ts», которое читается как «ц» (-ция)
MARKER_SOFT = ""  # y перед e после согласной: это «ь» (Vasilyevich)
MARKER_SH = ""  # s в «shch», которое читается как ш + ч (башчы)

_MARKER_RE = re.compile(r"[-]")

# Гласные латиницы. ö/ü/ı встречаются во входных текстах BGN/PCGN и
# общетюркской латиницы (Chüy, Özgön, Bardıq) — для правил это тоже гласные.
_VOWELS = "aeiouöüı"
_CONSONANTS = "bcdfghjklmnpqrstvwxz"

# «ts» после гласной (и после «р»: тартса, жыртса) — обычно стык «т» + «с»
# (айтса, кетсе), а не «ц». Правило идёт первым, пока «y» ещё не заменён
# маркером.
_TS_IS_TE_SE = (re.compile(r"(?<=[" + _VOWELS + r"yr])t(?=s)"), MARKER_TE)

# ...но русские заимствования на -ция/-цион/-цесс/-цент (конституция, полиция,
# процесс, лицей, улица, абзац) читаются как «ц». Кыргызское «т» + «с»
# бывает только на стыке основы и суффикса (-са/-се/-со/-сө, -сын/-син,
# -сыз/-сиз), поэтому следующие буквы предсказуемы гармонией гласных:
# [ei]+tsa, [aouy]+tse, [ei]+tso, «ts» перед согласной и в конце слова у
# кыргызских слов не встречаются.
_TS_IS_TSE = (
    re.compile(
        r"(?<=[" + _VOWELS + r"yr])t(?=s(?:i(?:y[aiu]|i|o|a|n[aeiou])"
        r"|(?<=[ei]ts)a|(?<=[aouy]ts)e|(?<=[ei]ts)o|e[rp]|enz|ey|[^aeiouy]|$|\b))"
    ),
    MARKER_TSE,
)

# «й» и «ы» пишутся одной буквой «y», поэтому разбираются по позиции:
# «yyy» — это ы+й+ы (кыйын), «yy» после гласной — й+ы (айыл), а не после
# гласной — ы+й (мыйзам, но не кыюу = ы+ю), «y» перед узкой гласной — й
# (бийик), «y» между гласной и согласной — й (ай, ой, той), «y» перед «o»
# после a/e/i/u — й (район, майор; после «о» остаётся ё: боёк, коён), в
# остальных случаях — ы (Ысык, кыз). Рядом с «ы» буква «й» пишется как «i»
# (кыйын -> kyiyn, айыл -> aiyl): такое «i» читается как «й».
_Y_RULES = (
    _TS_IS_TSE,
    _TS_IS_TE_SE,
    (re.compile(r"(?<=[aeou])i(?=y)"), MARKER_SHORT_I),  # aiyl, saiyn, Baiysh
    (re.compile(r"(?<![aeiou]y)(?<=y)i"), MARKER_SHORT_I),  # kyiyn, Yiman, myizam
    (re.compile(r"yyy"), "y" + MARKER_SHORT_I + "y"),
    (re.compile(r"(?<=[" + _VOWELS + r"])yy"), MARKER_SHORT_I + "y"),
    (re.compile(r"(?<![" + _VOWELS + r"])yy(?![aou])"), "y" + MARKER_SHORT_I),
    (re.compile(r"y(?=ue)"), MARKER_SHORT_I),
    (re.compile(r"(?<=[" + _VOWELS + r"])y(?=[ei])"), MARKER_SHORT_I),
    (re.compile(r"(?<=[" + _VOWELS + r"])y(?![" + _VOWELS + r"y])"), MARKER_SHORT_I),
    (re.compile(r"(?<=[aeiu])y(?=o)"), MARKER_SHORT_I),
    # «ye» после согласной — это ь + е (Vasilyevich -> Васильевич); в кыргызских
    # словах согласная + й + е и согласная + ы + е не встречаются.
    (re.compile(r"(?<=[" + _CONSONANTS + r"])y(?=e)"), MARKER_SOFT),
    # Долгое «ээ» (жээк, мээ, кээде, Жээнбеков): «ее» в кыргызских словах не
    # бывает. Исключение — русские фамилии на -еев/-еевич.
    (re.compile(r"ee(?!v)"), MARKER_E + MARKER_E),
    # ш + ч на стыке основы и суффикса -чы/-чи/-чу/-чү (башчы, ишчи, ашчы):
    # щ в кыргызских словах не встречается.
    (re.compile(r"(?<=[aeiouy])s(?=hch[yiu](?:[lsndgkmb]|$|\b))"), MARKER_SH),
)

# Правила прямого направления (кириллица -> латиница), общие для английских
# схем: «й» рядом с «ы» пишется как «i» (кыйын -> kyiyn, а не kyyyn), «е»
# после ъ/ь — как «ye» (подъезд -> podyezd, Васильевич -> Vasilyevich).
_FORWARD_RULES = (
    (re.compile(r"(?<=ы)й|й(?=ы)"), MARKER_I),
    (re.compile(r"(?<=[ъь])е"), MARKER_YE),
)

# Маркеры прямого направления и их латиница.
_FORWARD_MARKERS = {MARKER_I: "i", MARKER_YE: "ye"}

# Апострофы и модификаторы, которыми в латинице обозначают ъ и ь.
_TOLERANT = {"ʺ": "ъ", "ʼ": "ь", "ʻ": "ь"}

# Латинские буквы с диакритикой из записи BGN/PCGN, en.wikipedia и общетюркской
# латиницы (Chüy, Özgön, Bardıq): на входе понимаем, на выходе не пишем.
_LATIN_TOLERANT = {
    "ö": "ө", "ü": "ү", "ñ": "ң", "ŋ": "ң", "ı": "ы", "ş": "ш", "ç": "ч", "ğ": "г",
    "·": "",  # интерпункт BGN/PCGN в «n·g» (= н + г, а не ң)
}

# Латинские буквы, которых нет в схемах, но которые встречаются в текстах
# (заимствования, бренды). Нужны только для обратного направления.
_LATIN_EXTRAS = {"q": "к", "w": "в", "x": "кс", "h": "х", "c": "к"}

# Маркеры обратного направления, общие для английских схем.
_REVERSE_MARKERS = {
    MARKER_SHORT_I: "й",
    MARKER_TE: "т",
    MARKER_TSE: "т",
    MARKER_TSE + "s": "ц",
    MARKER_SOFT: "ь",
    MARKER_E: "э",
    MARKER_SH: "с",
    MARKER_SH + "h": "ш",
}


def _reverse_mapping(*markers: str, yery: bool = True) -> Dict[str, str]:
    """Правки обратной таблицы: апострофы и диакритика на входе плюс маркеры правил.

    :param markers: ключи из ``_REVERSE_MARKERS``, которые порождают правила схемы.
    :param yery: читать одиночное ``y`` как ``ы``.
    """
    mapping = dict(_TOLERANT)
    mapping.update(_LATIN_TOLERANT)
    mapping.update({marker: _REVERSE_MARKERS[marker] for marker in markers})
    if yery:
        mapping["y"] = "ы"
    return mapping


# Правки обратной таблицы английских схем: все маркеры _Y_RULES.
def _english_reverse_mapping() -> Dict[str, str]:
    return _reverse_mapping(*_REVERSE_MARKERS)


class UnknownSchemeError(KeyError):
    """Запрошена незарегистрированная схема транслитерации."""


_ASCII_LETTERS_RE = re.compile(r"[A-Za-z]*")


@dataclass
class Scheme:
    """Схема транслитерации.

    :param name: короткое имя, по которому схема запрашивается (регистр не
        важен).
    :param title: человекочитаемое описание.
    :param mapping: кириллица (нижний регистр) -> латиница. Значения — только
        буквы ``A-Za-z`` (или пустая строка).
    :param word_initial: замены только для начала слова.
    :param reverse_mapping: правки для обратной таблицы (латиница -> кириллица).
    :param reverse_word_initial: замены латиница -> кириллица только для начала
        слова (``e -> э``).
    :param reverse_skip: латинские последовательности, которые не надо брать
        в обратную таблицу автоматически.
    :param latin_upper: регистровые исключения латиницы.
    :param latin_lower: обратные регистровые исключения.
    :param forward_contextual: контекстные правила для прямого направления.
    :param reverse_contextual: контекстные правила для обратного направления.
    :param lossy: ``True``, если преобразование в латиницу необратимо.
    :param notes: примечания для документации и CLI.

    Таблицы строятся при первом обращении и кешируются: схему не стоит менять
    после того, как она была использована.
    """

    name: str
    title: str
    mapping: Dict[str, str]
    word_initial: Dict[str, str] = field(default_factory=dict)
    reverse_mapping: Dict[str, str] = field(default_factory=dict)
    reverse_word_initial: Dict[str, str] = field(default_factory=dict)
    reverse_skip: Tuple[str, ...] = ()
    latin_upper: Dict[str, str] = field(default_factory=dict)
    latin_lower: Dict[str, str] = field(default_factory=dict)
    forward_contextual: Tuple[Tuple[Pattern, str], ...] = ()
    reverse_contextual: Tuple[Tuple[Pattern, str], ...] = ()
    lossy: bool = False
    notes: str = ""
    _forward: Optional[Table] = field(default=None, init=False, repr=False, compare=False)
    _reverse: Optional[Table] = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("у схемы должно быть непустое имя")
        if not self.mapping:
            raise ValueError(f"таблица схемы {self.name!r} пуста")
        for label, table in (("mapping", self.mapping), ("word_initial", self.word_initial)):
            invalid = {
                source: target
                for source, target in table.items()
                if not _ASCII_LETTERS_RE.fullmatch(target)
            }
            if invalid:
                raise ValueError(
                    "scheme mappings must contain only English ASCII letters; "
                    f"invalid {label}: {invalid}"
                )
        for label, table in (("mapping", self.mapping), ("word_initial", self.word_initial)):
            bad_keys = [key for key in table if key != key.lower()]
            if bad_keys:
                raise ValueError(
                    f"ключи {label} должны быть в нижнем регистре: {bad_keys}"
                )
        for pattern, marker in self.forward_contextual:
            if _MARKER_RE.search(marker) and not any(
                char in self.mapping for char in _MARKER_RE.findall(marker)
            ):
                raise ValueError(
                    f"маркер правила {pattern.pattern!r} не описан в mapping схемы {self.name!r}"
                )

    def forward_table(self) -> Table:
        """Таблица «кириллица -> латиница»."""
        if self._forward is None:
            self._forward = Table(
                mapping=dict(self.mapping),
                word_initial=dict(self.word_initial),
                upper=dict(self.latin_upper),
                contextual=tuple(self.forward_contextual),
            )
        return self._forward

    def reverse_table(self) -> Table:
        """Таблица «латиница -> кириллица»."""
        if self._reverse is None:
            mapping: Dict[str, str] = {}
            for cyrillic, latin in self.mapping.items():
                if not latin or latin in self.reverse_skip or _MARKER_RE.search(cyrillic):
                    continue
                mapping.setdefault(latin.lower(), cyrillic)
            for latin, cyrillic in _LATIN_EXTRAS.items():
                mapping.setdefault(latin, cyrillic)
            mapping.update({k.lower(): v for k, v in self.reverse_mapping.items()})

            word_initial: Dict[str, str] = {}
            for cyrillic, latin in self.word_initial.items():
                if latin and not _MARKER_RE.search(cyrillic):
                    word_initial.setdefault(latin.lower(), cyrillic)
            word_initial.update({k.lower(): v for k, v in self.reverse_word_initial.items()})

            self._reverse = Table(
                mapping=mapping,
                word_initial=word_initial,
                fold=dict(self.latin_lower),
                contextual=tuple(self.reverse_contextual),
            )
        return self._reverse

    def missing_letters(self) -> List[str]:
        """Буквы кыргызского алфавита, которых нет в таблице схемы."""
        return [letter for letter in CYRILLIC_LETTERS if letter not in self.mapping]


def _scheme(name: str, title: str, mapping: Dict[str, str], **kwargs: object) -> Scheme:
    return Scheme(name=name, title=title, mapping=mapping, **kwargs)  # type: ignore[arg-type]


def _english_mapping(**overrides: str) -> Dict[str, str]:
    mapping = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "ң": "n", "о": "o", "ө": "o", "п": "p", "р": "r", "с": "s",
        "т": "t", "у": "u", "ү": "u", "ф": "f", "х": "kh", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya",
    }
    mapping.update(overrides)
    mapping.update(_FORWARD_MARKERS)  # маркеры объявлены после букв: обратно i -> и
    return mapping


# --- English ----------------------------------------------------------------

_ENGLISH = _scheme(
    "english",
    "Английская латиница — так кыргызы пишут латиницей в жизни",
    _english_mapping(),
    reverse_mapping=_english_reverse_mapping(),
    reverse_word_initial={"e": "э"},
    forward_contextual=_FORWARD_RULES,
    reverse_contextual=_Y_RULES,
    lossy=True,
    notes=(
        "Только буквы a-z: ң -> n, ө -> o, ү -> u, ж -> j, й/ы -> y (рядом друг "
        "с другом й -> i: кыйын -> kyiyn), х -> kh. Обратно ө, ү и ң по одной "
        "латинице не вычисляются, поэтому to_cyrillic() восстанавливает их по "
        "списку кыргызских слов."
    ),
)

# --- English with zh --------------------------------------------------------

_ENGLISH_ASCII = _scheme(
    "english_ascii",
    "То же, что english, но ж -> zh (как в паспортах и русской практике)",
    _english_mapping(ж="zh"),
    reverse_mapping=_english_reverse_mapping(),
    reverse_word_initial={"e": "э"},
    forward_contextual=_FORWARD_RULES,
    reverse_contextual=_Y_RULES,
    lossy=True,
    notes=(
        "Отличается от english только буквой ж -> zh; остальные буквы, включая "
        "ң -> n, ө -> o, ү -> u, те же, и ө/ү/ң так же восстанавливаются словарём."
    ),
)

# --- Legacy alias -----------------------------------------------------------

_BGN = _scheme(
    "bgn",
    "Устаревший алиас схемы english (это НЕ BGN/PCGN: там ö, ü, ng)",
    _english_mapping(),
    reverse_mapping=_english_reverse_mapping(),
    reverse_word_initial={"e": "э"},
    forward_contextual=_FORWARD_RULES,
    reverse_contextual=_Y_RULES,
    lossy=True,
    notes=(
        "Оставлено, чтобы старый код со scheme=\"bgn\" продолжал работать: это "
        "та же таблица, что english. Ближайшая a-z-запись настоящей BGN/PCGN "
        "1979 — схема bgn_ascii."
    ),
)

# --- BGN/PCGN 1979 in plain a-z ---------------------------------------------

_BGN_ASCII = _scheme(
    "bgn_ascii",
    "BGN/PCGN 1979 буквами a-z: ң -> ng, ö/ü -> o/u, апострофы ъ/ь опущены",
    _english_mapping(ң="ng"),
    reverse_mapping=_english_reverse_mapping(),
    reverse_word_initial={"e": "э"},
    forward_contextual=_FORWARD_RULES,
    reverse_contextual=_Y_RULES,
    lossy=True,
    notes=(
        "Таблица BGN/PCGN 1979 — она же национальная система КР для "
        "географических названий и практика en.wikipedia (Jengish Chokusu, "
        "Chong-Kemin) — записанная только буквами a-z: ö -> o, ü -> u, ”/’ "
        "опущены, ң -> ng. Обратно принимает и запись с диакритикой (Chüy, "
        "Özgön, n·g). ң и н + г в латинице совпадают (Narynga), ө/ү "
        "восстанавливаются по словарю."
    ),
)

# --- Passport (ICAO Doc 9303) ------------------------------------------------

# «i» в этой схеме — и «и», и «й»: разбирается по позиции, как «y» в english.
_I_RULES = (
    _TS_IS_TSE,
    _TS_IS_TE_SE,
    (re.compile(r"iii"), "i" + MARKER_SHORT_I + "i"),  # кийиз, бийик
    (re.compile(r"(?<=[" + _VOWELS + r"])ii"), MARKER_SHORT_I + "i"),
    (re.compile(r"(?<![" + _VOWELS + r"])ii(?![aou])"), "i" + MARKER_SHORT_I),  # жийде, ийне
    (re.compile(r"(?<=[" + _VOWELS + r"y])i(?![" + _VOWELS + r"])"), MARKER_SHORT_I),  # Aitmatov
    (re.compile(r"ee(?!v)"), MARKER_E + MARKER_E),
)

_PASSPORT = _scheme(
    "passport",
    "Как в паспорте и ID-карте: таблица кириллицы ICAO Doc 9303 (ж -> zh, й -> i, ю -> iu, я -> ia)",
    {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
        "н": "n", "ң": "n", "о": "o", "ө": "o", "п": "p", "р": "r", "с": "s",
        "т": "t", "у": "u", "ү": "u", "ф": "f", "х": "kh", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "ie", "ы": "y", "ь": "",
        "э": "e", "ю": "iu", "я": "ia",
    },
    reverse_skip=("ie",),  # ie -> и + е (Сариев); ъ не восстанавливается
    reverse_mapping=_reverse_mapping(
        MARKER_SHORT_I, MARKER_TE, MARKER_TSE, MARKER_TSE + "s", MARKER_E, yery=False
    ),
    reverse_word_initial={"e": "э"},
    reverse_contextual=_I_RULES,
    lossy=True,
    notes=(
        "Таблица кириллицы ICAO Doc 9303, часть 3, §6.B — так пишут имена в "
        "паспортах и ID-картах: ж -> zh, й -> i, ю -> iu, я -> ia, ё -> e, "
        "ц -> ts, х -> kh, щ -> shch, ъ -> ie, ь опускается. Букв ө, ү, ң в "
        "таблице ICAO нет — они пишутся o, u, n. Обратно i между гласной и "
        "согласной — й, iu/ia — ю/я; ё, ъ, ь и ө/ү/ң без словаря не "
        "восстанавливаются."
    ),
)

SCHEMES: Dict[str, Scheme] = {
    scheme.name: scheme for scheme in (_ENGLISH, _ENGLISH_ASCII, _BGN, _BGN_ASCII, _PASSPORT)
}


def get_scheme(scheme: str | Scheme = DEFAULT_SCHEME) -> Scheme:
    """Вернуть схему по имени (или саму схему, если передан объект)."""
    if isinstance(scheme, Scheme):
        return scheme
    if not isinstance(scheme, str):
        raise TypeError(
            f"схема задаётся именем или объектом Scheme, получено {scheme!r}"
        )
    try:
        return SCHEMES[scheme.strip().lower()]
    except KeyError:
        known = ", ".join(sorted(SCHEMES))
        raise UnknownSchemeError(
            f"неизвестная схема {scheme!r}; доступны: {known}"
        ) from None


def register_scheme(scheme: Scheme, *, overwrite: bool = False, strict: bool = True) -> Scheme:
    """Зарегистрировать свою схему, чтобы обращаться к ней по имени.

    Имена регистронезависимы. При ``strict=True`` схема без какой-либо из 36
    букв кыргызского алфавита отклоняется.
    """
    key = scheme.name.strip().lower()
    if not overwrite and key in SCHEMES:
        raise ValueError(f"схема {scheme.name!r} уже зарегистрирована")
    if strict and scheme.missing_letters():
        raise ValueError(
            "в схеме {!r} нет букв: {}".format(scheme.name, ", ".join(scheme.missing_letters()))
        )
    SCHEMES[key] = scheme
    return scheme


def list_schemes() -> List[Scheme]:
    """Все зарегистрированные схемы."""
    return list(SCHEMES.values())
