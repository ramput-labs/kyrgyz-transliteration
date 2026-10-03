"""Движок транслитерации.

Одна функция :func:`apply_table` умеет применять любую подготовленную таблицу
замен (:class:`Table`) в любом направлении: кириллица -> латиница или обратно.
Движок жадный (longest match first) и сам восстанавливает регистр, включая
многосимвольные замены вроде ``ё -> yo`` и аббревиатуры в верхнем регистре.

Неоднозначные буквы разбираются контекстными правилами (:attr:`Table.contextual`):
правило помечает символ служебным маркером, а маркер уже переводится таблицей.
Правило обязано сохранять длину текста: контекст задаётся проверками вида
``(?<=...)`` и ``(?=...)``, а замена — маркером той же длины, что и совпадение.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern, Set, Tuple

__all__ = ["Table", "apply_table", "match_case"]

# Слово — непрерывная последовательность букв. Модификаторы (U+02B0–U+02FF:
# апострофы ʼ ʹ, ударения ˈ) формально считаются буквами, но слово разрывают,
# как и обычный апостроф.
_WORD_RE = re.compile(r"[^\W\d_ʰ-˿]+")
_LINE_RE = re.compile(r"[^\n]+")


@dataclass
class Table:
    """Подготовленная таблица замен для одного направления.

    :param mapping: последовательность символов источника (в нижнем регистре)
        -> результат. Ключи приводятся к нижнему регистру автоматически.
    :param word_initial: замены, действующие только в начале слова; имеют
        приоритет над :attr:`mapping`.
    :param upper: как переводить символы результата в верхний регистр, если
        стандартного ``str.upper()`` недостаточно (например ``i -> İ``).
    :param fold: как приводить символы источника к нижнему регистру, если
        стандартного ``str.lower()`` недостаточно (например ``I -> ı``).
    :param contextual: правила ``(шаблон, маркер)``, которые до основного
        прохода помечают неоднозначные символы; маркеры должны быть описаны в
        :attr:`mapping`.
    """

    mapping: Dict[str, str]
    word_initial: Dict[str, str] = field(default_factory=dict)
    upper: Dict[str, str] = field(default_factory=dict)
    fold: Dict[str, str] = field(default_factory=dict)
    contextual: Tuple[Tuple[Pattern, str], ...] = ()
    max_len: int = field(init=False, default=0)
    _lengths: Dict[str, Tuple[int, ...]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Движок ищет ключи в приведённой к нижнему регистру копии текста,
        # поэтому ключ «Ж» не сработал бы никогда — приводим ключи сами.
        self.mapping = {key.lower(): value for key, value in self.mapping.items()}
        self.word_initial = {key.lower(): value for key, value in self.word_initial.items()}
        # Для каждого первого символа — длины ключей, которые с него начинаются,
        # от длинной к короткой: движок проверяет только их.
        lengths: Dict[str, Set[int]] = {}
        for key in list(self.mapping) + list(self.word_initial):
            if key:
                lengths.setdefault(key[0], set()).add(len(key))
        self._lengths = {
            first: tuple(sorted(sizes, reverse=True)) for first, sizes in lengths.items()
        }
        self.max_len = max((size for sizes in self._lengths.values() for size in sizes), default=0)


def _fold(text: str, fold: Dict[str, str]) -> str:
    """Регистронезависимая копия текста той же длины, что и исходный."""
    if not fold:
        # Быстрый путь. str.lower() строки контекстно-зависим только для
        # заглавной сигмы (Σ -> ς в конце слова), а длину меняют лишь символы
        # вроде 'İ' — в этих случаях идём посимвольно.
        lowered = text.lower()
        if len(lowered) == len(text) and "Σ" not in text:
            return lowered
    chars: List[str] = []
    for char in text:
        if char in fold:
            chars.append(fold[char])
            continue
        lowered = char.lower()
        # ``str.lower()`` для отдельных символов (например 'İ') может вернуть
        # два символа и сбить нумерацию — такие символы оставляем как есть.
        chars.append(lowered if len(lowered) == 1 else char)
    return "".join(chars)


def _upper(text: str, upper: Dict[str, str]) -> str:
    return "".join(upper.get(char, char.upper()) for char in text)


def _capitalize(text: str, upper: Dict[str, str]) -> str:
    if not text:
        return text
    return _upper(text[0], upper) + text[1:]


def _apply_contextual(folded: str, table: Table) -> str:
    """Расставить маркеры контекстных правил, не меняя длину текста."""
    for pattern, marker in table.contextual:
        marked = pattern.sub(marker, folded)
        if len(marked) != len(folded):
            raise ValueError(
                f"контекстное правило {pattern.pattern!r} изменило длину текста: "
                "замена должна быть той же длины, что и совпадение"
            )
        folded = marked
    return folded


def _cased(fragment: str) -> List[str]:
    """Буквы фрагмента, у которых есть регистр.

    Символы без регистра (модификаторы вроде ʼ, порядковые ª/º) не должны
    решать, набрано ли слово КАПСОМ.
    """
    return [char for char in fragment if char.isupper() or char.islower()]


def _is_caps(fragment: str) -> bool:
    # str.isupper(): все буквы с регистром прописные и хотя бы одна есть.
    return fragment.isupper() and len(fragment) > 1 and len(_cased(fragment)) > 1


def match_case(
    original: str,
    replacement: str,
    upper: Optional[Dict[str, str]] = None,
    all_caps: bool = False,
) -> str:
    """Привести ``replacement`` к регистру исходного фрагмента ``original``.

    :param upper: регистровые исключения (например ``{"i": "İ"}``).
    :param all_caps: считать фрагмент частью слова, набранного КАПСОМ.
    """
    upper = upper or {}
    if len(original) == 1:  # самый частый случай: одна буква
        if not original.isupper():
            return replacement
        return _upper(replacement, upper) if all_caps else _capitalize(replacement, upper)
    letters = _cased(original)
    if not letters or not letters[0].isupper():
        return replacement
    if all_caps or (len(letters) > 1 and all(char.isupper() for char in letters)):
        return _upper(replacement, upper)
    return _capitalize(replacement, upper)


def _caps_lock_flags(text: str) -> List[bool]:
    """Для каждой позиции: входит ли она в слово, набранное КАПСОМ.

    Слово из одной прописной буквы («Ч.» в инициалах, «Я») само по себе КАПСОМ
    не считается — иначе «Я жаздым» стало бы «YA jazdym». Но в строке, где все
    остальные слова набраны КАПСОМ («Ч. АЙТМАТОВ АТЫНДАГЫ ...»), и одиночная
    буква печатается прописными.
    """
    flags = [False] * len(text)
    if text.islower():  # ни одной прописной буквы — нечего искать
        return flags
    for line in _LINE_RE.finditer(text):
        content = line.group()
        if content.islower():
            continue
        offset = line.start()
        singles: List[Tuple[int, int]] = []
        long_words_caps = True
        has_long_words = False
        for word in _WORD_RE.finditer(content):
            fragment = word.group()
            if fragment.islower():
                has_long_words = has_long_words or len(fragment) > 1
                long_words_caps = long_words_caps and len(fragment) <= 1
                continue
            cased = _cased(fragment)
            if len(cased) > 1:
                has_long_words = True
                if fragment.isupper():
                    start, end = offset + word.start(), offset + word.end()
                    flags[start:end] = [True] * (end - start)
                else:
                    long_words_caps = False
            elif cased and cased[0].isupper():
                singles.append((offset + word.start(), offset + word.end()))
        if singles and has_long_words and long_words_caps:
            for start, end in singles:
                flags[start:end] = [True] * (end - start)
    return flags


def _in_caps_run(text: str, index: int, size: int) -> bool:
    """Стоит ли фрагмент ``text[index:index + size]`` рядом с прописной буквой.

    Нужно для многобуквенных замен внутри слов со смешанным регистром:
    аббревиатура с приклеенным окончанием «ЖЧКнын» должна дать «JCHKnyn»,
    а не «JChKnyn». Сначала смотрим на букву слева, затем — справа.
    """
    before = text[index - 1] if index else ""
    if before.isupper() or before.islower():
        return before.isupper()
    after = text[index + size] if index + size < len(text) else ""
    if after.isupper() or after.islower():
        return after.isupper()
    return False


def apply_table(text: str, table: Table) -> str:
    """Применить таблицу замен к тексту, сохранив регистр и всё остальное."""
    if not text:
        return ""

    folded = _apply_contextual(_fold(text, table.fold), table)
    caps_lock = _caps_lock_flags(text)
    mapping = table.mapping
    word_initial = table.word_initial
    key_lengths = table._lengths
    upper = table.upper
    result: List[str] = []
    append = result.append
    index = 0
    length = len(text)

    while index < length:
        sizes = key_lengths.get(folded[index])
        if sizes is None:  # ни один ключ не начинается с этого символа
            append(text[index])
            index += 1
            continue

        at_word_start = index == 0 or not text[index - 1].isalpha()
        source = replacement = None
        for size in sizes:
            if index + size > length:
                continue
            chunk = folded[index : index + size]
            if at_word_start and chunk in word_initial:
                source, replacement = chunk, word_initial[chunk]
                break
            if chunk in mapping:
                source, replacement = chunk, mapping[chunk]
                break

        if source is None:
            append(text[index])
            index += 1
            continue

        size = len(source)
        if replacement:
            original = text[index : index + size]
            if size == 1 and not original.isupper():
                append(replacement)  # самый частый случай: строчная буква
            else:
                all_caps = caps_lock[index] or (
                    len(replacement) > 1 and _in_caps_run(text, index, size)
                )
                append(match_case(original, replacement, upper, all_caps=all_caps))

        index += size

    return "".join(result)
