# -*- coding: utf-8 -*-
import pytest

from kyrgyz_transliteration import (
    Wordlist,
    ascii_key,
    builtin_wordlist,
    builtin_names,
    restore_words,
    to_cyrillic,
    transliterate,
)


@pytest.mark.parametrize(
    "word,key",
    [
        ("dongolok", "dongolok"),
        ("donggolok", "donggolok"),
        ("Kyrgyz", "kyrgyz"),
        ("Chuy", "chuy"),
        ("kitaʺ", "kita"),
        ("Ysyk-Kol", "ysyk-kol"),
    ],
)
def test_ascii_key(word, key):
    assert ascii_key(word) == key


def test_wordlist_indexes_all_typing_variants():
    words = Wordlist(["дөңгөлөк", "жаңылык"])
    for typed in ("dongolok", "donggolok", "DONGOLOK"):
        assert words.lookup(typed) == "дөңгөлөк"
    for typed in ("jangylyk", "jangilik", "zhangylyk", "janylyk"):
        assert words.lookup(typed) == "жаңылык"


def test_ambiguous_key_is_not_used():
    words = Wordlist(["кол", "көл"])
    assert words.lookup("kol") is None
    assert words.ambiguous_keys() == ["kol"]
    assert len(words) == 2


def test_preferred_word_wins_an_ambiguous_key():
    words = Wordlist(["уй"]).add(["үй"], preferred=True)
    assert words.lookup("uy") == "үй"
    assert words.ambiguous_keys() == []
    assert words.preferred() == ["үй"]


def test_preferred_word_wins_regardless_of_order():
    first = Wordlist(["үй"], ).add(["уй"])
    second = Wordlist(["уй"])
    first.add(["үй"], preferred=True)
    second.add(["үй"], preferred=True)
    assert first.lookup("uy") == second.lookup("uy") == "үй"


def test_two_preferred_words_are_ambiguous_again():
    words = Wordlist()
    words.add(["уй", "үй"], preferred=True)
    assert words.lookup("uy") is None


def test_wordlist_container_protocol():
    words = Wordlist(["мектеп"])
    assert "mektep" in words
    assert "dongolok" not in words
    assert words.words() == ["мектеп"]


def test_wordlist_from_file(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("# комментарий\n\nдөңгөлөк\nкөйгөй\n", encoding="utf-8")
    words = Wordlist.from_file(str(path))
    assert len(words) == 2
    assert words.lookup("koygoy") == "көйгөй"


def test_wordlist_file_marks_preferred_with_a_star(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("уй\n*үй\n", encoding="utf-8")
    words = Wordlist.from_file(str(path))
    assert words.lookup("uy") == "үй"
    assert words.words() == ["уй", "үй"]


def test_copy_is_independent_and_keeps_preferences():
    twin = builtin_wordlist().copy().add(["көгүчкөн"])
    assert twin.lookup("koguchkon") == "көгүчкөн"
    assert twin.lookup("uy") == "үй"
    assert "koguchkon" not in builtin_wordlist()


def test_merge_carries_preferred_words_over():
    custom = Wordlist(["уй"]).add(["үй"], preferred=True)
    merged = Wordlist(["мектеп"]).merge(custom)
    assert merged.lookup("uy") == "үй"
    assert merged.lookup("mektep") == "мектеп"


def test_restore_words_keeps_unknown_words_and_punctuation():
    words = Wordlist(["дөңгөлөк"])
    assert restore_words("Dongolok, kompyuter!", words) == "Дөңгөлөк, kompyuter!"


def test_restore_words_keeps_case():
    words = Wordlist(["көчө"])
    assert restore_words("kocho Kocho KOCHO", words) == "көчө Көчө КӨЧӨ"


def test_restore_words_ignores_cyrillic_input():
    assert restore_words("Дөңгөлөк жок", builtin_wordlist()) == "Дөңгөлөк жок"


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("dongolokton", "дөңгөлөктөн"),
        ("dongolokko", "дөңгөлөккө"),
        ("dongolokchu", "дөңгөлөкчү"),
        ("okmottun", "өкмөттүн"),
        ("duinodo", "дүйнөдө"),
        ("mektepte", "мектепте"),
        ("bishkekten", "бишкектен"),
    ],
)
def test_stem_lookup_with_vowel_harmony(typed, expected):
    assert restore_words(typed, builtin_wordlist()) == expected


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("dongologu", "дөңгөлөгү"),
        ("kitebi", "китеби"),
        ("eshigi", "эшиги"),
        ("mektebi", "мектеби"),
    ],
)
def test_stem_lookup_handles_final_voicing(typed, expected):
    # Перед гласным окончанием к -> г, п -> б: без этого окончание не отделить.
    assert restore_words(typed, builtin_wordlist()) == expected


def test_voiced_stem_is_not_a_word_of_its_own():
    words = Wordlist(["китеп"])
    assert words.lookup("kiteb") is None
    assert words.words() == ["китеп"]


def test_stem_lookup_respects_min_stem():
    words = Wordlist(["көчө"], min_stem=10)
    assert restore_words("kochodo", words) == "kochodo"
    assert restore_words("kochodo", Wordlist(["көчө"], min_stem=4)) == "көчөдө"


def test_builtin_wordlist_is_cached_and_useful():
    assert builtin_wordlist() is builtin_wordlist()
    assert len(builtin_wordlist()) > 400
    assert builtin_wordlist().lookup("mumkunchuluk") == "мүмкүнчүлүк"


def test_builtin_names_are_available_and_merged():
    assert builtin_names() is builtin_names()
    assert builtin_names().lookup("Alibek") == "Алибек"
    assert builtin_wordlist().lookup("Nurdoolot") == "Нурдөөлөт"
    assert builtin_names().lookup_trigram("Nurdoolod") == "Нурдөөлөт"


def test_trigram_name_matching_requires_name_like_capitalization():
    assert to_cyrillic("Nurdoolod") == "Нурдөөлөт"
    assert to_cyrillic("nurdoolod") != "Нурдөөлөт"


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("dongolok", "дөңгөлөк"),
        ("jonokoy", "жөнөкөй"),
        ("omur", "өмүр"),
        ("kenesh", "кеңеш"),
        ("kengesh", "кеңеш"),
        ("tushunuk", "түшүнүк"),
        ("kirgiz", "кыргыз"),
        ("kyrgyz", "кыргыз"),
        ("jonundo", "жөнүндө"),
        ("uy", "үй"),
    ],
)
def test_to_cyrillic_restores_special_letters_by_default(typed, expected):
    assert to_cyrillic(typed) == expected


def test_wordlist_can_be_switched_off():
    assert to_cyrillic("dongolok", wordlist=False) == "донголок"
    assert to_cyrillic("uy", wordlist=False) == "уй"


def test_empty_wordlist_is_not_mistaken_for_false():
    # Пустой Wordlist ложен как контейнер, но это всё-таки словарь.
    assert to_cyrillic("dongolok", wordlist=Wordlist()) == "донголок"


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("Ysyk-Kol", "Ысык-Көл"),
        ("YSYK-KOL", "ЫСЫК-КӨЛ"),
        ("Ysyk-Koldon", "Ысык-Көлдөн"),
        ("uy-bulo", "үй-бүлө"),
        ("Jalal-Abad", "Жалал-Абад"),
        ("ata-ene", "ата-эне"),
    ],
)
def test_compound_words_are_restored_whole(typed, expected):
    assert to_cyrillic(typed) == expected


def test_wordlist_does_not_break_correct_latin():
    assert to_cyrillic("donggolok jangylyk") == "дөңгөлөк жаңылык"
    assert to_cyrillic("Kyrgyz Respublikasy") == "Кыргыз Республикасы"


def test_transliterate_passes_wordlist_only_to_cyrillic():
    assert transliterate("dongolok") == "дөңгөлөк"
    assert transliterate("дөңгөлөк") == "dongolok"


def test_wordlist_can_be_extended():
    words = builtin_wordlist().copy().add(["көгүчкөн"])
    assert restore_words("koguchkondon", words) == "көгүчкөндөн"
    assert "koguchkon" not in builtin_wordlist()
