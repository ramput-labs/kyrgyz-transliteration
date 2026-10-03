"""Консольная утилита ``kyrgyz-transliteration``."""

from __future__ import annotations

import argparse
import codecs
import contextlib
import os
import sys
from typing import IO, Iterator, List, Optional, Tuple

from . import (
    DEFAULT_SCHEME,
    Wordlist,
    __version__,
    alphabet_table,
    builtin_wordlist,
    detect_script,
    get_scheme,
    list_schemes,
    slugify,
    transliterate,
)
from .schemes import UnknownSchemeError

__all__ = ["build_parser", "main"]

#: Кодировка ввода по умолчанию; BOM (Блокнот, Excel) распознаётся и отбрасывается.
DEFAULT_ENCODING = "utf-8"
#: Кодировка вывода. Кыргызской кириллице нет места ни в одной однобайтовой
#: кодовой странице Windows (в cp1251 нет ө, ү, ң), поэтому всегда UTF-8.
OUTPUT_ENCODING = "utf-8"

_BOM = "﻿"


class _CliError(Exception):
    """Ошибка, о которой пользователю сообщается одной строкой (код возврата 2)."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kyrgyz-transliteration",
        description=(
            "Транслитерация кыргызского текста: кириллица <-> английская латиница."
        ),
        epilog=(
            "Без аргумента TEXT и без --input текст читается со стандартного ввода "
            "(«-» вместо TEXT тоже означает стандартный ввод). Вывод всегда в UTF-8."
        ),
    )
    parser.add_argument("text", nargs="*", help="текст для транслитерации")
    parser.add_argument(
        "-i",
        "--input",
        metavar="FILE",
        help="читать текст из файла, а не со стандартного ввода",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="записать результат в файл (UTF-8), а не на стандартный вывод",
    )
    parser.add_argument(
        "--encoding",
        metavar="ENC",
        default=DEFAULT_ENCODING,
        help=(
            f"кодировка входного текста (по умолчанию: {DEFAULT_ENCODING}; BOM распознаётся), "
            "например cp1251 для старых файлов Windows"
        ),
    )
    parser.add_argument(
        "-s",
        "--scheme",
        default=DEFAULT_SCHEME,
        help=f"схема транслитерации (по умолчанию: {DEFAULT_SCHEME})",
    )
    parser.add_argument(
        "-d",
        "--direction",
        choices=("auto", "latin", "cyrillic"),
        default="auto",
        help=(
            "направление преобразования (по умолчанию: auto); с latin/cyrillic "
            "текст обрабатывается построчно, потоково"
        ),
    )
    parser.add_argument(
        "--no-words",
        dest="words",
        action="store_false",
        help=(
            "не восстанавливать ө, ү и ң по встроенному списку частотных "
            "кыргызских слов: читать латиницу только правилами схемы"
        ),
    )
    parser.add_argument(
        "--wordlist",
        metavar="FILE",
        help=(
            "добавить свой список слов (одно слово в строке, кириллицей, UTF-8); "
            "встроенный список тоже используется"
        ),
    )
    parser.add_argument(
        "--no-normalize",
        dest="normalize",
        action="store_false",
        help=(
            "не чистить кириллицу перед транслитерацией (двойники ө/ү/ң, латинские "
            "буквы внутри слов, ударения, невидимые символы)"
        ),
    )
    parser.add_argument(
        "--slug", action="store_true", help="вывести ASCII-слаг вместо транслитерации"
    )
    parser.add_argument(
        "--detect", action="store_true", help="определить письменность и выйти"
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="показать доступные схемы"
    )
    parser.add_argument(
        "--table",
        metavar="SCHEME",
        nargs="?",
        const=DEFAULT_SCHEME,
        help="показать таблицу соответствий схемы",
    )
    parser.add_argument("-V", "--version", action="version", version=__version__)
    return parser


def _configure_streams() -> None:
    """Перевести стандартные потоки на UTF-8 там, где Python сам этого не делает.

    На Windows каналы и перенаправления (``< in.txt``, ``> out.txt``, ``| clip``,
    консоль PyCharm) Python кодирует системной кодовой страницей — cp1251, в
    которой нет ө, ү и ң: ``--help``, ``--list`` и вывод кириллицы падали с
    UnicodeEncodeError, а UTF-8 на входе читался как кракозябры. Явно заданный
    PYTHONIOENCODING уважается. Терминал сохраняет свою кодировку, но символы,
    которых в ней нет, печатаются как ``\\uXXXX``, а не роняют программу.
    Переводы строк не преобразуются: что пришло (LF или CRLF), то и ушло.
    """
    if os.environ.get("PYTHONIOENCODING"):
        return
    for name, encoding, errors in (
        ("stdin", "utf-8-sig", "strict"),
        ("stdout", OUTPUT_ENCODING, "backslashreplace"),
        ("stderr", OUTPUT_ENCODING, "backslashreplace"),
    ):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # None под pythonw, io.StringIO в тестах
            continue
        try:
            if stream.isatty():
                if name != "stdin":
                    reconfigure(errors=errors)
            else:
                reconfigure(encoding=encoding, errors=errors, newline="")
        except (ValueError, OSError):  # pragma: no cover - закрытый или подменённый поток
            pass


def _input_encoding(encoding: str) -> str:
    """Имя кодировки для чтения; UTF-8 читается как utf-8-sig, чтобы отбросить BOM."""
    try:
        name = codecs.lookup(encoding).name
    except LookupError:
        raise _CliError(f"неизвестная кодировка {encoding!r}") from None
    return "utf-8-sig" if name == "utf-8" else encoding


def _print_schemes(stream: IO[str]) -> None:
    width = max(len(scheme.name) for scheme in list_schemes())
    for scheme in list_schemes():
        mark = " (с потерями)" if scheme.lossy else ""
        stream.write(f"{scheme.name.ljust(width)}  {scheme.title}{mark}\n")
        if scheme.notes:
            stream.write("{}  {}\n".format(" " * width, scheme.notes))


def _print_table(name: str, stream: IO[str]) -> None:
    scheme = get_scheme(name)
    stream.write(f"{scheme.name} — {scheme.title}\n")
    pairs = ["{} {}".format(cyr, lat or "-") for cyr, lat in alphabet_table(scheme)]
    for start in range(0, len(pairs), 6):
        stream.write(
            "  " + "   ".join(cell.ljust(6) for cell in pairs[start : start + 6]).rstrip() + "\n"
        )


def _load_wordlist(args: argparse.Namespace) -> bool | Wordlist:
    wordlist: bool | Wordlist = args.words
    if args.wordlist:
        try:
            custom = Wordlist.from_file(args.wordlist)
        except UnicodeDecodeError as error:
            raise _CliError(
                f"список слов {args.wordlist!r} должен быть в UTF-8 (байт 0x{error.object[error.start]:02x} в позиции {error.start})"
            ) from None
        base = builtin_wordlist().copy() if args.words else Wordlist()
        wordlist = base.merge(custom)
    return wordlist


def _open_source(
    args: argparse.Namespace, stack: contextlib.ExitStack
) -> Tuple[Optional[IO[str]], bool]:
    """Откуда читать: файл ``--input`` или стандартный ввод; ``None`` — текст в аргументах.

    Второй элемент — читаем ли мы с терминала (тогда работаем построчно).
    """
    if args.text and args.text != ["-"]:
        return None, False
    encoding = _input_encoding(args.encoding)
    if args.input and args.input != "-":
        return stack.enter_context(open(args.input, encoding=encoding, newline="")), False
    stdin = sys.stdin
    try:
        interactive = stdin.isatty()
    except (AttributeError, ValueError):
        interactive = False
    if not interactive and args.encoding != DEFAULT_ENCODING and hasattr(stdin, "reconfigure"):
        stdin.reconfigure(encoding=encoding)
    if interactive:
        sys.stderr.write(
            "Читаю текст со стандартного ввода построчно; закончить: "
            "Ctrl-Z и Enter (Windows) или Ctrl-D.\n"
        )
    return stdin, interactive


def _lines(args: argparse.Namespace, source: Optional[IO[str]]) -> Iterator[str]:
    """Строки текста вместе с их переводами строк; BOM в начале отбрасывается."""
    if source is None:
        text = " ".join(args.text)
        if text:
            yield text if text.endswith("\n") else text + "\n"
        return
    first = True
    for line in source:
        if first and line.startswith(_BOM):
            line = line[1:]
        first = False
        yield line


def _chain(first: str, rest: Iterator[str]) -> Iterator[str]:
    yield first
    yield from rest


def _mute_stdout() -> None:
    """После разрыва канала (``| head``) не дать Python ругаться на flush при выходе."""
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except (OSError, ValueError, AttributeError):  # pragma: no cover
        pass


def _fail(message: str) -> int:
    sys.stderr.write(f"ошибка: {message}\n")
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    _configure_streams()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        with contextlib.ExitStack() as stack:
            if args.list:
                _print_schemes(sys.stdout)
                return 0
            if args.table is not None:
                _print_table(args.table, sys.stdout)
                return 0

            scheme = get_scheme(args.scheme)  # проверяем имя схемы до чтения ввода
            _input_encoding(args.encoding)  # и имя кодировки
            wordlist = _load_wordlist(args)
            source, interactive = _open_source(args, stack)
            lines = _lines(args, source)
            first = next(lines, None)
            if first is None:
                parser.print_usage(sys.stderr)
                return 2
            lines = _chain(first, lines)

            out: IO[str] = sys.stdout
            if args.output:
                out = stack.enter_context(
                    open(args.output, "w", encoding=OUTPUT_ENCODING, newline="")
                )

            if args.detect:
                out.write(detect_script("".join(lines).strip(), normalize=args.normalize) + "\n")
                return 0
            if args.slug:
                out.write(
                    slugify("".join(lines).strip(), scheme=scheme, normalize=args.normalize) + "\n"
                )
                return 0

            if args.direction == "auto" and not interactive:
                # направление выбирается по всему тексту
                out.write(
                    transliterate("".join(lines), scheme, "auto", wordlist, normalize=args.normalize)
                )
            else:
                for line in lines:  # потоково: память не зависит от размера файла
                    out.write(
                        transliterate(line, scheme, args.direction, wordlist, normalize=args.normalize)
                    )
                    if interactive:
                        out.flush()
            return 0
    except UnknownSchemeError as error:
        return _fail(error.args[0])
    except _CliError as error:
        return _fail(str(error))
    except UnicodeDecodeError as error:
        return _fail(
            f"ввод не в кодировке {args.encoding} (байт 0x{error.object[error.start]:02x} в позиции {error.start}); укажите кодировку "
            "файла, например --encoding cp1251"
        )
    except BrokenPipeError:  # читатель закрыл канал (``| head``) — это не ошибка
        _mute_stdout()
        return 0
    except OSError as error:
        return _fail(str(error))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
