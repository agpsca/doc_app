"""Carrega documentos (e temas) a partir de arquivos YAML.

Formato do arquivo:

    # opcional — sobrescreve campos do tema padrão
    theme:
      cover:
        title: "Meu App"
        subtitle: "Documentação"
        tagline: "..."
        footnote: "..."
      header_left: "Meu App · Documentação"
      header_right: "Uso e regras"
      palette:        # qualquer cor como [r, g, b]
        brand: [0, 102, 78]
        accent: [5, 220, 127]

    # obrigatório — a lista de blocos
    blocks:
      - h1: "Visão geral"
      - p: "Texto do parágrafo..."
      - bullet:
          - "Primeiro item"
          - "Segundo item"
      - callout:
          title: "Atenção"
          text: "Corpo do destaque."
      - kv:
          - key: "BACKEND_URL"
            value: "Descrição..."
      - table:
          header: ["Coluna A", "Coluna B"]
          rows:
            - ["a1", "b1"]
          widths: [45, 125]
      - code: |
          linha 1
          linha 2
      - spacer: 4

Cada bloco é um mapa de **uma única chave**, cujo nome é o tipo do bloco.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import yaml

from .dsl import Block
from .theme import DOC_TYPES, Palette, Theme

_PALETTE_FIELDS = {f.name for f in dataclasses.fields(Palette)}


def _parse_color(name: str, value: Any) -> tuple[int, int, int]:
    """Aceita '#RRGGBB' (forma gravada pelo doc_app) ou [r, g, b]."""
    if name not in _PALETTE_FIELDS:
        raise ValueError(f"Cor de paleta desconhecida: {name!r}. "
                         f"Use uma de: {', '.join(sorted(_PALETTE_FIELDS))}.")
    if isinstance(value, str):
        h = value.strip().lstrip("#")
        if len(h) == 6:
            try:
                return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                pass
    elif isinstance(value, (list, tuple)) and len(value) == 3:
        return tuple(int(c) for c in value)
    raise ValueError(f"Cor {name!r} inválida: {value!r}. Use '#RRGGBB'.")


def load_document(path: str | Path,
                  type_override: str | None = None) -> tuple[list[Block], Theme, str]:
    """Lê um YAML e devolve (blocks, theme, doc_type).

    O tipo (brand|development|full) vem de `type_override` (CLI/painel) quando
    dado, senão da chave de topo `type:` (aceita `face:` legado; padrão: brand).
    Ele seleciona o tema base; a seção `theme:` aplica overrides por cima.
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict) or "blocks" not in raw:
        raise ValueError(
            f"{path}: o YAML precisa ter uma chave de nível superior 'blocks'."
        )
    doc_type = type_override or raw.get("type") or raw.get("face") or "brand"
    if doc_type not in DOC_TYPES:
        raise ValueError(
            f"{path}: tipo {doc_type!r} inválido. Use um de: {', '.join(DOC_TYPES)}."
        )
    blocks = _parse_blocks(raw["blocks"])
    theme = _parse_theme(raw.get("theme"), base=DOC_TYPES[doc_type])
    # Backend não tem identidade visual própria: sempre usa a paleta do doc_app,
    # mesmo que o YAML peça outra.
    if raw.get("app_kind") == "backend":
        theme = dataclasses.replace(theme, palette=Palette())
    return blocks, theme, doc_type


def save_document(path: str | Path, blocks: list[dict], doc_type: str,
                  theme_overrides: dict | None = None,
                  app_kind: str | None = None,
                  brand_source: str | None = None) -> Path:
    """Escreve o YAML da documentação (esqueleto ou editado).

    `brand_source` registra de onde vieram as cores detectadas no app; é só
    informativo, para quem for revisar o YAML.
    """
    doc: dict[str, Any] = {"type": doc_type}
    if app_kind:
        doc["app_kind"] = app_kind
    if brand_source:
        doc["brand_source"] = brand_source
    if theme_overrides:
        doc["theme"] = theme_overrides
    doc["blocks"] = blocks
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    return out


def _parse_blocks(items: Any) -> list[Block]:
    if not isinstance(items, list):
        raise ValueError("'blocks' precisa ser uma lista.")  # noqa: TRY004
    blocks: list[Block] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or len(item) != 1:
            raise ValueError(
                f"Bloco #{i}: cada bloco deve ser um mapa de uma única chave "
                f"(ex.: '- h1: ...'), recebido: {item!r}"
            )
        (typ, content), = item.items()
        blocks.append(Block(type=typ, content=content))
    return blocks


def _parse_theme(spec: Any, base: Theme) -> Theme:
    """Aplica overrides do YAML sobre o tema base (tudo opcional)."""
    if not spec:
        return base
    if not isinstance(spec, dict):
        raise ValueError("'theme' precisa ser um mapa.")  # noqa: TRY004

    replace: dict[str, Any] = {}

    if "palette" in spec:
        colors = {k: _parse_color(k, v) for k, v in spec["palette"].items()}
        replace["palette"] = dataclasses.replace(base.palette, **colors)
    if "cover" in spec:
        replace["cover"] = dataclasses.replace(base.cover, **spec["cover"])
    if "header_left" in spec:
        replace["header_left"] = spec["header_left"]
    if "header_right" in spec:
        replace["header_right"] = spec["header_right"]
    if "footer_left" in spec:
        replace["footer_left"] = spec["footer_left"]
    if "classification" in spec:
        replace["classification"] = spec["classification"] or None

    return dataclasses.replace(base, **replace)
