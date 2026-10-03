# -*- coding: utf-8 -*-
import io
import sys

from kyrgyz_transliteration.cli import main


def run(argv, stdin=None, monkeypatch=None, capsys=None):
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    code = main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def test_text_argument(capsys, monkeypatch):
    code, out, _ = run(["Кыргыз Республикасы"], capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0
    assert out == "Kyrgyz Respublikasy\n"


def test_scheme_and_direction(capsys, monkeypatch):
    code, out, _ = run(["-s", "bgn", "Ысык-Көл"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "Ysyk-Kol\n")
    code, out, _ = run(
        ["-d", "cyrillic", "Kyrgyz"], capsys=capsys, monkeypatch=monkeypatch
    )
    assert (code, out) == (0, "Кыргыз\n")


def test_stdin(capsys, monkeypatch):
    code, out, _ = run([], stdin="Бишкек\n", capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "Bishkek\n")


def test_slug_and_detect(capsys, monkeypatch):
    code, out, _ = run(["--slug", "Ысык-Көл"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "ysyk-kol\n")
    code, out, _ = run(["--detect", "Бишкек"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "cyrillic\n")


def test_list_and_table(capsys, monkeypatch):
    code, out, _ = run(["--list"], capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0
    assert "english" in out and "bgn" in out
    assert "turkic" not in out and "iso9" not in out
    code, out, _ = run(["--table", "bgn"], capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0
    assert "ж j" in out


def test_unknown_scheme_exits_with_error(capsys, monkeypatch):
    code, _, err = run(["-s", "nope", "тест"], capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2
    assert "nope" in err


def test_empty_stdin(capsys, monkeypatch):
    code, _, err = run([], stdin="", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2
    assert "usage" in err.lower()


def test_wordlist_is_on_by_default(capsys, monkeypatch):
    code, out, _ = run(["dongolok kocho jok"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "дөңгөлөк көчө жок\n")


def test_no_words_falls_back_to_scheme_rules(capsys, monkeypatch):
    code, out, _ = run(
        ["--no-words", "dongolok kocho jok"], capsys=capsys, monkeypatch=monkeypatch
    )
    assert (code, out) == (0, "донголок кочо жок\n")


def test_wordlist_file(capsys, monkeypatch, tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("# свои слова\nкөгүчкөн\n", encoding="utf-8")
    code, out, _ = run(
        ["--wordlist", str(path), "koguchkondon dongolok"],
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert (code, out) == (0, "көгүчкөндөн дөңгөлөк\n")


def test_wordlist_file_without_the_builtin_one(capsys, monkeypatch, tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("көгүчкөн\n", encoding="utf-8")
    code, out, _ = run(
        ["--no-words", "--wordlist", str(path), "koguchkon dongolok"],
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert (code, out) == (0, "көгүчкөн донголок\n")


def test_missing_wordlist_file_exits_with_error(capsys, monkeypatch):
    code, _, err = run(
        ["--wordlist", "/nope/words.txt", "dongolok"], capsys=capsys, monkeypatch=monkeypatch
    )
    assert code == 2
    assert "words.txt" in err


# --- кодировки, файлы, потоки -------------------------------------------------


def _cp1251_stdout(monkeypatch):
    """Стандартный вывод, как у канала на русской Windows: cp1251."""
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1251", newline="", write_through=True)
    monkeypatch.setattr(sys, "stdout", stream)
    return raw, stream


def test_help_works_on_a_cp1251_pipe(monkeypatch):
    raw, stream = _cp1251_stdout(monkeypatch)
    try:
        main(["--help"])
    except SystemExit as exit_:
        assert exit_.code == 0
    stream.flush()
    assert "kyrgyz-transliteration" in raw.getvalue().decode("utf-8")


def test_cyrillic_output_on_a_cp1251_pipe_is_utf8(monkeypatch):
    raw, stream = _cp1251_stdout(monkeypatch)
    assert main(["-d", "cyrillic", "dongolok"]) == 0
    stream.flush()
    assert raw.getvalue() == "дөңгөлөк\n".encode("utf-8")


def test_utf8_stdin_on_a_cp1251_pipe_is_read_as_utf8(monkeypatch, capsys):
    stdin = io.TextIOWrapper(io.BytesIO("Ысык-Көл дөңгөлөк\n".encode("utf-8")), encoding="cp1251")
    monkeypatch.setattr(sys, "stdin", stdin)
    assert main([]) == 0
    assert capsys.readouterr().out == "Ysyk-Kol dongolok\n"


def test_bom_at_the_start_of_stdin_is_dropped(capsys, monkeypatch):
    code, out, _ = run([], stdin="\ufeffБишкек\n", capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "Bishkek\n")


def test_trailing_blank_lines_are_preserved(capsys, monkeypatch):
    code, out, _ = run([], stdin="Бишкек\n\n\n", capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "Bishkek\n\n\n")
    code, out, _ = run([], stdin="Бишкек", capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "Bishkek")


def test_input_and_output_files(tmp_path, capsys, monkeypatch):
    src = tmp_path / "in.txt"
    dst = tmp_path / "out.txt"
    src.write_bytes(b"\xef\xbb\xbf" + "Кыргыз Республикасы\r\nдөңгөлөк\r\n".encode("utf-8"))
    code, out, err = run(["-i", str(src), "-o", str(dst)], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out, err) == (0, "", "")
    assert dst.read_bytes() == b"Kyrgyz Respublikasy\r\ndongolok\r\n"


def test_input_encoding_option(tmp_path, capsys, monkeypatch):
    src = tmp_path / "in.txt"
    src.write_bytes("Бишкек шаары\n".encode("cp1251"))
    code, out, _ = run(["-i", str(src), "--encoding", "cp1251"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "Bishkek shaary\n")
    code, _, err = run(["-i", str(src)], capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2 and "--encoding" in err
    code, _, err = run(["--encoding", "nope", "Бишкек"], capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2 and "nope" in err


def test_slug_honours_the_scheme(capsys, monkeypatch):
    code, out, _ = run(["--slug", "-s", "english_ascii", "Жалал-Абад"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "zhalal-abad\n")


def test_passport_scheme_from_the_cli(capsys, monkeypatch):
    code, out, _ = run(["-s", "passport", "Айгүл Жумагулова"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "Aigul Zhumagulova\n")


def test_dirty_cyrillic_is_normalized_unless_disabled(capsys, monkeypatch):
    code, out, _ = run(["дѳңгѳлѳк Тaлаc"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "dongolok Talas\n")
    code, out, _ = run(["--no-normalize", "дѳңгѳлѳк"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "dѳngѳlѳk\n")


def test_broken_pipe_is_not_an_error(capsys, monkeypatch):
    def broken_write(_):
        raise BrokenPipeError()

    monkeypatch.setattr(sys.stdout, "write", broken_write)
    assert main(["Бишкек"]) == 0
    assert capsys.readouterr().err == ""


def test_dash_means_stdin(capsys, monkeypatch):
    code, out, _ = run(["-"], stdin="Бишкек\n", capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "Bishkek\n")


def test_explicit_direction_streams_line_by_line(capsys, monkeypatch):
    code, out, _ = run(["-d", "latin"], stdin="Бишкек\nОш\n", capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "Bishkek\nOsh\n")


def test_version(capsys, monkeypatch):
    from kyrgyz_transliteration import __version__

    try:
        main(["--version"])
    except SystemExit as exit_:
        assert exit_.code == 0
    assert capsys.readouterr().out.strip() == __version__
