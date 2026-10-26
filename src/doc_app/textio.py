"""Leitura de arquivos de texto do app documentado, com detecção de codificação.

Repositórios reais trazem arquivos em UTF-16 (comum em README criado no
Windows), UTF-8 com BOM e Latin-1. Ler tudo como UTF-8 gera texto corrompido
no PDF, então todos os módulos que leem o app usam `read_text`.
"""

from __future__ import annotations

import codecs
from pathlib import Path

DEFAULT_MAX = 512 * 1024

_BOMS = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


def read_text(path: Path, max_bytes: int = DEFAULT_MAX) -> str | None:
    """Lê `path` como texto. Devolve None se não existir, for grande demais
    ou parecer binário. Quebras de linha são normalizadas para '\\n'."""
    try:
        if not path.is_file() or path.stat().st_size > max_bytes:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    text = decode(data)
    if text is None:
        return None
    return text.replace("\r\n", "\n").replace("\r", "\n")


def decode(data: bytes) -> str | None:
    for bom, encoding in _BOMS:
        if data.startswith(bom):
            return data.decode(encoding, errors="replace")
    # UTF-16 sem BOM: metade dos bytes nulos, alternados.
    if len(data) >= 4 and data.count(b"\0") > len(data) // 3:
        even, odd = data[0::2].count(0), data[1::2].count(0)
        if odd > even * 4:
            return data.decode("utf-16-le", errors="replace")
        if even > odd * 4:
            return data.decode("utf-16-be", errors="replace")
        return None  # nulos sem padrão de texto: binário
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")
