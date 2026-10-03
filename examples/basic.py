"""Practical Kyrgyz transliteration examples.

Run from the repository root:

    python -m examples

All built-in schemes write natural English ASCII spellings. The ``bgn`` name
is retained only for compatibility.
"""

from __future__ import annotations

from kyrgyz_transliteration import (
    detect_script,
    slugify,
    to_cyrillic,
    to_latin,
    transliterate,
)


KYRGYZ_TO_ENGLISH = (
    "дөңгөлөк",
    "өкмөттүн жаңы дөңгөлөгү",
    "үй-бүлө",
    "мүмкүнчүлүк",
    "Ысык-Көл облусундагы тоолор",
    "Кыргыз Республикасынын билим берүү жана илим министрлиги",
)

ENGLISH_TO_KYRGYZ = (
    "dongolok",
    "okmottun jangy dongologu",
    "uy-bulo",
    "mumkunchuluk",
    "Ysyk-Kol oblusundagy toolor",
    "Kyrgyz Respublikasynyn bilim beruu jana ilim ministrligi",
)


def show_kyrgyz_to_english() -> None:
    """Convert natural Kyrgyz text to ASCII English transliteration."""
    print("Kyrgyz -> English (default ASCII scheme)")
    for text in KYRGYZ_TO_ENGLISH:
        print(f"  {text} -> {to_latin(text)}")


def show_english_to_kyrgyz() -> None:
    """Restore Kyrgyz spelling from common ASCII transliterations."""
    print("\nEnglish -> Kyrgyz (dictionary-assisted restoration)")
    for text in ENGLISH_TO_KYRGYZ:
        print(f"  {text} -> {to_cyrillic(text)}")


def show_english_round_trip() -> None:
    """Show the natural English transliteration and dictionary restoration."""
    text = "Өмүр бою Кыргызстанды сагынам"
    latin = to_latin(text)
    restored = to_cyrillic(latin)
    print("\nEnglish transliteration round trip")
    print(f"  {text} -> {latin} -> {restored}")


def show_convenience_helpers() -> None:
    """Demonstrate automatic direction, script detection, and URL slugs."""
    print("\nConvenience helpers")
    print(f"  detect_script('Ысык-Көл') -> {detect_script('Ысык-Көл')}")
    print(f"  detect_script('Ysyk-Kol') -> {detect_script('Ysyk-Kol')}")
    print(f"  transliterate('Бишкек') -> {transliterate('Бишкек')}")
    print(f"  transliterate('Bishkek') -> {transliterate('Bishkek')}")
    print(
        "  slugify('Ысык-Көл облусу', separator='_')"
        f" -> {slugify('Ысык-Көл облусу', separator='_')}"
    )


def show_lossy_edge_case() -> None:
    """Make the default scheme's deliberate ambiguity visible."""
    text = "Ысык-Көлдүн көлү, Чүйдүн колу"  # көл (lake) and кол (hand) are both "kol"
    latin = to_latin(text)
    restored = to_cyrillic(latin)
    print("\nImportant: English ASCII transliteration is not always reversible")
    print(f"  original:  {text}")
    print(f"  latin:     {latin}")
    print(f"  restored:  {restored}")
    print("  True homographs (кол/көл, он/оң) cannot be told apart: the dictionary picks")
    print("  the more frequent reading. Everything else in the built-in lists round-trips.")


def main() -> None:
    """Run all examples."""
    show_kyrgyz_to_english()
    show_english_to_kyrgyz()
    show_english_round_trip()
    show_convenience_helpers()
    show_lossy_edge_case()


if __name__ == "__main__":
    main()
