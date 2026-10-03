# -*- coding: utf-8 -*-
"""Круг «кириллица -> латиница -> кириллица» на встроенных списках слов и имён.

Эти тесты фиксируют точный набор слов, которые не восстанавливаются: это
истинные омографы (кол/көл, он/оң) и варианты написания одного имени
(Чынгыз/Чыңгыз). Новое слово в списке, создающее новую коллизию, сразу
проваливает тест.
"""
import time

import pytest

from kyrgyz_transliteration import builtin_names, builtin_wordlist, to_cyrillic, to_latin
from kyrgyz_transliteration.restore import _parse_words, _resource_text

# Пары, которые по-английски пишутся одинаково; побеждает более частотное
# слово (кол, он, тоо, үй, түз помечены звёздочкой в kyrgyz_frequent.txt).
KNOWN_FREQUENT_HOMOGRAPHS = {"көл", "оң", "туз", "төө", "уй"}

# Имена, проигравшие свою латиницу другому написанию того же имени.
KNOWN_NAME_HOMOGRAPHS = {
    "Айал",  # айал -> аял (частотное слово)
    "Кундуз",  # кундуз -> күндүз (частотное слово)
    "Омурбек",  # побеждает Өмүрбек
    "Бактыгул", "Кумушайым", "Омурзаков", "Толонбай",  # побеждают ө/ү-написания
    "Чынгыз", "Чынгызбай", "Чынгызбек", "Чынгызгер", "Чынгызжан", "Чынгыззат",
    "Чынгызлан", "Чынгызмат", "Чынгызмырза", "Чынгызтай", "Чынгызул", "Чынгызхан",
}


@pytest.mark.parametrize("scheme", ["english", "english_ascii", "passport"])
@pytest.mark.parametrize("case", [str.lower, str.capitalize, str.upper], ids=["lower", "Title", "UPPER"])
def test_frequent_wordlist_round_trips_except_the_known_homographs(scheme, case):
    words = builtin_wordlist().words()
    # Аббревиатуры (ЕАЭБ) в списке записаны прописными: их регистр не меняем.
    targets = [case(word) if word == word.lower() else word for word in words]
    broken = {
        word
        for word, target in zip(words, targets)
        if to_cyrillic(to_latin(target, scheme), scheme) != target
    }
    assert broken == KNOWN_FREQUENT_HOMOGRAPHS


def test_bgn_ascii_recovers_ong_thanks_to_ng():
    broken = {word for word in builtin_wordlist().words() if to_cyrillic(to_latin(word, "bgn_ascii"), "bgn_ascii") != word}
    assert broken == KNOWN_FREQUENT_HOMOGRAPHS - {"оң"}


def test_frequent_wordlist_has_no_ambiguous_keys_and_no_duplicates():
    assert builtin_wordlist().ambiguous_keys() == []
    parsed = [word.lower() for word, _ in _parse_words(_resource_text("kyrgyz_frequent.txt"))]
    assert len(parsed) == len(set(parsed))


@pytest.mark.parametrize("case", [str.capitalize, str.upper], ids=["Title", "UPPER"])
def test_names_round_trip_except_the_known_homographs(case):
    names = builtin_names().words()
    assert len(names) > 4900
    broken = {name for name in names if to_cyrillic(to_latin(case(name))) != case(name)}
    assert broken == KNOWN_NAME_HOMOGRAPHS


def test_names_file_header_matches_its_content():
    text = _resource_text("kyrgyz_names.txt")
    names = {word for word, _ in _parse_words(text)}
    assert f"# Total: {len(names)} unique names" in text
    assert not any("йй" in name.lower() for name in names)


@pytest.mark.parametrize(
    "latin,expected",
    [
        ("Aytsa", "Айтса"),
        ("Akim", "Аким"),
        ("Bolotov", "Болотов"),
        ("Jamgyrlar", "Жамгырлар"),
        ("Kyzylsu", "Кызылсу"),
        ("Nurdoolod", "Нурдөөлөт"),
    ],
)
def test_name_index_does_not_hijack_ordinary_capitalised_words(latin, expected):
    assert to_cyrillic(latin) == expected


@pytest.mark.parametrize(
    "latin,expected",
    [
        ("Omurov", "Өмүров"),
        ("Omurova", "Өмүрова"),
        ("Omurbekov", "Өмүрбеков"),
        ("Kuchukov", "Күчүков"),
        ("Dongolokov", "Дөңгөлөков"),
        ("dongolokton", "дөңгөлөктөн"),
        ("Kochoev", "Көчөев"),
    ],
)
def test_vowel_harmony_skips_russian_surname_endings(latin, expected):
    assert to_cyrillic(latin) == expected


def test_reverse_direction_is_fast_on_capitalised_text():
    text = "Respublikasynyn Jogorku Keneshi " * 200
    start = time.perf_counter()
    result = to_cyrillic(text)
    assert time.perf_counter() - start < 1.0
    assert result == "Республикасынын Жогорку Кеңеши " * 200


def test_compressed_data_is_read_the_same_way(monkeypatch):
    """В wheel списки лежат как *.txt.gz (hatch_build.py) — текст должен совпасть."""
    import gzip

    from kyrgyz_transliteration import restore

    plain = {name: restore._read_resource(name) for name in ("kyrgyz_names.txt", "kyrgyz_frequent.txt")}
    packed = {name + ".gz": gzip.compress(raw, mtime=0) for name, raw in plain.items()}

    def read(name):
        if name in packed:
            return packed[name]
        raise FileNotFoundError(name)

    monkeypatch.setattr(restore, "_read_resource", read)
    for name, raw in plain.items():
        assert restore._resource_text(name) == raw.decode("utf-8-sig")
