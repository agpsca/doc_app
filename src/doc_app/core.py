"""Operações do doc_app sem interação com terminal.

Usado pelo painel/CLI (`cli.py`) e pelo servidor MCP (`mcp_server.py`):
caminhos do workspace, criação da documentação inicial e geração do PDF.
Nada aqui imprime ou pergunta; quem chama decide como mostrar o resultado.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from .brand import BrandColors, detect_brand
from .builder import build_pdf
from .extract import ProjectFacts, extract_facts
from .loader import load_document, save_document
from .skeleton import skeleton_blocks
from .theme import DOC_TYPES, Theme

WORKSPACE_DIRNAME = "workspace"
DEFAULT_TYPE = "brand"
DEFAULT_MARK = "Uso interno"


# --- caminhos --------------------------------------------------------------

def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2] / WORKSPACE_DIRNAME


def cache_dir(app_name: str) -> Path:
    return workspace_root() / app_name


def doc_path(app_name: str, doc_type: str) -> Path:
    return cache_dir(app_name) / f"{doc_type}.yaml"


def desktop_dir() -> Path:
    desktop = Path.home() / "Desktop"
    return desktop if desktop.is_dir() else Path.home()


def default_output(app_name: str, doc_type: str) -> Path:
    return desktop_dir() / f"{app_name}-{doc_type}.pdf"


def normalize_output(raw: str, app_name: str, doc_type: str) -> Path:
    """Tolerante: diretório -> salva dentro; sem .pdf -> acrescenta."""
    path = Path(raw).expanduser()
    if raw.endswith(("/", "\\")) or path.is_dir():
        return path / f"{app_name}-{doc_type}.pdf"
    if path.suffix.lower() != ".pdf":
        path = path.with_name(path.name + ".pdf")
    return path


def check_doc_type(doc_type: str) -> str:
    if doc_type not in DOC_TYPES:
        raise ValueError(f"Tipo {doc_type!r} inválido. Use um de: {', '.join(DOC_TYPES)}.")
    return doc_type


def app_dir(app_path: str | Path) -> Path:
    path = Path(app_path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"App não encontrado (não é um diretório): {path}")
    return path


# --- criação ---------------------------------------------------------------

@dataclass
class CreateResult:
    path: Path
    facts: ProjectFacts
    colors: BrandColors | None
    todos: int
    created: bool        # False se já existia e não foi recriado


def create_doc(app_path: Path, doc_type: str, overwrite: bool = False) -> CreateResult:
    """Cria o YAML inicial (fatos extraídos + trechos (TODO)) no workspace."""
    check_doc_type(doc_type)
    app_name = app_path.name
    dp = doc_path(app_name, doc_type)
    facts = extract_facts(app_path)
    if dp.exists() and not overwrite:
        return CreateResult(dp, facts, None, count_todos_in_file(dp), created=False)

    blocks = skeleton_blocks(facts, doc_type)
    overrides: dict = {
        "cover": {"title": app_name},
        "header_left": f"{app_name} · Documentação",
        "footer_left": app_name,
    }
    colors = None
    brand_source = None
    if facts.stack.kind in ("frontend", "fullstack"):
        colors = detect_brand(app_path)
        if colors:
            overrides["palette"] = colors.palette_overrides()
            brand_source = "; ".join(colors.sources)
    save_document(dp, blocks, doc_type, theme_overrides=overrides,
                  app_kind=facts.stack.kind, brand_source=brand_source)
    return CreateResult(dp, facts, colors, count_todos(blocks), created=True)


def count_todos(blocks: list[dict]) -> int:
    return sum(1 for b in blocks for v in b.values() if "(TODO)" in str(v))


def count_todos_in_file(path: Path) -> int:
    import yaml
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return count_todos(raw.get("blocks") or [])


# --- geração ---------------------------------------------------------------

@dataclass
class BuildResult:
    output: Path
    blocks: int
    doc_type: str
    theme: Theme


def build(app_name: str, doc_type: str, output: Path,
          mark: str | None = None) -> BuildResult:
    """Gera o PDF a partir do YAML do workspace. `mark` aplica a marca de
    classificação só nesta geração, sem alterar o YAML."""
    dp = doc_path(app_name, doc_type)
    if not dp.exists():
        raise FileNotFoundError(f"Sem documentação {doc_type!r} no cache para "
                                f"{app_name!r} ({dp}). Crie com create_doc primeiro.")
    blocks, theme, used_type = load_document(dp, type_override=doc_type)
    if mark:
        theme = dataclasses.replace(theme, classification=mark)
    out = build_pdf(blocks, output, theme)
    return BuildResult(out, len(blocks), used_type, theme)
