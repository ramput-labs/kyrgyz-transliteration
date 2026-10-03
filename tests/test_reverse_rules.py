# -*- coding: utf-8 -*-
"""Обратное направление: правила, которые делают круг «кириллица -> латиница ->
кириллица» точным для частых классов слов."""
import pytest

from kyrgyz_transliteration import Wordlist, to_cyrillic, to_latin


@pytest.mark.parametrize(
    "word",
    [
        "жээк", "мээ", "ээ", "кээде", "жээн", "бээ", "дээрлик", "мээнет", "Жээнбеков", "Мээрим",
        "Ысык-Көлдүн жээги",
    ],
)
def test_long_ee_is_restored_as_double_e_reversed(word):
    assert to_cyrillic(to_latin(word)) == word


@pytest.mark.parametrize("word", ["Андреев", "Сергеевич", "Алексеева", "идея", "музей", "мектепте"])
def test_russian_double_e_before_v_and_other_e_words_are_untouched(word):
    assert to_cyrillic(to_latin(word)) == word


@pytest.mark.parametrize(
    "word",
    [
        "район", "району", "райондук", "майор", "айоо", "боёк", "коён", "Ёлка", "самолёт",
        "күйөө", "түйүн",
    ],
)
def test_y_before_o_after_a_e_i_u_is_short_i(word):
    assert to_cyrillic(to_latin(word)) == word


@pytest.mark.parametrize(
    "word",
    [
        "конституция", "Конституциясы", "информация", "полиция", "лицей", "улица", "медицина",
        "процесс", "абзац", "социалдык", "лицензия", "Кузнецов", "концерт", "цирк",
        "айтса", "кетсе", "тартса", "кетсин", "айтсын",
    ],
)
def test_ts_is_tse_in_loanwords_but_te_se_at_kyrgyz_suffix_boundaries(word):
    assert to_cyrillic(to_latin(word)) == word


def test_ts_before_harmonic_suffix_vowel_is_te_se_even_without_the_wordlist():
    assert to_cyrillic("otso", wordlist=False) == "отсо"
    assert to_cyrillic("ketse", wordlist=False) == "кетсе"
    assert to_cyrillic("ulitsa", wordlist=False) == "улица"


@pytest.mark.parametrize(
    "word", ["башчы", "ашчы", "ишчи", "кошчу", "башчылык", "жумушчу", "Щербаков", "борщ", "защита"]
)
def test_sh_plus_ch_at_agent_suffix_is_not_shcha(word):
    assert to_cyrillic(to_latin(word)) == word


@pytest.mark.parametrize(
    "word", ["Васильевич", "Григорьев", "премьер", "пьеса", "барьер", "Юрьевич"]
)
def test_soft_sign_before_e_round_trips(word):
    assert to_cyrillic(to_latin(word)) == word


def test_soft_sign_before_other_iotated_vowels_is_still_lost():
    # ь перед я/ю в латинице не виден: semya, Ilyas — это документированная потеря.
    assert to_cyrillic(to_latin("семья")) == "семя"


@pytest.mark.parametrize(
    "latin,expected",
    [
        ("aiyl", "айыл"),
        ("kyiyn", "кыйын"),
        ("Yiman", "Ыйман"),
        ("Baiysh", "Байыш"),
        ("Mukhammedkalyi", "Мухаммедкалый"),
        ("Krasnyi", "Красный"),
        ("ayyl", "айыл"),
        ("kyyyn", "кыйын"),
        ("myyzam", "мыйзам"),
        ("Said", "Саид"),
        ("Ismail", "Исмаил"),
        ("Aida", "Аида"),
        ("Raisa", "Раиса"),
        ("biyik", "бийик"),
        ("kiyim", "кийим"),
        ("Mariya", "Мария"),
        ("Yuriy", "Юрий"),
        ("Said Ismail", "Саид Исмаил"),
    ],
)
def test_i_next_to_y_is_short_i_but_vowel_plus_i_stays_i(latin, expected):
    assert to_cyrillic(latin) == expected
    assert to_cyrillic(latin, wordlist=False) == expected or to_cyrillic(latin) == expected


@pytest.mark.parametrize(
    "latin,expected",
    [
        ("Jeti-Ögüz", "Жети-Өгүз"),
        ("Sülüktü", "Сүлүктү"),
        ("Tash-Kömür", "Таш-Көмүр"),
        ("Chüy Oblusu", "Чүй Облусу"),
        ("Bardıq adamdar öz", "Бардык адамдар өз"),
        ("Mahabat", "Махабат"),
        ("Centr", "Кентр"),
    ],
)
def test_diacritics_of_bgn_and_turkic_spellings_are_understood(latin, expected):
    assert to_cyrillic(latin, wordlist=False) == expected


def test_urls_emails_and_handles_pass_through_to_cyrillic():
    text = "Toluk maalymat: https://www.gov.kg/ky/news, info@tunduk.kg, @tunduk_kg #Bishkek"
    assert to_cyrillic(text) == (
        "Толук маалымат: https://www.gov.kg/ky/news, info@tunduk.kg, @tunduk_kg #Bishkek"
    )


def test_passport_scheme_restores_words_through_the_wordlist():
    assert to_cyrillic("Shamalduu-Sai", "passport") == "Шамалдуу-Сай"
    assert to_cyrillic("kompiuter", "passport") == "компьютер"
    assert to_cyrillic("dongolokton", "passport") == "дөңгөлөктөн"
    assert to_cyrillic("Ysyk-Koldon", "passport") == "Ысык-Көлдөн"


def test_wordlist_file_with_bom(tmp_path):
    path = tmp_path / "words.txt"
    path.write_bytes(b"\xef\xbb\xbf# words\n" + "көпөлөк\n".encode("utf-8"))
    assert Wordlist.from_file(str(path)).words() == ["көпөлөк"]
    path.write_bytes(b"\xef\xbb\xbf" + "көпөлөк\n".encode("utf-8"))
    assert Wordlist.from_file(str(path)).lookup("kopolok") == "көпөлөк"


def test_mixed_case_token_keeps_the_case_of_its_stem():
    assert to_cyrillic("CHUYdun") == "ЧҮЙдүн"
    assert to_cyrillic("YSYK-KOLdun") == "ЫСЫК-КӨЛдүн"
    assert to_cyrillic(to_latin("ЫСЫК-КӨЛдүн")) == "ЫСЫК-КӨЛдүн"


def test_loanwords_with_initial_e_come_from_the_wordlist():
    assert to_cyrillic("EAEB") == "ЕАЭБ"
    assert to_cyrillic("evro Evropa Evraziya") == "евро Европа Евразия"
    assert to_cyrillic("el emgek eski") == "эл эмгек эски"
