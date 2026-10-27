"""DSL de blocos da documentação.

Um documento é uma sequência de *blocos* e cada bloco tem um `type` e um
`content`, cujo formato depende do tipo. Esta é a mesma ideia da lista `DOC`
do script original, agora formalizada e desacoplada da renderização.

Tipos suportados:
    h1, h2, h3   -> content: str                (títulos)
    p            -> content: str                (parágrafo)
    bullet       -> content: list[str]          (lista com marcadores)
    num          -> content: list[str]          (lista numerada)
    code         -> content: str                (bloco de código monoespaçado)
    callout      -> content: {title, text}      (caixa de destaque)
    kv           -> content: list[{key, value}] (pares chave/valor)
    table        -> content: {header, rows, widths?}
    spacer       -> content: float              (espaço vertical em mm)

Blocos de identidade visual, desenhados no tipo "slides" (no documento em A4
viram imagem, tabela ou parágrafo equivalentes):
    logo         -> content: {path, caption?}            (asset da marca)
    clearspace   -> content: {path, ratio?, caption?}    (área de proteção)
    swatches     -> content: {items: [{name, hex, source?}]}
    specimen     -> content: {font, role?, weights?, sample?, source?}

O formato interno canônico é uma lista de `Block`. O `loader` converte YAML
(e a lista de tuplas legada) para esses blocos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

BLOCK_TYPES = {
    "h1", "h2", "h3", "p", "bullet", "num",
    "code", "callout", "kv", "table", "spacer",
    # blocos de identidade visual (usados pelo tipo "slides")
    "logo", "swatches", "clearspace", "specimen",
}


@dataclass
class Block:
    type: str
    content: Any

    def __post_init__(self) -> None:
        if self.type not in BLOCK_TYPES:
            raise ValueError(
                f"Tipo de bloco desconhecido: {self.type!r}. "
                f"Tipos válidos: {', '.join(sorted(BLOCK_TYPES))}."
            )


def from_tuples(doc: list[tuple[str, Any]]) -> list[Block]:
    """Converte a lista de tuplas legada (DOC = [(tipo, conteúdo), ...])."""
    return [Block(type=typ, content=content) for typ, content in doc]


def _is_str_list(v: Any) -> bool:
    return isinstance(v, list) and bool(v) and all(isinstance(x, str) and x.strip()
                                                   for x in v)


def validate_block(item: Any, where: str = "bloco") -> list[str]:
    """Valida um bloco no formato do YAML (`{tipo: conteúdo}`).

    Devolve a lista de erros, vazia quando o bloco é válido. As mensagens
    dizem o formato esperado, para quem escreveu o bloco conseguir corrigir.
    """
    if not isinstance(item, dict) or len(item) != 1:
        return [f"{where}: cada bloco é um mapa de uma única chave, ex.: "
                f'{{"p": "texto"}}. Recebido: {item!r:.120}']
    (typ, content), = item.items()
    if typ not in BLOCK_TYPES:
        return [f"{where}: tipo {typ!r} não existe. Use um de: "
                f"{', '.join(sorted(BLOCK_TYPES))}."]

    errors: list[str] = []
    if typ in ("h1", "h2", "h3", "p", "code"):
        if not isinstance(content, str) or not content.strip():
            errors.append(f"{where} ({typ}): o conteúdo deve ser um texto não vazio.")
    elif typ in ("bullet", "num"):
        if not _is_str_list(content):
            errors.append(f"{where} ({typ}): o conteúdo deve ser uma lista de textos "
                          "não vazios.")
    elif typ == "callout":
        if not (isinstance(content, dict) and isinstance(content.get("title"), str)
                and isinstance(content.get("text"), str) and content["text"].strip()):
            errors.append(f'{where} (callout): use {{"title": "...", "text": "..."}}.')
    elif typ == "kv":
        ok = isinstance(content, list) and bool(content) and all(
            isinstance(p, dict) and isinstance(p.get("key"), str)
            and isinstance(p.get("value"), str) for p in content)
        if not ok:
            errors.append(f'{where} (kv): use [{{"key": "...", "value": "..."}}, ...].')
    elif typ == "table":
        errors += _validate_table(content, where)
    elif typ == "logo":
        errors += _validate_logo(content, where)
    elif typ == "clearspace":
        errors += _validate_logo(content, where, kind="clearspace")
    elif typ == "swatches":
        errors += _validate_swatches(content, where)
    elif typ == "specimen":
        if not (isinstance(content, dict) and isinstance(content.get("font"), str)
                and content["font"].strip()):
            errors.append(f'{where} (specimen): use {{"font": "Space Grotesk", '
                          '"role": "sans", "weights": "400, 500", '
                          '"sample": "texto de amostra", "source": "arquivo"}}.')
    elif typ == "spacer":
        if not isinstance(content, (int, float)) or not 0 < content <= 50:
            errors.append(f"{where} (spacer): use um número de 1 a 50 (mm).")
    return errors


def _validate_logo(spec: Any, where: str, kind: str = "logo") -> list[str]:
    extra = ', "ratio": 0.5' if kind == "clearspace" else ""
    fmt = f'{{"path": "public/logo.svg", "caption": "..."{extra}}}'
    if not (isinstance(spec, dict) and isinstance(spec.get("path"), str)
            and spec["path"].strip()):
        return [f"{where} ({kind}): 'path' deve ser o caminho da imagem "
                f"(SVG ou PNG), relativo à pasta do app. Formato: {fmt}."]
    errors = []
    ratio = spec.get("ratio")
    if ratio is not None and not (isinstance(ratio, (int, float)) and 0 < ratio <= 2):
        errors.append(f"{where} ({kind}): 'ratio' é a fração da altura do símbolo "
                      "usada como respiro; use um número entre 0 e 2 (ex.: 0.5).")
    on = spec.get("on")
    if on is not None and on not in ("light", "dark", "both"):
        errors.append(f"{where} ({kind}): 'on' indica o fundo da amostra; use "
                      '"light", "dark" ou "both".')
    if spec.get("path_dark") is not None and not isinstance(spec["path_dark"], str):
        errors.append(f"{where} ({kind}): 'path_dark' é o caminho da versão para "
                      "fundo escuro.")
    return errors


def _validate_swatches(spec: Any, where: str) -> list[str]:
    fmt = ('{"items": [{"name": "brand-green", "hex": "#00664E", '
           '"source": "globals.css"}]}')
    items = spec.get("items") if isinstance(spec, dict) else None
    if not isinstance(items, list) or not items:
        return [f"{where} (swatches): 'items' deve ser uma lista não vazia. "
                f"Formato: {fmt}."]
    for i, item in enumerate(items):
        if not (isinstance(item, dict) and isinstance(item.get("name"), str)
                and isinstance(item.get("hex"), str)
                and re.fullmatch(r"#[0-9a-fA-F]{6}", item["hex"].strip())):
            return [f"{where} (swatches): item {i} precisa de 'name' e 'hex' "
                    f"em #RRGGBB. Formato: {fmt}."]
    return []


def _validate_table(spec: Any, where: str) -> list[str]:
    fmt = '{"header": ["A", "B"], "rows": [["a1", "b1"]], "widths": [60, 110]}'
    if not isinstance(spec, dict):
        return [f"{where} (table): use {fmt}."]
    header, rows = spec.get("header"), spec.get("rows")
    if not _is_str_list(header):
        return [f"{where} (table): 'header' deve ser uma lista de textos. Formato: {fmt}."]
    errors = []
    if not isinstance(rows, list) or not rows:
        errors.append(f"{where} (table): 'rows' deve ser uma lista não vazia de linhas.")
    else:
        for i, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != len(header):
                errors.append(f"{where} (table): a linha {i} deve ter {len(header)} "
                              f"células, como o header.")
                break
    widths = spec.get("widths")
    if widths is not None:
        if (not isinstance(widths, list) or len(widths) != len(header)
                or not all(isinstance(w, (int, float)) and w > 0 for w in widths)):
            errors.append(f"{where} (table): 'widths' deve ter {len(header)} números "
                          "positivos (mm).")
        elif sum(widths) > 291:
            errors.append(f"{where} (table): a soma de 'widths' é {sum(widths)} mm; "
                          "a largura útil é 170 mm no documento A4 e 290 mm no "
                          "slide. Sem 'widths', as colunas ficam iguais.")
    return errors
