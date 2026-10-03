"""Complex, real-world usage examples for Kyrgyz transliteration.

Run from the repository root:

    python -m examples.complex_cases

These examples focus on cases where a simple letter-for-letter demonstration is
not enough: suffixes, compounds, punctuation, case preservation, ambiguous
ASCII spellings, custom vocabulary, and extended ASCII output.
"""

from __future__ import annotations

from kyrgyz_transliteration import (
    ascii_key,
    builtin_wordlist,
    detect_script,
    slugify,
    to_cyrillic,
    to_latin,
    transliterate,
)


def show_inflected_words() -> None:
    """Restore stems and Kyrgyz suffixes from ASCII transliteration."""
    examples = (
        ("dongolokton", "дөңгөлөктөн"),
        ("dongologu", "дөңгөлөгү"),
        ("okmottun", "өкмөттүн"),
        ("koygoydon", "көйгөйдөн"),
        ("dongoloktor", "дөңгөлөктөр"),
    )
    print("Inflected words")
    for latin, expected in examples:
        result = to_cyrillic(latin)
        assert result == expected, (latin, result, expected)
        print(f"  {latin:14} -> {result}")


def show_compound_phrases() -> None:
    """Keep compounds together when their meaning depends on the whole word."""
    examples = (
        "Ысык-Көлдүн жээгиндеги чакан айыл",
        "үй-бүлөлүк дарыгерге кайрылдым",
        "Кыргызстандагы айыл чарба ишканалары",
        "көз карандысыздыкты коргоо",
    )
    print("\nCompound phrases")
    for kyrgyz in examples:
        latin = to_latin(kyrgyz)
        restored = to_cyrillic(latin)
        print(f"  {kyrgyz}")
        print(f"    -> {latin}")
        print(f"    -> {restored}")


def show_case_and_punctuation() -> None:
    """Preserve capitalization and pass punctuation, numbers, and symbols through."""
    text = "БИШКЕК — Кыргызстандын борбору, 2026-жыл."
    latin = to_latin(text)
    restored = to_cyrillic(latin)
    print("\nCase, punctuation, and numbers")
    print(f"  {text}")
    print(f"  -> {latin}")
    print(f"  -> {restored}")


def show_ambiguous_spellings() -> None:
    """Show the difference between dictionary restoration and rules only."""
    print("\nAmbiguous ASCII spellings")
    for latin in ("dongolok", "uy-bulo", "mumkunchuluk"):
        with_words = to_cyrillic(latin)
        rules_only = to_cyrillic(latin, wordlist=False)
        print(f"  {latin:16} -> {with_words:16} (dictionary)")
        print(f"  {'':16} -> {rules_only:16} (rules only)")


def show_custom_wordlist() -> None:
    """Add domain vocabulary without mutating the cached built-in dictionary."""
    custom = builtin_wordlist().copy().add(
        [
            "маалыматташтыруу",
            "санариптештирүү",
            "көпөлөктөн",
        ]
    )
    latin = "maalymattashtyruu jana sanaripteshtiruu"
    restored = to_cyrillic(latin, wordlist=custom)
    print("\nCustom vocabulary")
    print(f"  {latin}")
    print(f"  -> {restored}")
    print(f"  ascii_key('donggolok') -> {ascii_key('donggolok')}")
    assert "maalymattashtyruu" in custom
    assert "maalymattashtyruu" not in builtin_wordlist()


def show_exact_ascii_round_trip() -> None:
    """Use ASCII output with the familiar ``o`` and ``u`` spellings."""
    text = "Өзгөчө мүмкүнчүлүктөрү бар үй-бүлөлөр"
    latin = to_latin(text, scheme="english_ascii")
    restored = to_cyrillic(latin, scheme="english_ascii")
    print("\nExtended English ASCII")
    print(f"  {text}")
    print(f"  -> {latin}")
    print(f"  -> {restored}")
    assert latin.isascii()


def show_mixed_workflow() -> None:
    """Combine script detection, automatic direction, and URL slug generation."""
    inputs = (
        "Кыргыз Республикасынын Улуттук илимдер академиясы",
        "Kyrgyz Respublikasynyn Uluttuk ilimder akademiyasy",
    )
    print("\nMixed workflow")
    for text in inputs:
        result = transliterate(text)
        print(f"  [{detect_script(text):8}] {text} -> {result}")
    print(
        "  slug ->",
        slugify("Кыргыз Республикасынын Улуттук илимдер академиясы"),
    )


def main() -> None:
    """Run all complex examples."""
    show_inflected_words()
    show_compound_phrases()
    show_case_and_punctuation()
    show_ambiguous_spellings()
    show_custom_wordlist()
    show_exact_ascii_round_trip()
    show_mixed_workflow()


if __name__ == "__main__":
    main()
