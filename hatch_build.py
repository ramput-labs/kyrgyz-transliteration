"""Сборочный хук hatchling: в wheel списки слов кладутся сжатыми.

В репозитории ``src/kyrgyz_transliteration/data/*.txt`` остаются обычным
текстом — их удобно править и смотреть в диффах. При сборке wheel каждый
такой файл сжимается gzip (детерминированно, с нулевым временем), кладётся
рядом как ``*.txt.gz``, а сам текст в wheel не попадает. Пакет читает
``*.txt.gz``, если он есть, иначе ``*.txt`` (см. ``restore._resource_text``),
поэтому ``pip install -e .`` и запуск из исходников работают как раньше.
"""

from __future__ import annotations

import gzip
import io
import os
import tempfile
from typing import Any, Dict

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

DATA_DIR = os.path.join("src", "kyrgyz_transliteration", "data")
PACKAGE_DATA = "kyrgyz_transliteration/data"


def _gzip_bytes(raw: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0) as packed:
        packed.write(raw)
    return buffer.getvalue()


class CompressDataHook(BuildHookInterface):
    PLUGIN_NAME = "compress-data"

    def initialize(self, version: str, build_data: Dict[str, Any]) -> None:
        if self.target_name != "wheel" or version == "editable":
            return
        self._tmp = tempfile.TemporaryDirectory()
        source_dir = os.path.join(self.root, DATA_DIR)
        for name in sorted(os.listdir(source_dir)):
            if not name.endswith(".txt"):
                continue
            with open(os.path.join(source_dir, name), "rb") as handle:
                packed = _gzip_bytes(handle.read())
            target = os.path.join(self._tmp.name, name + ".gz")
            with open(target, "wb") as handle:
                handle.write(packed)
            build_data["force_include"][target] = PACKAGE_DATA + "/" + name + ".gz"

    def finalize(self, version: str, build_data: Dict[str, Any], artifact_path: str) -> None:
        tmp = getattr(self, "_tmp", None)
        if tmp is not None:
            tmp.cleanup()
