# Examples

These examples use real Kyrgyz words and phrases, including dictionary-assisted
restoration of `ө`, `ү`, and `ң`:

- `дөңгөлөк` → `dongolok` → `дөңгөлөк`
- `өкмөттүн жаңы дөңгөлөгү` → `okmottun jangy dongologu`
- `үй-бүлө` → `uy-bulo` → `үй-бүлө`
- `мүмкүнчүлүк` → `mumkunchuluk` → `мүмкүнчүлүк`
- `Ысык-Көл облусундагы тоолор` → `Ysyk-Kol oblusundagy toolor`

Run the complete demo from the repository root:

```bash
python -m examples
```

The main implementation is in [`basic.py`](./basic.py). It demonstrates:

- Kyrgyz Cyrillic to ASCII English transliteration with `to_latin`;
- English transliteration back to Kyrgyz with `to_cyrillic`;
- natural English output such as `Өмүр бою...` → `Omur boyu...`;
- automatic direction detection with `transliterate`;
- script detection and URL-safe slugs;
- a genuinely lossy case: the homographs `көл`/`кол` are both `kol`.

For deeper cases, run [`complex_cases.py`](./complex_cases.py):

```bash
python -m examples.complex_cases
```

It covers inflected words such as `dongolokton`, compound phrases, punctuation
and capitalization, ambiguous spellings with and without the dictionary,
custom domain vocabulary, the `english_ascii` scheme (`ж` → `zh`), and mixed
automatic direction workflows.

For especially dense Kyrgyz text, run
[`very_complex_cases.py`](./very_complex_cases.py):

```bash
python -m examples.very_complex_cases
```

It uses words and sentences with repeated `ң`, `ү`, and `ө`, shows the legacy
`bgn` alias next to the default scheme, and demonstrates adding an inflected
form to a copied custom wordlist.

For the supplied personal sentence cases, run
[`custom_cases.py`](./custom_cases.py):

```bash
python -m examples.custom_cases
```

It demonstrates names, punctuation, questions, and application-specific
vocabulary added to a copied `Wordlist`.

Schemes: the default `english` scheme is designed for keyboards, URLs,
filenames, and messengers, so `ө`, `ү`, `ң` share ASCII spellings with `о`,
`у`, `н` and are restored from the dictionary. `english_ascii` differs only by
`ж` → `zh`. `passport` reproduces the ICAO Doc 9303 table used in Kyrgyz
passports (`й` → `i`, `ю` → `iu`, `я` → `ia`), and `bgn_ascii` is BGN/PCGN 1979
in plain `a-z` (`ң` → `ng`). The legacy `bgn` name is an alias of `english`.
Even with the default dictionary, uncommon words and unfamiliar inflections may
need a custom [`Wordlist`](../README.md#свой-список-слов).

The same operations are available from the installed CLI:

```bash
kyrgyz-transliteration "дөңгөлөк"
kyrgyz-transliteration -s passport "Айгүл Жумагулова"
kyrgyz-transliteration -d cyrillic "okmottun jangy dongologu"
kyrgyz-transliteration -i text.txt -o text-latin.txt
```
