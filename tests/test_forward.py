# -*- coding: utf-8 -*-
"""Прямое направление (кириллица -> латиница): полный алфавит, регистр, правила."""
import random

import pytest

from kyrgyz_transliteration import CYRILLIC_LETTERS, SCHEMES, alphabet_table, to_cyrillic, to_latin

ASCII_LETTERS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")

ENGLISH = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "ң": "n",
    "о": "o", "ө": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ү": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
EXPECTED = {
    "english": ENGLISH,
    "bgn": ENGLISH,
    "english_ascii": dict(ENGLISH, ж="zh"),
    "bgn_ascii": dict(ENGLISH, ң="ng"),
    "passport": dict(ENGLISH, ё="e", ж="zh", й="i", ъ="ie", ю="iu", я="ia"),
}


def test_all_built_in_schemes_are_registered():
    assert sorted(SCHEMES) == ["bgn", "bgn_ascii", "english", "english_ascii", "passport"]


@pytest.mark.parametrize("scheme", sorted(EXPECTED))
def test_alphabet_table_matches_the_documented_letters(scheme):
    assert dict(alphabet_table(scheme)) == EXPECTED[scheme]


@pytest.mark.parametrize("scheme", sorted(EXPECTED))
@pytest.mark.parametrize("letter", list(CYRILLIC_LETTERS))
def test_every_letter_in_every_case(scheme, letter):
    latin = EXPECTED[scheme][letter]
    assert to_latin(letter, scheme) == latin
    assert to_latin(letter.upper(), scheme) == latin.capitalize()
    # Внутри слова КАПСОМ многобуквенная замена тоже печатается прописными.
    assert to_latin("А" + letter.upper() + "А", scheme) == "A" + latin.upper() + "A"
    assert to_latin("а" + letter + "а", scheme) == "a" + latin + "a"


@pytest.mark.parametrize("scheme", sorted(EXPECTED))
def test_random_kyrgyz_text_gives_only_english_letters(scheme):
    rng = random.Random(2026)
    alphabet = CYRILLIC_LETTERS + CYRILLIC_LETTERS.upper() + " -.,0123456789\n'«»"
    for _ in range(300):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 40)))
        latin = to_latin(text, scheme)
        assert all(not char.isalpha() or char in ASCII_LETTERS for char in latin), (text, latin)
        assert to_latin(latin, scheme) == latin  # идемпотентность


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ЖЧКнын", "JCHKnyn"),
        ("АКШдагы", "AKSHdagy"),
        ("ЮНЕСКОнун", "YUNESKOnun"),
        ("ЦИКтин", "TSIKtin"),
        ("ЧҮЙдүн", "CHUYdun"),
        ("Щи", "Shchi"),
        ("ЩиТ", "ShchiT"),
        ("Чүй", "Chuy"),
        ("Ч.Айтматов", "Ch.Aytmatov"),
        ("ЧҮЙʼДҮН", "CHUYʼDUN"),
        ("ЖЧКʼнын", "JCHKʼnyn"),
        ("ЫСЫК-КӨЛ", "YSYK-KOL"),
        ("Ысык-КӨЛ", "Ysyk-KOL"),
        ("ОБЪЕКТ", "OBYEKT"),
        ("СЕМЬЯ", "SEMYA"),
    ],
)
def test_case_of_multi_letter_replacements_follows_the_neighbours(text, expected):
    assert to_latin(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Я ЖАЗДЫМ", "YA JAZDYM"),
        ("Я жаздым", "Ya jazdym"),
        ("Ч. АЙТМАТОВ АТЫНДАГЫ УЛУТТУК КИТЕПКАНА", "CH. AYTMATOV ATYNDAGY ULUTTUK KITEPKANA"),
        ("Ч. Айтматов", "Ch. Aytmatov"),
        ("АЙТМАТОВ Ч.Т.", "AYTMATOV CH.T."),
        ("ЖЧК «Я»", "JCHK «YA»"),
        ("Я, ЖЧК директору", "Ya, JCHK direktoru"),
        ("Я", "Ya"),
    ],
)
def test_single_capital_letter_follows_its_line(text, expected):
    assert to_latin(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("кыйын жыйын ыйык айыл", "kyiyn jyiyn yiyk aiyl"),
        ("Айыл Банк", "Aiyl Bank"),
        ("Мухаммедкалый", "Mukhammedkalyi"),
        ("Айым Байыш Ыйман", "Aiym Baiysh Yiman"),
        ("КЫЙЫН", "KYIYN"),
        ("той бийик кийим сайын", "toy biyik kiyim saiyn"),
        ("Чүй Айтматов Ысык-Көл", "Chuy Aytmatov Ysyk-Kol"),
        ("кыял кыюу", "kyyal kyyuu"),
    ],
)
def test_short_i_next_to_yery_is_written_as_i(text, expected):
    assert to_latin(text) == expected
    assert to_cyrillic(expected) == text


@pytest.mark.parametrize(
    "text,expected",
    [
        ("подъезд объект", "podyezd obyekt"),
        ("Васильевич Григорьев премьер", "Vasilyevich Grigoryev premyer"),
        ("ПОДЪЕЗД Подъезд", "PODYEZD Podyezd"),
        ("семья Ильяс Ильич", "semya Ilyas Ilich"),
    ],
)
def test_e_after_hard_or_soft_sign_keeps_its_glide(text, expected):
    assert to_latin(text) == expected


def test_passport_scheme_follows_icao_doc_9303():
    assert to_latin("Айгүл Жумагулова", "passport") == "Aigul Zhumagulova"
    assert to_latin("Юлия Кийизбаева", "passport") == "Iuliia Kiiizbaeva"
    assert to_latin("Чүй Айтматов", "passport") == "Chui Aitmatov"
    assert to_latin("ЖУМАГУЛОВА АЙГҮЛ", "passport") == "ZHUMAGULOVA AIGUL"
    assert to_latin("Семёнов объект", "passport") == "Semenov obieekt"
    assert to_cyrillic("Aigul Zhumagulova", "passport") == "Айгүл Жумагулова"
    assert to_cyrillic("Chui Aitmatov", "passport") == "Чүй Айтматов"
    assert to_cyrillic("Iuliia", "passport") == "Юлия"
    assert to_cyrillic("Kyrgyz Respublikasy", "passport") == "Кыргыз Республикасы"


def test_bgn_ascii_scheme_writes_ng():
    assert to_latin("Жеңиш Чокусу", "bgn_ascii") == "Jengish Chokusu"
    assert to_latin("Көк-Жаңгак Чоң-Кемин", "bgn_ascii") == "Kok-Janggak Chong-Kemin"
    assert to_latin("Чыңгыз Айтматов", "bgn_ascii") == "Chynggyz Aytmatov"
    assert to_cyrillic("Kök-Janggak", "bgn_ascii") == "Көк-Жаңгак"
    assert to_cyrillic("Jengish Chokusu", "bgn_ascii") == "Жеңиш Чокусу"
    assert to_cyrillic("Chüy Oblusu", "bgn_ascii", wordlist=False) == "Чүй Облусу"


def test_legacy_bgn_alias_is_the_english_table():
    assert SCHEMES["bgn"].mapping == SCHEMES["english"].mapping
    assert "НЕ BGN/PCGN" in SCHEMES["bgn"].title


@pytest.mark.parametrize("scheme", sorted(EXPECTED))
def test_non_letter_runs_are_preserved_byte_for_byte(scheme):
    text = "Бишкек,\t2026-жыл: 100% — «ок»!\r\nЭкинчи сап…\n\n"
    latin = to_latin(text, scheme)
    for token in (",\t", "2026-", ": 100% — «", "»!\r\n", " ", "…\n\n"):
        assert token in latin
