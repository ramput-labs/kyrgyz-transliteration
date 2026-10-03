# -*- coding: utf-8 -*-
"""Нормализация «грязной» кириллицы перед транслитерацией."""
import unicodedata

import pytest

from kyrgyz_transliteration import (
    builtin_names,
    builtin_wordlist,
    detect_script,
    normalize_cyrillic,
    slugify,
    to_latin,
    transliterate,
)
from kyrgyz_transliteration.normalize import CYRILLIC_EXTRAS, LATIN_HOMOGLYPHS, LATIN_LOOKALIKES

NFD = lambda text: unicodedata.normalize("NFD", text)  # noqa: E731


@pytest.mark.parametrize(
    "text,expected",
    [
        # декомпозированные формы и ударения
        (NFD("Чүй Айтматов"), "Chuy Aytmatov"),
        (NFD("ЁЛКА Семёнов"), "YOLKA Semyonov"),
        ("Кыргы́з Респу́бликасы", "Kyrgyz Respublikasy"),
        ("ТУ́Ш", "TUSH"),
        ("ко҃л", "kol"),
        ("тан̧", "tan"),
        # двойники ө / ү / ң
        ("дѳңгѳлѳк Ѳмүр", "dongolok Omur"),
        ("дɵңгɵлɵк Ɵмүр", "dongolok Omur"),
        ("дöңгöлöк Öмүр", "dongolok Omur"),
        ("дӧңгӧлӧк Ӧмүр", "dongolok Omur"),
        ("тüшüнüк Üч", "tushunuk Uch"),
        ("тӱшӱнӱк тұшұнұк", "tushunuk tushunuk"),
        ("таҥ таӊ таӈ таŋ тañ таƞ", "tan tan tan tan tan tan"),
        ("дøңгøлøк дθңгθлθк", "dongolok dongolok"),
        ("Yй-бүлө Yч", "Uy-bulo Uch"),
        # соседние алфавиты
        ("Әлия Ғани Қазақстан Ұлан Һәм Іле", "Aliya Gani Kazakstan Ulan Kham Ile"),
        ("Тоҷикистон Ҳисор", "Tojikiston Khisor"),
        ("Київ Євген Їжак Ґанок", "Kiiv Evgen Ijak Ganok"),
        ("Љубљана Ђорђе Јован", "Lublana Djordje Yovan"),
        ("ЉУБЉАНА", "LUBLANA"),
        ("ѣсть міръ", "est mir"),
        # невидимые символы внутри слова
        ("Рес­публика", "Respublika"),
        ("Кыргыз​стан Кыргыз‍стан Кыргыз⁠стан", "Kyrgyzstan Kyrgyzstan Kyrgyzstan"),
        ("АК­Ч", "AKCH"),
        # латинские двойники внутри кириллических слов
        ("Тaлаc", "Talas"),
        ("Чyй", "Chuy"),
        ("HАРЫН", "NARYN"),
        ("PЕСПУБЛИКА", "RESPUBLIKA"),
        ("xан Hарын", "khan Naryn"),
        ("Кaрaкoл Бишкеk", "Karakol Bishkek"),
        # римские цифры кириллицей, градусы, апостроф вместо ъ
        ("ХХ кылым ХІХ кылымда ХХІ кылым", "XX kylym XIX kylymda XXI kylym"),
        ("ІV чакырылыш", "IV chakyrylysh"),
        ("25°С жылуу", "25°C jyluu"),
        ("об'ект под’езд обʼект", "obekt podezd obekt"),
    ],
)
def test_real_world_input_is_repaired(text, expected):
    assert to_latin(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Facebook'тан",
        "Facebookʼтан",
        "iPhoneго",
        "HPге",
        "TOPтун",
        "HBOдо",
        "Zoomдо",
        "IT-адистер",
        "COVID-19дан",
        "café Бишкек",
        "Türkiye Köln señor Zürich",
        "Бишкек 👨‍👩‍👧",
        "﻿Кыргыз",
        "Кыргыз Республикасы",
        "Кыргыз Республикасы",
        "Х. Карасаев",
        "ХИМИЯ хх",
        "Витамин С",
        "КТРК'да Кыргызстан'дын",
        "XX кылым",
        "а→ب 42",
    ],
)
def test_genuine_latin_symbols_and_clean_text_are_untouched(text):
    assert normalize_cyrillic(text) == text
    assert to_latin(text) == to_latin(text, normalize=False)


def test_normalize_is_identity_on_builtin_words():
    words = builtin_wordlist().words() + builtin_names().words()
    assert all(normalize_cyrillic(word) == word for word in words)


def test_normalize_is_idempotent():
    dirty = "дѳңгѳлѳк Тaлаc Кыргы́з Рес­публика ХХ кылым 25°С"
    once = normalize_cyrillic(dirty)
    assert normalize_cyrillic(once) == once
    assert to_latin(to_latin(dirty)) == to_latin(dirty)


def test_normalize_can_be_switched_off():
    assert to_latin("дѳңгѳлѳк", normalize=False) == "dѳngѳlѳk"
    assert to_latin("дѳңгѳлѳк") == "dongolok"


def test_every_cyrillic_letter_yields_english_letters():
    for start, stop in ((0x0400, 0x0530), (0x1C80, 0x1C90), (0xA640, 0xA6A0)):
        for code in range(start, stop):
            char = chr(code)
            if not char.isalpha():
                continue
            latin = to_latin("а" + char + "а")
            assert all(
                not c.isalpha() or c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                for c in latin
            ), (hex(code), unicodedata.name(char, "?"), latin)


def test_tables_are_lowercase_and_fold_properly():
    for key in list(CYRILLIC_EXTRAS) + list(LATIN_LOOKALIKES):
        assert key == key.lower()
    for key in LATIN_HOMOGLYPHS:
        assert len(key) == 1


def test_slugify_survives_dirty_input():
    assert slugify("дѳңгѳлѳк Ѳмүр") == "dongolok-omur"
    assert slugify("дɵңгɵлɵк") == "dongolok"
    assert slugify("Рес­публика") == "respublika"
    assert slugify(NFD("Чүй Айтматов")) == "chuy-aytmatov"
    assert slugify("№5 мектеп") == "no5-mektep"
    assert slugify("Тaлаc Ошpa") == "talas-oshpa"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Тaлаc", "cyrillic"),
        ("дöңгöлöк", "cyrillic"),
        ("ᲂᲃ", "cyrillic"),
        ("2 × 3", "unknown"),
        ("Бишкек Bishkek", "mixed"),
        ("Толук маалымат: https://www.gov.kg/ky/news", "cyrillic"),
        ("test@mail.kg", "unknown"),
    ],
)
def test_detect_script_counts_words_not_stray_letters(text, expected):
    assert detect_script(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Facebook'тан жана Instagram'дан жазды", "Facebook'tan jana Instagram'dan jazdy"),
        ("Толук маалымат: https://www.gov.kg/ky/news", "Toluk maalymat: https://www.gov.kg/ky/news"),
        ("iPhone 15 Pro Max сатылат", "iPhone 15 Pro Max satylat"),
        ("Жаңылыктар: BBC News Kyrgyz", "Janylyktar: BBC News Kyrgyz"),
        ("Бишкек — Bishkek", "Bishkek — Bishkek"),
        ("таñ", "tan"),
        ("Бишкек", "Bishkek"),
        ("Bishkek", "Бишкек"),
        ("dongolok", "дөңгөлөк"),
        ("2026", "2026"),
    ],
)
def test_auto_direction_prefers_latin_when_any_cyrillic_is_present(text, expected):
    assert transliterate(text) == expected
