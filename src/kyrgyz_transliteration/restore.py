"""Восстановление кыргызских слов из английской латиницы.

В английском алфавите нет ни ө, ни ү, ни ң: схема `english` пишет их как o, u
и n, и по такой записи выбрать между «дөңгөлөк» и «донголок» нельзя — оба
слова подчиняются гармонии гласных. Единственный надёжный способ — словарь.

:class:`Wordlist` индексирует кыргызские слова по «сплющенному» ASCII-ключу
(``дөңгөлөк`` -> ``dongolok``, ``donggolok``). При разборе латиницы слово
ищется в словаре: нашлось ровно одно — берём его, иначе слово разбирается
обычными правилами схемы. Если точного совпадения нет, ищется самая длинная
основа из словаря, а к оставшемуся суффиксу применяется гармония гласных
(``dongolokton`` -> ``дөңгөлөктөн``).
"""

from __future__ import annotations

import gzip
import re
import unicodedata
from collections import Counter
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from .core import Table, _is_caps, apply_table, match_case
from .schemes import DEFAULT_SCHEME, Scheme, get_scheme

__all__ = [
    "Wordlist",
    "ascii_key",
    "builtin_names",
    "builtin_wordlist",
    "restore_words",
]

# Слово вместе с дефисами внутри: «Ысык-Көл» и «үй-бүлө» стоит искать в
# словаре целиком — по отдельности «көл» от «кол» не отличить.
_WORD_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")

# Варианты латинской записи каждой кыргызской буквы: так их набирают на
# практике. Из них строятся все ключи слова — ө и ү неотличимы от о и у, ң
# пишут и как n, и как ng, ы и й — и как y, и как i, ж — как j или zh,
# ю/я — как yu/ya (english) или iu/ia (паспорт).
_KEY_VARIANTS = {
    "а": ("a",), "б": ("b",), "в": ("v",), "г": ("g",), "д": ("d",),
    "е": ("e",), "ё": ("yo", "e", "io"), "ж": ("j", "zh"), "з": ("z",),
    "и": ("i",), "й": ("y", "i"), "к": ("k",), "л": ("l",), "м": ("m",),
    "н": ("n",), "ң": ("n", "ng"), "о": ("o",), "ө": ("o", "oe"), "п": ("p",),
    "р": ("r",), "с": ("s",), "т": ("t",), "у": ("u",), "ү": ("u", "ue"),
    "ф": ("f",), "х": ("h", "kh", "x"), "ц": ("ts", "c"), "ч": ("ch",), "ш": ("sh",),
    "щ": ("shch", "sch"), "ъ": ("", "ie"), "ы": ("y", "i"), "ь": ("",), "э": ("e",),
    "ю": ("yu", "iu"), "я": ("ya", "ia"),
}

# Для имён «ы» индексируется только как y: иначе обычное слово «аким»
# (Akim) подменялось бы именем Акым.
_NAME_KEY_VARIANTS = dict(_KEY_VARIANTS, ы=("y",))

# Для поиска по началу слова (основа + суффикс) варианты, оканчивающиеся на
# гласную (ө -> oe, ү -> ue, ё -> e), не годятся: в «Kochoev» основа «көчө»
# совпала бы с «kochoe» и съела букву «е» следующей морфемы.
_STEM_KEY_VARIANTS = dict(_KEY_VARIANTS, ө=("o",), ү=("u",), ё=("yo",), ъ=("",))

#: Ограничение на число ключей одного слова.
MAX_KEYS_PER_WORD = 512
NAME_TRIGRAM_MIN_SCORE = 0.72
NAME_TRIGRAM_MIN_MARGIN = 0.08
#: Нечёткий поиск имени допускает разницу в длине не больше одной буквы:
#: «Bolotov» не должен превращаться в «Бекболотов».
NAME_TRIGRAM_MAX_LENGTH_DIFF = 1
_TRIGRAM_CANDIDATES = 40

# Сведение допустимых латинских вариантов к ASCII.
_FOLD = {
    "ö": "o", "ü": "u", "ʺ": "", "ʹ": "", "ʼ": "", "ʻ": "", "'": "", "’": "",
}

_BOM = "﻿"

# Конечный согласный основы озвончается перед гласным окончанием:
# китеп -> китеби, эшик -> эшиги, дөңгөлөк -> дөңгөлөгү. Такие основы
# заводятся в словаре отдельно, иначе окончание не отделить.
_FINAL_VOICING = {"к": "г", "п": "б"}

_FRONT_VOWELS = "еёиөүэ"
_BACK_VOWELS = "аоуы"
_FRONT_HARMONY = {"о": "ө", "у": "ү", "О": "Ө", "У": "Ү"}
_BACK_HARMONY = {"и": "ы", "И": "Ы"}

# Русские фамильные окончания гармонии гласных не подчиняются: Өмүров,
# Жээнбеков, Күчүков, а не «Өмүрөв».
_RUSSIAN_TAIL_RE = re.compile(r"(ов|ев|ова|ева|ович|евич|овна|евна)$", re.IGNORECASE)

#: Минимальная длина основы при поиске по началу слова.
DEFAULT_MIN_STEM = 4

_SUFFIX_TABLES: Dict[str, Table] = {}


def _suffix_table(scheme: str | Scheme = DEFAULT_SCHEME) -> Table:
    """Таблица для разбора суффикса — обратная таблица схемы без правил начала слова.

    Суффикс стоит в конце слова, поэтому его «e» — это «е», а не «э»
    (``mektepte`` -> «мектепте», а не «мектептэ»).
    """
    resolved = get_scheme(scheme)
    table = _SUFFIX_TABLES.get(resolved.name)
    if table is None:
        base = resolved.reverse_table()
        table = Table(
            mapping=dict(base.mapping),
            fold=dict(base.fold),
            contextual=tuple(base.contextual),
        )
        _SUFFIX_TABLES[resolved.name] = table
    return table


def ascii_key(word: str) -> str:
    """ASCII-ключ слова: нижний регистр, без диакритики и апострофов.

        >>> ascii_key("donggolok")
        'donggolok'
        >>> ascii_key("Kyrgyz")
        'kyrgyz'
        >>> ascii_key("Chuy")
        'chuy'
    """
    if word.isascii():  # быстрый путь: латиница без диакритики
        return word.lower().replace("'", "")
    return "".join(_char_key(char) for char in word)


def _strip_marks(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


_CHAR_KEYS: Dict[str, str] = {}


def _char_key(char: str) -> str:
    """ASCII-ключ одного символа (кешируется: символов в тексте немного)."""
    folded = _CHAR_KEYS.get(char)
    if folded is None:
        lowered = char.lower()
        if len(lowered) != 1:  # 'İ'.lower() — это два символа
            lowered = _strip_marks(lowered) or char
        folded = _FOLD[lowered] if lowered in _FOLD else _strip_marks(lowered)
        _CHAR_KEYS[char] = folded
    return folded


def _key_with_offsets(word: str) -> Tuple[str, List[int]]:
    """ASCII-ключ и длина ключа после каждого символа исходного слова.

    Длины нужны, чтобы по границе основы в ключе найти границу в самом слове:
    один символ может дать два (лигатура ``ﬁ`` -> ``fi``) или ни одного
    (апостроф вместо ъ и ь).
    """
    chars = [_char_key(char) for char in word]
    offsets = [0]
    for folded in chars:
        offsets.append(offsets[-1] + len(folded))
    return "".join(chars), offsets


def _trigrams(key: str) -> FrozenSet[str]:
    """Символьные триграммы с маркерами границ слова."""
    padded = "^^" + key + "$$"
    return frozenset(padded[index : index + 3] for index in range(len(padded) - 2))


def _trigram_similarity(left: str, right: str) -> float:
    """Коэффициент Дайса для двух наборов триграмм."""
    left_grams = _trigrams(left)
    right_grams = _trigrams(right)
    if not left_grams or not right_grams:
        return 0.0
    return 2.0 * len(left_grams & right_grams) / (len(left_grams) + len(right_grams))


class Wordlist:
    """Словарь кыргызских слов, проиндексированный по ASCII-ключам.

    Слова задаются кириллицей. Ключ, на который претендуют два разных слова
    (``кол`` и ``көл`` -> ``kol``), считается неоднозначным и не используется:
    такое слово разберётся обычными правилами схемы.

        >>> words = Wordlist(["дөңгөлөк", "түшүнүк"])
        >>> words.lookup("dongolok")
        'дөңгөлөк'
        >>> words.lookup("tushunuk")
        'түшүнүк'
        >>> words.lookup("kompyuter") is None
        True

    Спор за ключ можно решить, добавив более частотное слово как
    предпочтительное: ``уй`` и ``үй`` оба пишутся ``uy``, но «үй» встречается
    несравнимо чаще, и без такой пометки ү потерялось бы.

        >>> pair = Wordlist(["уй"]).add(["үй"], preferred=True)
        >>> pair.lookup("uy")
        'үй'
        >>> pair.ambiguous_keys()
        []
    """

    def __init__(
        self,
        words: Iterable[str] = (),
        *,
        min_stem: int = DEFAULT_MIN_STEM,
        key_variants: Optional[Dict[str, Tuple[str, ...]]] = None,
        stems: bool = True,
    ) -> None:
        self.min_stem = min_stem
        self._variants = key_variants if key_variants is not None else _KEY_VARIANTS
        self._index_stems = stems
        self._forms: Dict[str, Optional[str]] = {}
        self._pinned_keys: Set[str] = set()
        self._stem_forms: Dict[str, Optional[str]] = {}
        self._stem_pinned: Set[str] = set()
        self._stems: Dict[str, Optional[str]] = {}
        self._preferred_words: Set[str] = set()
        self._words: Set[str] = set()
        self._trigram_words: Set[str] = set()
        self._trigram_index: Dict[str, Set[str]] = {}
        self._trigram_keys: Dict[str, Tuple[FrozenSet[str], ...]] = {}
        self._trigram_cache: Dict[Tuple[str, float, float], Optional[str]] = {}
        self._name_index: Optional[Wordlist] = None
        self.add(words)

    def add(
        self,
        words: Iterable[str],
        *,
        preferred: bool = False,
        trigram: bool = False,
    ) -> Wordlist:
        """Добавить слова (кириллицей). Возвращает сам словарь.

        :param preferred: закрепить за словом его ключи, отобрав их у обычных
            слов. Так задаётся более частотное чтение неоднозначной латиницы
            (``uy`` -> «үй», а не «уй»). Порядок добавления при этом не важен;
            если на один ключ претендуют два предпочтительных слова, ключ
            снова становится неоднозначным.
        :param trigram: добавить слово в индекс нечёткого поиска имён.
        """
        self._trigram_cache.clear()
        for word in words:
            word = word.strip().lstrip(_BOM)
            if not word:
                continue
            self._words.add(word)
            if trigram:
                self._add_trigram_word(word)
            if preferred:
                self._preferred_words.add(word)
            for key in self._keys(word, self._variants):
                self._claim(self._forms, self._pinned_keys, key, word, preferred)
            if self._index_stems:
                for key in self._keys(word, _STEM_KEY_VARIANTS):
                    self._claim(self._stem_forms, self._stem_pinned, key, word, preferred)
                self._add_voiced_stem(word)
        return self

    def _add_trigram_word(self, word: str) -> None:
        self._trigram_words.add(word)
        grams = tuple(_trigrams(key) for key in self._keys(word, self._variants))
        self._trigram_keys[word] = grams
        for key_grams in grams:
            for trigram in key_grams:
                self._trigram_index.setdefault(trigram, set()).add(word)

    def _add_voiced_stem(self, word: str) -> None:
        """Завести озвончённую основу слова: китеп -> китеб, эшик -> эшиг.

        Она нужна только для поиска по началу слова: сама по себе такая
        основа словом не является, поэтому в общий индекс не попадает.
        """
        voiced = _FINAL_VOICING.get(word[-1:].lower())
        if voiced is None:
            return
        stem = word[:-1] + voiced
        for key in self._keys(stem, _STEM_KEY_VARIANTS):
            if self._stems.get(key, stem) != stem:
                self._stems[key] = None  # основу делят два слова
            else:
                self._stems[key] = stem

    @staticmethod
    def _claim(
        forms: Dict[str, Optional[str]],
        pinned: Set[str],
        key: str,
        word: str,
        preferred: bool,
    ) -> None:
        """Записать ключ за словом с учётом уже занятых и закреплённых ключей."""
        taken = forms.get(key, word) != word  # на ключ претендует другое слово
        if preferred:
            forms[key] = None if taken and key in pinned else word
            pinned.add(key)
        elif key not in pinned:
            forms[key] = None if taken else word

    def copy(self) -> Wordlist:
        """Независимая копия словаря — вместе с предпочтительными словами.

            >>> mine = builtin_wordlist().copy().add(["көгүчкөн"])
            >>> mine.lookup("koguchkon")
            'көгүчкөн'
            >>> "koguchkon" in builtin_wordlist()
            False
        """
        twin = Wordlist(min_stem=self.min_stem, key_variants=self._variants, stems=self._index_stems)
        twin._forms = dict(self._forms)
        twin._pinned_keys = set(self._pinned_keys)
        twin._stem_forms = dict(self._stem_forms)
        twin._stem_pinned = set(self._stem_pinned)
        twin._stems = dict(self._stems)
        twin._preferred_words = set(self._preferred_words)
        twin._words = set(self._words)
        twin._trigram_words = set(self._trigram_words)
        twin._trigram_index = {
            trigram: set(words) for trigram, words in self._trigram_index.items()
        }
        twin._trigram_keys = dict(self._trigram_keys)
        twin._name_index = self._name_index
        return twin

    def merge(self, other: Wordlist) -> Wordlist:
        """Добавить слова другого словаря вместе с его предпочтительными чтениями."""
        self.add(
            (word for word in other.words() if word not in other._preferred_words),
            trigram=False,
        )
        self.add(other.preferred(), preferred=True, trigram=False)
        for word in other._trigram_words:
            self._add_trigram_word(word)
        return self

    @staticmethod
    def _keys(word: str, variants: Optional[Dict[str, Tuple[str, ...]]] = None) -> Set[str]:
        """Все ASCII-записи слова, которые может набрать человек."""
        table = variants if variants is not None else _KEY_VARIANTS
        keys = [""]
        for char in word.lower():
            options = table.get(char)
            if options is None:
                folded = ascii_key(char)
                options = (folded,) if folded else ("",)
            keys = [key + option for key in keys for option in options]
            if len(keys) > MAX_KEYS_PER_WORD:
                keys = keys[:MAX_KEYS_PER_WORD]
        return {key for key in keys if key}

    @classmethod
    def from_file(
        cls,
        path: str,
        *,
        min_stem: int = DEFAULT_MIN_STEM,
        key_variants: Optional[Dict[str, Tuple[str, ...]]] = None,
        stems: bool = True,
    ) -> Wordlist:
        """Прочитать список слов из файла: одно слово в строке, ``#`` — комментарий.

        Файл читается как UTF-8; BOM (Блокнот сохраняет UTF-8 с ним) не мешает.
        Строка, начинающаяся со звёздочки (``*үй``), задаёт предпочтительное
        чтение — см. :meth:`add`.
        """
        with open(path, encoding="utf-8-sig") as handle:
            return cls.from_text(
                handle.read(), min_stem=min_stem, key_variants=key_variants, stems=stems
            )

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        min_stem: int = DEFAULT_MIN_STEM,
        key_variants: Optional[Dict[str, Tuple[str, ...]]] = None,
        stems: bool = True,
    ) -> Wordlist:
        """То же, что :meth:`from_file`, но список слов уже прочитан в строку."""
        words = cls(min_stem=min_stem, key_variants=key_variants, stems=stems)
        parsed = _parse_words(text)
        words.add(word for word, preferred in parsed if not preferred)
        words.add((word for word, preferred in parsed if preferred), preferred=True)
        return words

    def lookup(self, key: str) -> Optional[str]:
        """Слово по ASCII-ключу или ``None``, если его нет или ключ неоднозначен."""
        normalized = ascii_key(key)
        form = self._forms.get(normalized)
        if form is not None:
            return form
        if self._name_index is not None and normalized not in self._forms:
            return self._name_index.lookup(normalized)
        return None

    def lookup_regular(self, key: str) -> Optional[str]:
        """Поиск только по обычным словам, без индекса имён."""
        return self._forms.get(ascii_key(key))

    def attach_name_index(self, names: Wordlist) -> Wordlist:
        """Подключить отдельный индекс имён, не смешивая его ключи с обычными словами."""
        self._name_index = names
        return self

    def lookup_trigram(
        self,
        key: str,
        *,
        min_score: float = NAME_TRIGRAM_MIN_SCORE,
        min_margin: float = NAME_TRIGRAM_MIN_MARGIN,
    ) -> Optional[str]:
        """Найти близкое имя по перекрытию символьных триграмм.

        Нечёткий поиск ограничен словами, добавленными с ``trigram=True``.
        Возвращается только однозначный лучший кандидат, отличающийся по длине
        не больше чем на одну букву; это предотвращает случайную замену обычных
        слов или похожих имён.
        """
        normalized = ascii_key(key)
        if self._name_index is not None and not self._trigram_words:
            return self._name_index.lookup_trigram(
                normalized,
                min_score=min_score,
                min_margin=min_margin,
            )
        if len(normalized) < 3 or not self._trigram_words:
            return None
        cache_key = (normalized, min_score, min_margin)
        if cache_key in self._trigram_cache:
            return self._trigram_cache[cache_key]

        query = _trigrams(normalized)
        shared: Counter = Counter()
        for trigram in query:
            for word in self._trigram_index.get(trigram, ()):
                shared[word] += 1
        result: Optional[str] = None
        if shared:
            ranked: List[Tuple[float, str]] = []
            for word, _ in shared.most_common(_TRIGRAM_CANDIDATES):
                for grams in self._trigram_keys.get(word, ()):
                    # Длина ключа = число триграмм - 3 (два маркера с каждой стороны).
                    if abs(len(grams) - len(query)) > NAME_TRIGRAM_MAX_LENGTH_DIFF:
                        continue
                    score = 2.0 * len(query & grams) / (len(query) + len(grams))
                    ranked.append((score, word))
            ranked.sort(reverse=True)
            if ranked and ranked[0][0] >= min_score:
                best_score = ranked[0][0]
                best_words = {word for score, word in ranked if score == best_score}
                if len(best_words) == 1:
                    next_score = max(
                        (score for score, word in ranked if word not in best_words),
                        default=0.0,
                    )
                    if best_score - next_score >= min_margin:
                        result = next(iter(best_words))
        self._trigram_cache[cache_key] = result
        return result

    def lookup_stem(self, key: str) -> Optional[Tuple[str, int]]:
        """Самая длинная однозначная основа: ``(основа, длина ключа основы)``.

        Основой может быть как само слово (``дөңгөлөк`` в ``dongolokton``),
        так и его озвончённая форма (``дөңгөлөг`` в ``dongologu``). Остаток
        после основы не может содержать дефис: «Shamalduu-Sai» — это два слова.
        """
        for size in range(len(key) - 1, self.min_stem - 1, -1):
            if "-" in key[size:]:
                continue
            head = key[:size]
            form = self._stem_forms.get(head)
            if form is None:
                form = self._stems.get(head)
            if form is not None:
                return form, size
        return None

    def ambiguous_keys(self) -> List[str]:
        """Ключи, на которые претендует больше одного слова."""
        return sorted(key for key, form in self._forms.items() if form is None)

    def words(self) -> List[str]:
        """Все слова словаря."""
        return sorted(self._words)

    def preferred(self) -> List[str]:
        """Слова, помеченные как предпочтительное чтение неоднозначной латиницы."""
        return sorted(self._preferred_words)

    def __len__(self) -> int:
        return len(self._words)

    def __contains__(self, word: str) -> bool:
        return self.lookup(word) is not None

    def __repr__(self) -> str:  # pragma: no cover - для отладки
        return f"Wordlist({len(self._words)} слов, {len(self._forms)} ключей)"


def _parse_words(text: str) -> List[Tuple[str, bool]]:
    r"""Разобрать список слов в пары ``(слово, предпочтительное ли)``.

    Одно слово в строке, ``#`` — комментарий, ``*`` в начале строки помечает
    предпочтительное чтение неоднозначного ключа (см. :meth:`Wordlist.add`).

        >>> _parse_words("# дом\nуй\n*үй\n")
        [('уй', False), ('үй', True)]
    """
    words = []
    for line in text.lstrip(_BOM).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        preferred = line.startswith("*")
        word = line.lstrip("*").strip()
        if word:
            words.append((word, preferred))
    return words


_BUILTIN: Optional[Wordlist] = None
_BUILTIN_NAMES: Optional[Wordlist] = None


def _read_resource(filename: str) -> bytes:
    try:
        from importlib.resources import files

        # Через родительский (обычный) пакет: на Python 3.9 files() не умеет
        # пакеты без __init__.py.
        return files("kyrgyz_transliteration").joinpath("data").joinpath(filename).read_bytes()
    except (ImportError, AttributeError, TypeError):  # pragma: no cover - старые Python
        import os

        with open(os.path.join(os.path.dirname(__file__), "data", filename), "rb") as handle:
            return handle.read()


def _resource_text(filename: str) -> str:
    """Текст файла данных пакета.

    В установленном пакете (wheel) списки слов лежат сжатыми — ``*.txt.gz``,
    в исходниках и при установке ``pip install -e`` — обычным текстом.
    """
    try:
        data = gzip.decompress(_read_resource(filename + ".gz"))
    except OSError:  # сжатой копии нет (FileNotFoundError — подкласс OSError)
        data = _read_resource(filename)
    return data.decode("utf-8-sig")


def builtin_names() -> Wordlist:
    """Встроенный список кыргызских имён и фамилий (кешируется).

    Возвращаемый объект менять нельзя: перед добавлением своих имён сделайте
    :meth:`Wordlist.copy`.
    """
    global _BUILTIN_NAMES
    if _BUILTIN_NAMES is None:
        # Имена ищутся только целиком: индекс основ им не нужен.
        names = Wordlist.from_text(
            _resource_text("kyrgyz_names.txt"), key_variants=_NAME_KEY_VARIANTS, stems=False
        )
        for name in names.words():  # то же, что add(..., trigram=True), без повторной индексации ключей
            names._add_trigram_word(name)
        _BUILTIN_NAMES = names
    return _BUILTIN_NAMES


def builtin_wordlist() -> Wordlist:
    """Встроенный список частотных кыргызских слов (кешируется).

        >>> len(builtin_wordlist()) > 200
        True
        >>> builtin_wordlist().lookup("dongolok")
        'дөңгөлөк'
    """
    global _BUILTIN
    if _BUILTIN is None:
        words = Wordlist.from_text(_resource_text("kyrgyz_frequent.txt"))
        words.attach_name_index(builtin_names())
        _BUILTIN = words
    return _BUILTIN


def _harmonize(suffix: str, stem: str) -> str:
    """Согласовать гласные суффикса с основой (гармония гласных).

    Русские фамильные окончания (-ов, -ев, -ова, -евич...) не трогаются.
    """
    tail = ""
    match = _RUSSIAN_TAIL_RE.search(suffix)
    if match:
        suffix, tail = suffix[: match.start()], suffix[match.start() :]
    last = ""
    for char in reversed(stem.lower()):
        if char in _FRONT_VOWELS or char in _BACK_VOWELS:
            last = char
            break
    if not last:
        return suffix + tail
    table = _FRONT_HARMONY if last in _FRONT_VOWELS else _BACK_HARMONY
    return "".join(table.get(char, char) for char in suffix) + tail


def _restore_compound(token: str, wordlist: Wordlist, scheme: Scheme) -> Optional[str]:
    """Разобрать составное слово по частям, если целиком его в словаре нет.

    Части, которых в словаре тоже нет, остаются латиницей — их разберут
    правила схемы (``uy-bulo`` -> «үй-бүлө», ``ata-ene`` -> ``ata-ene``).
    """
    parts = token.split("-")
    restored = [_restore_token(part, wordlist, scheme) for part in parts]
    if all(form is None for form in restored):
        return None
    return "-".join(
        part if form is None else form for part, form in zip(parts, restored)
    )


def restore_words(
    text: str, wordlist: Wordlist, scheme: str | Scheme = DEFAULT_SCHEME
) -> str:
    """Заменить латинские слова на кириллические по словарю.

    Слова, которых в словаре нет, остаются как есть — их разберёт обычная
    транслитерация (:func:`kyrgyz_transliteration.to_cyrillic` делает это сама:
    словарь у неё включён по умолчанию). Схема нужна, чтобы прочитать
    окончание после найденной основы её правилами.

        >>> restore_words("Dongolok jok", builtin_wordlist())
        'Дөңгөлөк жок'
        >>> restore_words("dongolokton", builtin_wordlist())
        'дөңгөлөктөн'
    """
    resolved = get_scheme(scheme)
    result: List[str] = []
    position = 0
    restored: Dict[str, Optional[str]] = {}  # слова в тексте повторяются

    for match in _WORD_RE.finditer(text):
        token = match.group()
        if token in restored:
            replacement = restored[token]
        else:
            replacement = _restore_token(token, wordlist, resolved)
            if replacement is None and "-" in token:
                replacement = _restore_compound(token, wordlist, resolved)
            restored[token] = replacement
        if replacement is None:
            continue
        result.append(text[position : match.start()])
        result.append(replacement)
        position = match.end()

    result.append(text[position:])
    return "".join(result)


def _restore_token(token: str, wordlist: Wordlist, scheme: Scheme) -> Optional[str]:
    """Кириллическое написание слова по словарю или ``None``, если не нашлось."""
    key, offsets = _key_with_offsets(token)
    if not key.isascii() or not key.replace("-", "").isalpha():
        return None

    capitalized = token[:1].isupper()
    form = wordlist.lookup(key) if capitalized else wordlist.lookup_regular(key)
    if form is not None:
        return _match_case(token, form)

    found = wordlist.lookup_stem(key)
    if found is not None:
        stem, size = found
        try:
            split = offsets.index(size)
        except ValueError:  # граница основы попала внутрь диграфа
            split = -1
        if split > 0:
            suffix = apply_table(token[split:], _suffix_table(scheme))
            return _match_case(token[:split], stem) + _harmonize(suffix, stem)

    if capitalized and "-" not in key:
        form = wordlist.lookup_trigram(key)
        if form is not None:
            return _match_case(token, form)
    return None


def _match_case(token: str, form: str) -> str:
    """Привести слово к регистру набранного — у составных слов по частям.

    «Ysyk-Kol» — это «Ысык-Көл», а не «Ысык-көл»: с прописной каждая часть.
    """
    caps = _is_caps(token)
    parts, forms = token.split("-"), form.split("-")
    if len(parts) != len(forms):
        return match_case(token, form, all_caps=caps)
    return "-".join(
        match_case(part, piece, all_caps=caps) for part, piece in zip(parts, forms)
    )
