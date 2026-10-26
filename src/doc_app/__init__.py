"""doc_app — gerador de documentação em PDF a partir de uma DSL de blocos."""

from __future__ import annotations

from .builder import build_pdf
from .dsl import Block, from_tuples
from .loader import load_document, save_document
from .theme import (
    BRAND_THEME,
    DEFAULT_THEME,
    DEVELOPMENT_THEME,
    DOC_TYPES,
    FULL_THEME,
    Theme,
)

__all__ = [
    "BRAND_THEME",
    "DEFAULT_THEME",
    "DEVELOPMENT_THEME",
    "DOC_TYPES",
    "FULL_THEME",
    "Block",
    "Theme",
    "build_pdf",
    "from_tuples",
    "load_document",
    "save_document",
]
