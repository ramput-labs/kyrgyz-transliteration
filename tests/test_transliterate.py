# -*- coding: utf-8 -*-
import pytest

from kyrgyz_transliteration import (
    SCHEMES,
    builtin_wordlist,
    detect_script,
    slugify,
    to_cyrillic,
    to_latin,
    transliterate,
)

WORDS = [
    "кыргыз",
    "республика",
    "ысык-көл",
    "жалал-абад",
    "манас",
    "бишкек",
    "таң",
    "күн",
    "өмүр",
    "сүйүү",
    "жаңылык",
    "чүкө",
    "шамал",
    "ыңгайлуу",
    "мүмкүнчүлүк",
]


def test_library_speaks_english_only():
    assert sorted(SCHEMES) == ["bgn", "bgn_ascii", "english", "english_ascii", "passport"]
    for scheme in SCHEMES.values():
        latin = "".join(scheme.mapping.values())
        assert latin.isascii()
    # В схеме по умолчанию — только буквы английского алфавита.
    assert "".join(SCHEMES["english"].mapping.values()).isascii()


@pytest.mark.parametrize("scheme", list(SCHEMES), ids=list(SCHEMES))
def test_every_scheme_emits_only_english_ascii(scheme):
    output = to_latin(
        "Көңүлдүү мүмкүнчүлүктөрдүн жаңылыктары: 2026!",
        scheme,
    )
    assert all(
        not char.isalpha()
        or char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        for char in output
    )


@pytest.mark.parametrize("word", WORDS)
def test_english_round_trip_uses_the_wordlist(word):
    assert to_cyrillic(to_latin(word)) == word


@pytest.mark.parametrize("scheme", list(SCHEMES), ids=list(SCHEMES))
def test_non_letters_pass_through(scheme):
    text = "Бишкек, 2026-жыл: 100% — «ок»!"
    result = to_latin(text, scheme)
    for token in ("2026", "100%", "«", "»", "!", ":", ","):
        assert token in result


def test_english_defaults():
    assert to_latin("Кыргыз Республикасы") == "Kyrgyz Respublikasy"
    assert to_latin("жаңы жыл") == "jany jyl"
    assert to_latin("Чүй облусу") == "Chuy oblusu"
    assert to_latin("Ысык-Көл") == "Ysyk-Kol"
    assert to_latin("өмүр") == "omur"
    assert to_latin("Жалал-Абад") == "Jalal-Abad"


def test_english_latin_has_no_letters_outside_a_to_z():
    latin = to_latin("Өкмөттүн жаңы дөңгөлөгү — Ысык-Көлдөн")
    letters = [char for char in latin if char.isalpha()]
    assert all(char.isascii() for char in letters), latin
    assert "—" in latin  # не-буквы проходят насквозь


def test_bgn_examples():
    assert to_latin("Кыргыз Республикасы", "bgn") == "Kyrgyz Respublikasy"
    assert to_latin("Ысык-Көл", "bgn") == "Ysyk-Kol"
    assert to_latin("Ёлка", "bgn") == "Yolka"
    assert to_latin("Ош шаары", "bgn") == "Osh shaary"
    assert to_latin("жаңы", "bgn") == "jany"


def test_english_ascii_uses_plain_english_vowels():
    text = "Өмүр бою Кыргызстанды сагынам"
    latin = to_latin(text, "english_ascii")
    assert latin == "Omur boyu Kyrgyzstandy sagynam"


def test_english_example_uses_natural_ascii_spelling():
    text = "Өмүр бою Кыргызстанды сагынам"
    latin = to_latin(text)
    assert latin == "Omur boyu Kyrgyzstandy sagynam"
    assert to_cyrillic(latin) == text


@pytest.mark.parametrize(
    "latin,cyrillic",
    [
        ("Alibek", "Алибек"),
        ("Nurdoolot Rysbaev", "Нурдөөлөт Рысбаев"),
        ("Janyl", "Жаңыл"),
        ("Chyngyz", "Чыңгыз"),
        ("Meerim", "Мээрим"),
    ],
)
def test_name_corpus_restores_names(latin, cyrillic):
    assert to_cyrillic(latin) == cyrillic


def test_case_is_preserved():
    assert to_latin("Жол") == "Jol"
    assert to_latin("ЖОЛ") == "JOL"
    assert to_latin("Ёлка") == "Yolka"
    assert to_latin("ЁЛКА") == "YOLKA"
    assert to_latin("КЫРГЫЗ ЭЛИ") == "KYRGYZ ELI"
    assert to_cyrillic("KYRGYZ") == "КЫРГЫЗ"
    assert to_cyrillic("Kyrgyz") == "Кыргыз"


def test_single_letter_word_is_capitalized_not_shouted():
    assert to_latin("Я жаздым") == "Ya jazdym"


def test_soft_and_hard_signs_are_dropped_in_english():
    assert to_latin("альбом") == "albom"
    assert to_latin("семья") == "semya"
    # ...кроме позиции перед «е», где они обозначают йотацию: podyezd, а не podezd.
    assert to_latin("подъезд") == "podyezd"


def test_digraphs_win_over_single_letters():
    assert to_cyrillic("shchi") == "щи"
    assert to_cyrillic("yurt") == "юрт"
    assert to_cyrillic("khan") == "хан"


def test_latin_extras_are_understood():
    assert to_cyrillic("qwerty") == "кверты"


def test_empty_input():
    assert to_latin("") == ""
    assert to_cyrillic("") == ""
    assert slugify("") == ""


def test_detect_script():
    assert detect_script("Бишкек") == "cyrillic"
    assert detect_script("Bishkek") == "latin"
    assert detect_script("Бишкек Bishkek") == "mixed"
    assert detect_script("2026!") == "unknown"


def test_transliterate_auto_direction():
    assert transliterate("Бишкек") == "Bishkek"
    assert transliterate("Bishkek") == "Бишкек"
    assert transliterate("2026") == "2026"
    assert transliterate("Бишкек", direction="cyrillic") == "Бишкек"
    with pytest.raises(ValueError):
        transliterate("Бишкек", direction="sideways")


def test_slugify():
    assert slugify("Ысык-Көл облусу") == "ysyk-kol-oblusu"
    assert slugify("Жалал-Абад", separator="_") == "jalal_abad"
    assert slugify("  Манас   атанын  ") == "manas-atanyn"
    assert slugify("Бишкек 2026") == "bishkek-2026"
    assert slugify("Чүй", separator="") == "chuy"
    assert slugify("Ысык-Көл", scheme="bgn") == "ysyk-kol"


def test_multiline_text_keeps_line_breaks():
    text = "Кыргыз\nРеспубликасы\n"
    assert to_latin(text) == "Kyrgyz\nRespublikasy\n"


@pytest.mark.parametrize(
    "latin,cyrillic",
    [
        ("Ysyk-Kol", "Ысык-Көл"),
        ("oy-toy", "ой-той"),
        ("ayyl", "айыл"),
        ("myyzam", "мыйзам"),
        ("kyyyn", "кыйын"),
        ("biyik", "бийик"),
        ("kyyuu", "кыюу"),
        ("sayakat", "саякат"),
        ("Kyrgyz Respublikasy", "Кыргыз Республикасы"),
    ],
)
def test_reverse_resolves_y_between_short_i_and_yery(latin, cyrillic):
    assert to_cyrillic(latin, "bgn") == cyrillic


@pytest.mark.parametrize("scheme", ["english", "bgn"])
def test_reverse_ts_after_vowel_is_te_plus_se(scheme):
    assert to_cyrillic(to_latin("айтса кетсе", scheme), scheme) == "айтса кетсе"
    assert to_cyrillic(to_latin("концерт цирк", scheme), scheme) == "концерт цирк"


@pytest.mark.parametrize("scheme", ["english", "bgn"])
def test_word_initial_e_becomes_reversed_e(scheme):
    assert to_cyrillic(to_latin("эл эмгек эски", scheme), scheme) == "эл эмгек эски"
    assert to_cyrillic(to_latin("мектеп", scheme), scheme) == "мектеп"


SENTENCE = "Кыргыз Республикасынын Жогорку Кеңеши"


def test_sentence_round_trip_in_english_needs_the_wordlist():
    assert to_cyrillic(to_latin(SENTENCE)) == SENTENCE


WORDS_CORPUS = (
    "айыл кыйын айтса кетсе концерт цирк ай ой үй кыз ырыс ысык-көл тайыз жайыл "
    "сайын аяк оюн саякат бийик мыйзам ыйлады тийет кыюу бай той сарай май жыл "
    "жылдыз кыргыз республика бишкек нарын талас баткен жалал-абад чүй таң күн "
    "өмүр сүйүү жаңылык чүкө шамал ыңгайлуу мүмкүнчүлүк мектеп китеп эже байке "
    "сиңди кыздар эмгек өлкө шаар манас семетей сейтек жийде тоо суу асман эчки "
    "эрте эми экен жер эл тил сөз үн ый айт кел жакшы чоң кичине узун кыска эски"
).split()


def test_corpus_round_trip_in_english_ascii_with_dictionary():
    broken = [
        word
        for word in WORDS_CORPUS
        if to_cyrillic(to_latin(word, "bgn"), "bgn") != word
    ]
    assert broken == []


def test_corpus_round_trip_in_english_with_the_wordlist():
    broken = [word for word in WORDS_CORPUS if to_cyrillic(to_latin(word)) != word]
    assert broken == []


def test_builtin_wordlist_round_trips_apart_from_true_homographs():
    words = builtin_wordlist().words()
    broken = [word for word in words if to_cyrillic(to_latin(word)) != word]
    # Пары вроде «кол»/«көл» пишутся по-английски одинаково: одно из двух
    # слов неизбежно теряется, остальные 400+ восстанавливаются точно.
    assert len(broken) <= 5
    assert len(words) - len(broken) > 400
