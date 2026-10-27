"""Operações do doc_app sem interação com terminal.

Usado pelo painel/CLI (`cli.py`) e pelo servidor MCP (`mcp_server.py`):
caminhos do workspace, criação da documentação inicial e geração do PDF.
Nada aqui imprime ou pergunta; quem chama decide como mostrar o resultado.
"""

from __future__ import annotations

import dataclasses
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .brand import BrandColors, detect_brand
from .builder import build_pdf
from .extract import ProjectFacts, extract_facts
from .identity import Identity, detect_identity
from .loader import load_document, save_document
from .skeleton import skeleton_blocks
from .slides import build_slides
from .theme import DOC_TYPES, Theme

WORKSPACE_DIRNAME = "workspace"
DEFAULT_TYPE = "brand"
DEFAULT_MARK = "Uso interno"

# Formatos de saída: PDF para entregar, Office para editar fora do YAML.
# Rótulos usados no menu do painel; a ordem define a ordem das opções.
FORMATS = {
    "pdf": "📕  PDF             (pronto para enviar)",
    "docx": "📝  Word (.docx)    (editável no Word, Google Docs, LibreOffice)",
    "pptx": "📊  PowerPoint (.pptx) (editável no PowerPoint, Google Slides)",
}
DEFAULT_FORMAT = "pdf"


# --- caminhos --------------------------------------------------------------

# Caminho no formato do Windows: UNC (\\wsl.localhost\...) ou unidade (C:\...).
_WINDOWS_PATH = re.compile(r"^(\\\\|[A-Za-z]:[\\/])")


def parse_path(raw: str) -> Path:
    r"""Caminho como a pessoa digitou ou colou.

    Dentro do WSL, aceita o formato do Windows
    (`\\wsl.localhost\<distro>\home\...`, `C:\projetos\app`), convertido pelo
    próprio `wslpath`. O "Copiar como caminho" do Explorer traz aspas; saem.
    """
    raw = raw.strip().strip('"')
    if _WINDOWS_PATH.match(raw) and (wslpath := shutil.which("wslpath")):
        res = subprocess.run([wslpath, "-u", raw], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            raw = res.stdout.strip()
    return Path(raw).expanduser()


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2] / WORKSPACE_DIRNAME


def cache_dir(app_name: str) -> Path:
    return workspace_root() / app_name


def doc_path(app_name: str, doc_type: str) -> Path:
    return cache_dir(app_name) / f"{doc_type}.yaml"


# Último app documentado, lembrado no cache para não ter que digitar o caminho
# de novo. Fica solto no workspace/ (não é pasta de app, então `clean` ignora).
LAST_APP_FILE = "last-app.txt"


def last_app() -> Path | None:
    """Caminho do último app documentado, se a pasta ainda existir."""
    try:
        raw = (workspace_root() / LAST_APP_FILE).read_text(encoding="utf-8")
    except OSError:
        return None
    path = parse_path(raw)
    return path if path.is_dir() else None


def save_last_app(app_path: Path) -> None:
    file = workspace_root() / LAST_APP_FILE
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(str(app_path.resolve()), encoding="utf-8")


def desktop_dir() -> Path:
    """Desktop do usuário. No Windows pode estar redirecionado ao OneDrive;
    sem Desktop (servidor, WSL), cai na home."""
    home = Path.home()
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    candidates = ([Path(onedrive) / "Desktop"] if onedrive else []) + [home / "Desktop"]
    return next((d for d in candidates if d.is_dir()), home)


def default_output(app_name: str, doc_type: str, fmt: str = "pdf") -> Path:
    return desktop_dir() / f"{app_name}-{doc_type}.{fmt}"


def normalize_output(raw: str, app_name: str, doc_type: str,
                     fmt: str = "pdf") -> Path:
    """Tolerante: diretório -> salva dentro; extensão errada ou ausente ->
    troca pela do formato pedido."""
    ends_with_sep = raw.rstrip().endswith(("/", "\\"))
    path = parse_path(raw)
    if ends_with_sep or path.is_dir():
        return path / f"{app_name}-{doc_type}.{fmt}"
    if path.suffix.lower() != f".{fmt}":
        path = path.with_name(path.name + f".{fmt}")
    return path


def check_doc_type(doc_type: str) -> str:
    if doc_type not in DOC_TYPES:
        raise ValueError(f"Tipo {doc_type!r} inválido. Use um de: {', '.join(DOC_TYPES)}.")
    return doc_type


def check_format(fmt: str) -> str:
    if fmt not in FORMATS:
        raise ValueError(f"Formato {fmt!r} inválido. Use um de: {', '.join(FORMATS)}.")
    return fmt


def app_dir(app_path: str | Path) -> Path:
    path = parse_path(str(app_path)).resolve()
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
    identity: Identity | None = None


def create_doc(app_path: Path, doc_type: str, overwrite: bool = False) -> CreateResult:
    """Cria o YAML inicial (fatos extraídos + trechos (TODO)) no workspace."""
    check_doc_type(doc_type)
    app_name = app_path.name
    dp = doc_path(app_name, doc_type)
    facts = extract_facts(app_path)
    identity = detect_identity(app_path) if doc_type == "slides" else None
    if dp.exists() and not overwrite:
        return CreateResult(dp, facts, None, count_todos_in_file(dp), created=False,
                            identity=identity)

    blocks = skeleton_blocks(facts, doc_type, identity)
    overrides: dict = {
        "cover": {"title": app_name},
        "header_left": f"{app_name} · Documentação",
        "footer_left": app_name,
    }
    if doc_type == "slides":
        overrides["cover"] = {"title": identity.title or app_name}
        overrides["header_left"] = identity.title or app_name
        overrides["header_right"] = "Identidade visual"
    colors = None
    brand_source = None
    if facts.stack.kind in ("frontend", "fullstack") or doc_type == "slides":
        colors = detect_brand(app_path)
        if colors:
            overrides["palette"] = colors.palette_overrides()
            brand_source = "; ".join(colors.sources)
    save_document(dp, blocks, doc_type, theme_overrides=overrides,
                  app_kind=facts.stack.kind, brand_source=brand_source,
                  app_path=str(app_path) if doc_type == "slides" else None)
    return CreateResult(dp, facts, colors, count_todos(blocks), created=True,
                        identity=identity)


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
          mark: str | None = None, fmt: str = "pdf") -> BuildResult:
    """Gera o documento a partir do YAML do workspace, no formato `fmt`
    (`pdf`, `docx` ou `pptx`). `mark` aplica a marca de classificação só
    nesta geração, sem alterar o YAML."""
    check_format(fmt)
    dp = doc_path(app_name, doc_type)
    if not dp.exists():
        raise FileNotFoundError(f"Sem documentação {doc_type!r} no cache para "
                                f"{app_name!r} ({dp}). Crie com create_doc primeiro.")
    blocks, theme, used_type = load_document(dp, type_override=doc_type)
    if mark:
        theme = dataclasses.replace(theme, classification=mark)
    if fmt in ("docx", "pptx"):
        # import tardio: só quem exporta Office paga o custo do python-docx
        from .office import build_docx, build_pptx
        if fmt == "docx":
            out = build_docx(blocks, output, theme)
        else:
            out = build_pptx(blocks, output, theme, cover_logo=_cover_logo(blocks))
    elif used_type == "slides":
        out = build_slides(blocks, output, theme, cover_logo=_cover_logo(blocks))
    else:
        out = build_pdf(blocks, output, theme)
    return BuildResult(out, len(blocks), used_type, theme)


def _cover_logo(blocks) -> str | None:
    """Caminho do primeiro bloco de logo, usado na capa do deck."""
    return next((b.content.get("path") for b in blocks
                 if b.type == "logo" and isinstance(b.content, dict)), None)
