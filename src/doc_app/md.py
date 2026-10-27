"""Markdown -> blocos da DSL.

Converte o corpo de uma seção de README no subconjunto de blocos que o
documento usa: parágrafo, listas, código, tabela e subtítulo (h3). É o que
permite aproveitar o README inteiro, e não só a introdução, sem pedir para o
agente reescrever o que já está escrito.

Fora do escopo: HTML, imagens, notas de rodapé e listas aninhadas (a DSL não
tem nível), que entram achatadas.
"""

from __future__ import annotations

import re

PAGE_WIDTH = 170   # largura útil da página, em mm (igual ao validador da DSL)
MIN_COL = 18       # largura mínima de uma coluna de tabela, em mm

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^\s*(#{1,6})\s+(.*)")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(.+)")
_NUMBERED = re.compile(r"^(\s*)\d+[.)]\s+(.+)")
_ROW = re.compile(r"^\s*\|.*\|\s*$")
_DIVIDER = re.compile(r"^\s*\|[\s:|\-]+\|\s*$")
_QUOTE = re.compile(r"^\s*>\s?(.*)")
_HR = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")


def plain_markdown(text: str) -> str:
    """Remove marcações simples de Markdown para caber no PDF."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)          # imagens
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)       # links
    text = re.sub(r"`([^`]+)`", r"\1", text)                   # código inline
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)            # negrito
    text = re.sub(r"(?<!\w)[*_](.+?)[*_](?!\w)", r"\1", text)  # itálico
    return re.sub(r"\s+", " ", text).strip()


def md_blocks(lines: list[str], keep: tuple[str, ...] | None = None,
              max_blocks: int = 60) -> list[dict]:
    """Blocos da DSL para o corpo de uma seção de Markdown.

    `keep` filtra os tipos aproveitados (ex.: só a prosa de uma seção cujo
    quadro já está no documento como fato extraído).
    """
    blocks: list[dict] = []
    i, total = 0, len(lines)
    while i < total and len(blocks) < max_blocks:
        line = lines[i]
        if not line.strip() or _HR.match(line):
            i += 1
            continue
        if _FENCE.match(line):
            i, block = _take_code(lines, i)
        elif (m := _HEADING.match(line)):
            i, block = i + 1, _text_block("h3", m.group(2))
        elif _ROW.match(line) and i + 1 < total and _DIVIDER.match(lines[i + 1]):
            i, block = _take_table(lines, i)
        elif _BULLET.match(line) or _NUMBERED.match(line):
            i, block = _take_list(lines, i)
        else:
            i, block = _take_paragraph(lines, i)
        if block:
            blocks.append(block)
    if keep is not None:
        blocks = [b for b in blocks if next(iter(b)) in keep]
    return blocks


def _text_block(typ: str, raw: str) -> dict | None:
    text = plain_markdown(raw)
    return {typ: text} if text else None


# --- código ----------------------------------------------------------------

def _take_code(lines: list[str], i: int) -> tuple[int, dict | None]:
    marker = _FENCE.match(lines[i]).group(1)
    body: list[str] = []
    i += 1
    while i < len(lines) and not lines[i].strip().startswith(marker):
        body.append(lines[i].rstrip())
        i += 1
    code = "\n".join(body).strip("\n")
    return i + 1, {"code": code} if code else None


# --- tabela ----------------------------------------------------------------

def _cells(line: str) -> list[str]:
    return [plain_markdown(c) for c in line.strip().strip("|").split("|")]


def _take_table(lines: list[str], i: int) -> tuple[int, dict | None]:
    header = [c or "—" for c in _cells(lines[i])]
    i += 2                                        # pula o divisor
    rows: list[list[str]] = []
    while i < len(lines) and _ROW.match(lines[i]):
        cells = _cells(lines[i])[: len(header)]
        rows.append(cells + [""] * (len(header) - len(cells)))
        i += 1
    if not rows:
        return i, None
    if MIN_COL * len(header) > PAGE_WIDTH:         # tabela larga demais: vira lista
        return i, {"bullet": [" · ".join(c for c in row if c) or "—" for row in rows]}
    return i, {"table": {"header": header, "widths": _widths(header, rows),
                         "rows": rows}}


def _widths(header: list[str], rows: list[list[str]]) -> list[int]:
    """Larguras proporcionais ao texto mais longo de cada coluna."""
    longest = [max(len(row[c]) for row in [header, *rows]) or 1
               for c in range(len(header))]
    total = sum(longest)
    widths = [max(MIN_COL, round(PAGE_WIDTH * n / total)) for n in longest]
    while sum(widths) > PAGE_WIDTH:                # sobra de arredondamento
        widths[widths.index(max(widths))] -= 1
    return widths


# --- listas e parágrafos ---------------------------------------------------

def _take_list(lines: list[str], i: int) -> tuple[int, dict | None]:
    numbered = bool(_NUMBERED.match(lines[i]))
    items: list[str] = []
    while i < len(lines):
        line = lines[i]
        m = _NUMBERED.match(line) if numbered else _BULLET.match(line)
        other = _BULLET.match(line) if numbered else _NUMBERED.match(line)
        if m:
            items.append(m.group(2).strip())
        elif other and other.group(1):             # lista aninhada: achata
            items.append(other.group(2).strip())
        elif not line.strip() or _FENCE.match(line) or _HEADING.match(line) \
                or _ROW.match(line) or other:
            break
        elif items:                                # continuação do item anterior
            items[-1] += " " + line.strip()
        else:
            break
        i += 1
    clean = [t for t in (plain_markdown(it) for it in items) if t]
    return i, {"num" if numbered else "bullet": clean} if clean else None


def _take_paragraph(lines: list[str], i: int) -> tuple[int, dict | None]:
    para: list[str] = []
    while i < len(lines):
        line = lines[i]
        if not line.strip() or _FENCE.match(line) or _HEADING.match(line) \
                or _BULLET.match(line) or _NUMBERED.match(line) or _ROW.match(line) \
                or _HR.match(line):
            break
        quote = _QUOTE.match(line)
        para.append(quote.group(1) if quote else line.strip())
        i += 1
    return i, _text_block("p", " ".join(para))
