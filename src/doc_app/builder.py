"""Monta o PDF a partir de uma lista de blocos e um tema.

Orquestra a renderização: capa, sumário e corpo. Faz o dispatch de cada
tipo de bloco para o método correspondente do `Renderer`.
"""

from __future__ import annotations

from pathlib import Path

from .dsl import Block
from .renderer import Renderer
from .theme import DEFAULT_THEME, Theme


def build_pdf(
    blocks: list[Block],
    output_path: str | Path,
    theme: Theme | None = None,
) -> Path:
    """Gera o PDF em `output_path` a partir dos `blocks`. Retorna o caminho."""
    theme = theme or DEFAULT_THEME
    renderer = Renderer(theme)
    pdf = renderer.pdf

    renderer.draw_cover()

    # Reserva a página do sumário agora; o conteúdo é renderizado ao final,
    # quando a página de cada seção já é conhecida (números de página reais).
    pdf.add_page()
    pdf.insert_toc_placeholder(renderer.render_toc, pages=1, allow_extra_pages=True)

    for i, block in enumerate(blocks):
        _render_block(renderer, block, i, _min_height(blocks, i + 1))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    return out


def _is_intro(block: Block) -> bool:
    """Frase de introdução ("...:") que deve ficar junto do bloco seguinte."""
    return block.type == "p" and str(block.content).rstrip().endswith(":")


def _min_height(blocks: list[Block], i: int) -> float:
    """Altura mínima (mm) que o bloco `blocks[i]` precisa para começar numa
    página sem ficar órfão. Encadeia frases de introdução com o bloco que as
    segue, para título → introdução → tabela/código não se separarem."""
    if i >= len(blocks):
        return 0.0
    block = blocks[i]
    typ, content = block.type, block.content
    if _is_intro(block):
        return 12.0 + _min_height(blocks, i + 1)
    if typ == "code":
        n = content.count("\n") + 1
        return (n if n <= 8 else 4) * 5.0 + 10
    if typ == "table":
        return 22.0          # cabeçalho + uma linha
    if typ in ("kv", "callout"):
        return 18.0
    if typ in ("h1", "h2", "h3"):
        return 20.0
    return 12.0              # parágrafo/lista: ~2 linhas


def _render_block(renderer: Renderer, block: Block, index: int,
                  next_min: float) -> None:
    typ = block.type
    content = renderer.clean_content(block.content, keep_spacing=(typ == "code"))
    anchor_id = f"b{index}"
    if typ in ("h1", "h2", "h3"):
        renderer.heading(content, int(typ[1]), anchor_id=anchor_id,
                         reserve=next_min)
    elif typ == "p":
        keep = next_min if _is_intro(block) else 0.0
        renderer.paragraph(content, keep_with=keep)
    elif typ == "bullet":
        renderer.bullets(content)
    elif typ == "num":
        renderer.bullets(content, numbered=True)
    elif typ == "code":
        renderer.code_block(content)
    elif typ == "callout":
        renderer.callout(content["title"], content["text"])
    elif typ == "kv":
        renderer.kv_block([(p["key"], p["value"]) for p in content])
    elif typ == "table":
        renderer.table_block(content)
    elif typ == "spacer":
        renderer.pdf.ln(content)
