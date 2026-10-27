"""Identidade visual de um app, lida dos arquivos (determinístico, sem IA).

Reúne o que um guia de marca precisa e que o repositório consegue provar:

  assets      arquivos de logotipo, símbolo, mascote, favicon e OG image
  colors      cores de marca e cores semânticas, com nome e arquivo de origem
  fonts       famílias tipográficas declaradas (next/font, @font-face, Tailwind)
  tokens      raio, espaçamento e sombra declarados como variáveis
  missing     o que um app publicado costuma ter e aqui falta

Nada é inventado: cada item carrega a origem (`arquivo: variável`). O que
depende de decisão humana (posicionamento, tom de voz, usos indevidos) sai do
guia como (TODO).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .brand import BRAND_NAME, css_variables, to_hex
from .textio import read_text

MAX_READ = 512 * 1024

ASSET_DIRS = ("public", "static", "assets", "www", "resources", "media",
              "images", "img", "src/assets", "src/images", "src/img",
              "app", "src/app", "web", "dist/assets")
ASSET_SUFFIXES = {".svg", ".png", ".webp", ".ico", ".jpg", ".jpeg"}
IGNORED_DIRS = {"node_modules", ".git", ".next", "dist", "build", "out"}

# nome do arquivo -> papel do asset, na ordem de especificidade
ASSET_ROLES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"opengraph|og[-_]?image|twitter[-_]?image", re.I), "OG image"),
    (re.compile(r"apple[-_]?(touch[-_]?)?icon", re.I), "ícone iOS"),
    (re.compile(r"favicon", re.I), "favicon"),
    (re.compile(r"mascot|mascote", re.I), "mascote"),
    (re.compile(r"wordmark|lettering", re.I), "wordmark"),
    (re.compile(r"logo|assinatura|lockup", re.I), "logotipo"),
    (re.compile(r"icon|symbol|simbolo|símbolo|mark|brand", re.I), "símbolo"),
]
ASSET_HINT = re.compile(r"logo|icon|symbol|simbolo|símbolo|mark|brand|favicon|"
                        r"mascot|mascote|wordmark|lockup|assinatura|opengraph|"
                        r"og[-_]?image|apple[-_]?touch", re.I)
ON_SURFACE = re.compile(r"on[-_]?(light|dark)|(light|dark)[-_]?(bg|mode)", re.I)
# Pastas e nomes que parecem marca mas não são: conjuntos de ícones e fontes.
NOT_BRAND = re.compile(r"(^|/)(fonts?|icons?|iconfont)/|boxicons|fontawesome|"
                       r"fa-(brands|solid|regular)|materialdesignicons|dripicons|"
                       r"feather|remixicon|sprite", re.I)
# Formatos que o PDF consegue desenhar (o .ico fica na lista como fato, mas
# nunca é escolhido para desenhar).
RENDERABLE = {"svg", "png", "jpg", "jpeg"}

# Cores de componente: existem na UI, não na identidade da marca. A comparação
# é por segmento do nome, senão "spring-green" casaria com "ring".
COMPONENT_WORDS = {"sidebar", "chart", "card", "popover", "tooltip", "badge",
                   "button", "input", "ring", "border", "table", "menu",
                   "dialog", "toast", "scroll", "skeleton", "overlay"}


def _segments(name: str) -> list[str]:
    return re.split(r"[-_]", name.lstrip("-$@").lower())

# Cores semânticas: o conjunto que shadcn/Tailwind popularizou.
SEMANTIC_NAMES = ("background", "foreground", "card", "popover", "primary",
                  "secondary", "muted", "accent", "destructive", "success",
                  "warning", "info", "border", "input", "ring")

TOKEN_GROUPS: list[tuple[str, re.Pattern]] = [
    ("Raio", re.compile(r"^--(radius|rounded)", re.I)),
    ("Espaçamento", re.compile(r"^--(spacing|space|gap)", re.I)),
    ("Sombra", re.compile(r"^--(shadow|elevation)", re.I)),
]

_NEXT_FONT = re.compile(r"from\s+[\"']next/font/(google|local)[\"']")
_NEXT_FONT_IMPORT = re.compile(r"import\s*\{([^}]+)\}\s*from\s*[\"']next/font/google[\"']")
_FONT_CALL = re.compile(r"\b([A-Z]\w*(?:_\w+)*)\s*\(\s*\{(.*?)\}\s*\)", re.S)
_VARIABLE = re.compile(r"""variable\s*:\s*["'](--[\w-]+)["']""")
_WEIGHTS = re.compile(r"""weight\s*:\s*\[([^\]]*)\]""")
_FONT_FACE = re.compile(r"@font-face\s*\{[^}]*?font-family\s*:\s*['\"]?([^;'\"}]+)",
                        re.S | re.I)
_TW_FAMILY = re.compile(r"""fontFamily\s*:\s*\{(.*?)\}""", re.S)
_TW_ENTRY = re.compile(r"""(\w+)\s*:\s*\[\s*["']([^"']+)["']""")
_CSS_FONT_VAR = re.compile(r"^(?:--|\$|@)font[-_]?(?:family[-_]?)?([\w-]*)")
# tokens de fonte que não são família: tamanho, peso, altura de linha...
_NOT_FAMILY = re.compile(r"size|weight|style|line|letter|spacing|smooth|feature",
                         re.I)


@dataclass
class Asset:
    """Arquivo de marca encontrado no repositório."""
    path: str                 # relativo à pasta do app, com barra normal
    role: str                 # logotipo, símbolo, mascote, favicon, OG image
    format: str               # svg, png, ico...
    size: str                 # "734 × 360" ou "—"
    surface: str | None = None  # "light" ou "dark", quando o nome diz
    ratio: float | None = None  # largura / altura, quando medida

    @property
    def is_vector(self) -> bool:
        return self.format == "svg"

    @property
    def renderable(self) -> bool:
        return self.format in RENDERABLE

    @property
    def square(self) -> bool:
        return self.ratio is not None and 0.8 <= self.ratio <= 1.25


@dataclass
class NamedColor:
    name: str                 # "--color-brand-green"
    hex: str                  # "#00664E"
    source: str               # "src/app/globals.css"


@dataclass
class FontSpec:
    name: str                 # "Space Grotesk"
    role: str                 # sans, mono, heading
    source: str               # "src/app/layout.tsx: next/font/google"
    weights: str = ""         # "400, 500"


@dataclass
class CopySource:
    """Arquivo com texto de interface, e algumas frases de amostra.

    É a evidência de tom de voz que existe num repositório: o que o produto
    diz ao usuário. Quem escreve a seção lê estes arquivos.
    """
    path: str
    strings: int
    samples: list[str] = field(default_factory=list)


@dataclass
class Identity:
    assets: list[Asset] = field(default_factory=list)
    brand_colors: list[NamedColor] = field(default_factory=list)
    semantic_colors: list[NamedColor] = field(default_factory=list)
    fonts: list[FontSpec] = field(default_factory=list)
    tokens: list[tuple[str, str, str]] = field(default_factory=list)  # grupo, nome, valor
    missing: list[str] = field(default_factory=list)
    # arquivos com mais texto de interface: é onde o tom de voz está escrito
    ui_copy: list[CopySource] = field(default_factory=list)
    # metadados declarados no app (título, descrição, idioma), com a origem
    title: str | None = None
    description: str | None = None
    lang: str | None = None
    meta: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.assets or self.brand_colors or self.fonts)

    def by_role(self, *roles: str) -> list[Asset]:
        return [a for a in self.assets if a.role in roles]

    def signature(self) -> Asset | None:
        """Melhor arquivo para a assinatura da marca: logotipo horizontal em
        vetor, se houver; senão o símbolo. Formatos que o PDF não desenha
        (como .ico) ficam de fora."""
        usable = [a for a in self.assets if a.renderable]
        for roles in (("logotipo",), ("wordmark",), ("imagem de marca",),
                      ("símbolo",)):
            found = [a for a in usable if a.role in roles]
            wide = [a for a in found if a.ratio and a.ratio >= 1.6]
            vector = [a for a in (wide or found) if a.is_vector]
            if vector or wide or found:
                return (vector or wide or found)[0]
        return usable[0] if usable else None

    def symbol(self) -> Asset | None:
        """Símbolo isolado, de preferência quadrado: é ele que define o H da
        área de proteção."""
        usable = [a for a in self.assets
                  if a.renderable and a.role in ("símbolo", "ícone iOS",
                                                 "imagem de marca")]
        square = [a for a in usable if a.square and not a.surface]
        vector = [a for a in (square or usable) if a.is_vector]
        return (vector or square or usable or [None])[0]


def detect_identity(app_path: Path) -> Identity:
    identity = Identity()
    _read_assets(app_path, identity)
    _read_colors(app_path, identity)
    _read_fonts(app_path, identity)
    _read_metadata(app_path, identity)
    _read_ui_copy(app_path, identity)
    _check_missing(app_path, identity)
    return identity


# --- texto de interface ----------------------------------------------------

COPY_SUFFIXES = {".tsx", ".jsx", ".vue", ".svelte", ".html", ".ts", ".js"}
_QUOTED = re.compile(r"""["'`]([^"'`\n]{8,140})["'`]""")
_TWO_WORDS = re.compile(r"[A-Za-zÀ-ÿ]{3,}[\s,][A-Za-zÀ-ÿ]{2,}")
_NOT_COPY = re.compile(r"[/{}<>=;#$]|\|\||::|=>|\b(px|rem|vh|vw|flex|grid|rounded|"
                       r"font-|text-|bg-|w-|h-|p[xytblr]?-|m[xytblr]?-|gap-|"
                       r"border|shadow|hover|focus|dark|utf-8|https?)\b", re.I)
_DIRECTIVES = {"use client", "use server", "use strict"}


def _read_ui_copy(app: Path, identity: Identity, limit: int = 6,
                  per_file: int = 4) -> None:
    from .extract import source_files   # mesma varredura de arquivos de código

    found: list[CopySource] = []
    for path in source_files(app):
        if path.suffix.lower() not in COPY_SUFFIXES:
            continue
        text = read_text(path, MAX_READ)
        if not text:
            continue
        phrases = [s for s in (m.group(1).strip() for m in _QUOTED.finditer(text))
                   if _is_copy(s)]
        if len(phrases) >= 3:
            found.append(CopySource(path=path.relative_to(app).as_posix(),
                                    strings=len(phrases),
                                    samples=_unique(phrases)[:per_file]))
    found.sort(key=lambda c: -c.strings)
    identity.ui_copy = found[:limit]


def _is_copy(text: str) -> bool:
    """Frase dita ao usuário, não classe de CSS, caminho nem diretiva."""
    return (text.lower() not in _DIRECTIVES and bool(_TWO_WORDS.search(text))
            and not _NOT_COPY.search(text))


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


# --- metadados do app ------------------------------------------------------
#
# Cada framework declara nome, descrição e idioma num lugar diferente. A ordem
# aqui é da fonte mais específica para a mais genérica; o primeiro arquivo que
# responde cada campo vence, e a origem de cada valor vai para o documento.

_META_FILES = (
    "src/app/layout.tsx", "app/layout.tsx", "src/app/layout.jsx", "app/layout.jsx",
    "index.html", "public/index.html", "src/index.html", "app/index.html",
    "public/manifest.json", "public/site.webmanifest", "public/manifest.webmanifest",
    "static/manifest.json", "app.json", "pubspec.yaml", "package.json",
)
_META_LABELS = {"title": "Título do app", "template": "Template de título",
                "description": "Descrição", "lang": "Idioma declarado",
                "name": "Nome declarado", "short_name": "Nome curto"}


def _read_metadata(app: Path, identity: Identity) -> None:
    """Título, descrição e idioma declarados pelo app, em qualquer stack.

    A descrição costuma ser a definição de produto mais curta que existe no
    código, e é o melhor ponto de partida do posicionamento.
    """
    seen: set[str] = set()
    for rel in _META_FILES:
        text = read_text(app / rel, MAX_READ)
        if not text:
            continue
        if rel.endswith((".tsx", ".jsx")):
            found = _meta_from_jsx(text)
        elif rel.endswith(".html"):
            found = _meta_from_html(text)
        elif rel.endswith(".yaml"):
            found = _meta_from_yaml(text)
        else:
            found = _meta_from_json(text)
        for key, value in found.items():
            value = " ".join(str(value).split())
            if not value or key in seen:
                continue
            seen.add(key)
            identity.meta.append((_META_LABELS.get(key, key), value, rel))
            if key in ("title", "name", "short_name") and not identity.title:
                identity.title = value
            elif key == "description" and not identity.description:
                identity.description = value
            elif key == "lang" and not identity.lang:
                identity.lang = value


def _meta_from_jsx(text: str) -> dict[str, str]:
    """Metadados do Next (`export const metadata = {...}`) e o lang do <html>."""
    if "metadata" not in text and "<html" not in text:
        return {}
    out = {}
    for key, pattern in (
            ("title", r"""default\s*:\s*["'](.+?)["']"""),
            ("title", r"""title\s*:\s*["'](.+?)["']"""),
            ("template", r"""template\s*:\s*["'](.+?)["']"""),
            ("description", r"""description\s*:\s*["'](.+?)["']"""),
            ("lang", r"""<html[^>]*\blang=["']([\w-]+)["']"""),
    ):
        found = re.search(pattern, text)
        if found and key not in out:
            out[key] = found.group(1)
    return out


def _meta_from_html(text: str) -> dict[str, str]:
    out = {}
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    if title:
        out["title"] = re.sub(r"\s+", " ", title.group(1)).strip()
    desc = re.search(r"""<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)""",
                     text, re.I)
    if desc:
        out["description"] = desc.group(1)
    lang = re.search(r"""<html[^>]*\blang=["']([\w-]+)["']""", text, re.I)
    if lang:
        out["lang"] = lang.group(1)
    return out


def _meta_from_json(text: str) -> dict[str, str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    data = data.get("expo", data) if isinstance(data.get("expo"), dict) else data
    out = {}
    for key in ("name", "short_name", "description", "lang"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            out[key] = value.strip()
    return out


def _meta_from_yaml(text: str) -> dict[str, str]:
    """pubspec.yaml (Flutter) e afins: name e description no topo do arquivo."""
    out = {}
    for key in ("name", "description"):
        found = re.search(rf"^{key}\s*:\s*(.+)$", text, re.M)
        if found:
            out[key] = found.group(1).strip().strip("\"'")
    return out


# --- assets ----------------------------------------------------------------

def _read_assets(app: Path, identity: Identity, limit: int = 40) -> None:
    seen: set[str] = set()
    for base in ASSET_DIRS:
        root = app / base
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(app).as_posix()
            if (len(identity.assets) >= limit or rel in seen
                    or not path.is_file()
                    or path.suffix.lower() not in ASSET_SUFFIXES
                    or any(part in IGNORED_DIRS for part in path.parts)
                    or NOT_BRAND.search(rel)
                    or not ASSET_HINT.search(rel)):
                continue
            seen.add(rel)
            width, height = _dimensions(path)
            ratio = (width / height) if width and height else None
            # o papel vem do nome do arquivo; se o nome não diz (o caso de
            # "on-dark.svg" numa pasta Brand/), a proporção decide
            role = next((r for pattern, r in ASSET_ROLES
                         if pattern.search(path.stem)), None)
            if role is None:
                role = ("logotipo" if ratio and ratio >= 1.6 else
                        "símbolo" if ratio and 0.8 <= ratio <= 1.25 else
                        "imagem de marca")
            surface = ON_SURFACE.search(path.stem)
            identity.assets.append(Asset(
                path=rel, role=role, format=path.suffix.lower().lstrip("."),
                size=_size_label(path, width, height), ratio=ratio,
                surface=(surface.group(1) or surface.group(2)).lower()
                if surface else None))
    # vetor antes de bitmap, e o papel mais específico antes
    order = {role: i for i, (_, role) in enumerate(ASSET_ROLES)}
    identity.assets.sort(key=lambda a: (order.get(a.role, 99), not a.is_vector,
                                        bool(a.surface), a.path))


def _dimensions(path: Path) -> tuple[float | None, float | None]:
    """Largura e altura do arquivo, sem depender de biblioteca de imagem."""
    suffix = path.suffix.lower()
    if suffix == ".svg":
        head = (read_text(path, MAX_READ) or "")[:2000]
        w = re.search(r"\bwidth=[\"']([\d.]+)", head)
        h = re.search(r"\bheight=[\"']([\d.]+)", head)
        if w and h:
            return float(w.group(1)), float(h.group(1))
        box = re.search(r"viewBox=[\"'][\d.\-\s]*?([\d.]+)[\s,]+([\d.]+)[\"']", head)
        if box:
            return float(box.group(1)), float(box.group(2))
    elif suffix == ".png":
        try:
            header = path.read_bytes()[:26]
        except OSError:
            return None, None
        if header[:8] == b"\x89PNG\r\n\x1a\n":
            return (float(int.from_bytes(header[16:20], "big")),
                    float(int.from_bytes(header[20:24], "big")))
    return None, None


def _size_label(path: Path, width: float | None, height: float | None) -> str:
    if width and height:
        return f"{_num(width)} × {_num(height)}"
    return "vetor" if path.suffix.lower() == ".svg" else "—"


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


# --- cores -----------------------------------------------------------------

def _read_colors(app: Path, identity: Identity, limit: int = 14) -> None:
    variables = css_variables(app)
    brand: list[NamedColor] = []
    semantic: list[NamedColor] = []
    for var in variables:
        if var.color is None:
            group = next((g for g, pattern in TOKEN_GROUPS
                          if pattern.match(var.name)), None)
            if group and len(identity.tokens) < 18:
                identity.tokens.append((group, var.name, var.raw))
            continue
        named = NamedColor(name=var.name, hex=to_hex(var.color), source=var.source)
        words = _segments(var.name)
        plain = "-".join(words)
        is_component = bool(COMPONENT_WORDS & set(words))
        if (BRAND_NAME.search(var.name) and not is_component
                and not plain.endswith("foreground")):
            brand.append(named)
        elif plain in SEMANTIC_NAMES or words[0] in SEMANTIC_NAMES:
            semantic.append(named)
    # Com um namespace de marca explícito (--color-brand-*), ele manda: os
    # nomes genéricos (primary, accent) são decisão de UI, não de identidade.
    explicit = [c for c in brand if "brand" in _segments(c.name)]
    identity.brand_colors = _dedupe_colors(explicit or brand)[:limit]
    identity.semantic_colors = _dedupe_colors(
        semantic + ([c for c in brand if c not in explicit] if explicit else []))[:limit]
    identity.brand_colors.sort(key=lambda c: _luma(c.hex))


def _luma(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
    identity.brand_colors = _dedupe_colors(brand)[:limit]
    identity.semantic_colors = _dedupe_colors(semantic)[:limit]


def _dedupe_colors(colors: list[NamedColor]) -> list[NamedColor]:
    """Um nome por cor: a mesma cor declarada duas vezes aparece uma vez."""
    seen: set[str] = set()
    out = []
    for color in colors:
        if color.hex in seen:
            continue
        seen.add(color.hex)
        out.append(color)
    return out


# --- tipografia ------------------------------------------------------------

def _read_fonts(app: Path, identity: Identity) -> None:
    for rel in ("src/app/layout.tsx", "app/layout.tsx", "src/app/layout.jsx",
                "app/layout.jsx", "src/main.tsx", "src/App.tsx"):
        text = read_text(app / rel, MAX_READ)
        if text and _NEXT_FONT.search(text):
            _from_next_font(rel, text, identity)
            break

    # <link href="...fonts.googleapis.com/css2?family=Inter:wght@400;700">
    for rel in ("index.html", "public/index.html", "src/index.html"):
        text = read_text(app / rel, MAX_READ)
        if not text:
            continue
        for href in re.findall(r"""fonts\.googleapis\.com[^"'>]+""", text):
            for family in re.findall(r"family=([^&:\"']+)", href):
                _add_font(identity, family.replace("+", " "), "sans",
                          f"{rel}: Google Fonts")

    for cfg in ("tailwind.config.ts", "tailwind.config.js", "tailwind.config.mjs"):
        text = read_text(app / cfg, MAX_READ)
        if not text:
            continue
        family = _TW_FAMILY.search(text)
        if family:
            for role, name in _TW_ENTRY.findall(family.group(1)):
                _add_font(identity, name, role, f"{cfg}: fontFamily.{role}")

    for var in css_variables(app):
        if var.color is not None:
            continue
        role = _CSS_FONT_VAR.match(var.name)
        # --font-size, $font-weight e afins não são família tipográfica
        if not role or _NOT_FAMILY.search(var.name):
            continue
        name = re.split(r",", var.raw)[0].strip().strip("\"'")
        if name and not name.startswith("var("):
            _add_font(identity, name, role.group(1) or "sans",
                      f"{var.source}: {var.name}")

    for css in _style_files(app):
        text = read_text(css, MAX_READ)
        if not text:
            continue
        rel = css.relative_to(app).as_posix()
        for name in _FONT_FACE.findall(text):
            _add_font(identity, name.strip(), "declarada", f"{rel}: @font-face")
        # font-family declarada direto (CSS, Sass, Less, sem variável)
        for value in re.findall(r"font-family\s*:\s*([^;}\n]+)", text, re.I)[:6]:
            first = re.split(r",", value)[0].strip().strip("\"'")
            if first and not first.startswith(("var(", "$", "@", "inherit")):
                role = "mono" if "mono" in value.lower() else "sans"
                _add_font(identity, first, role, f"{rel}: font-family")


def _style_files(app: Path, limit: int = 6) -> list[Path]:
    """Folhas de estilo mais prováveis de declarar a tipografia."""
    names = ("globals.css", "global.css", "index.css", "main.css", "app.css",
             "style.css", "styles.css", "main.scss", "style.scss")
    found = []
    for base in (app, app / "src", app / "src" / "app", app / "app",
                 app / "src" / "styles", app / "styles", app / "assets" / "css"):
        for name in names:
            path = base / name
            if path.is_file() and path not in found:
                found.append(path)
    return found[:limit]


def _from_next_font(rel: str, text: str, identity: Identity) -> None:
    """Fontes do `next/font/google`: o nome vem do import (Space_Grotesk) e o
    papel, da variável CSS declarada na chamada (--font-sans)."""
    imported = set()
    for group in _NEXT_FONT_IMPORT.findall(text):
        imported |= {name.strip() for name in group.split(",") if name.strip()}
    for name, args in _FONT_CALL.findall(text):
        if name not in imported:
            continue
        variable = _VARIABLE.search(args)
        role = "sans"
        if variable:
            found = _CSS_FONT_VAR.match(variable.group(1))
            role = (found.group(1) if found and found.group(1) else "sans")
        weights = _WEIGHTS.search(args)
        _add_font(identity, name.replace("_", " "), role,
                  f"{rel}: next/font/google",
                  ", ".join(w.strip().strip("\"'")
                            for w in weights.group(1).split(",") if w.strip())
                  if weights else "")


def _add_font(identity: Identity, name: str, role: str, source: str,
              weights: str = "") -> None:
    name = name.strip().strip("\"'")
    # família tem nome; valor numérico, null ou palavra-chave do CSS, não
    if (not name or not re.match(r"[A-Za-zÀ-ÿ]", name)
            or name.lower() in ("inherit", "initial", "unset", "null", "none",
                                "revert", "auto", "normal")):
        return
    role = role.lower()
    role = ("mono" if "mono" in role else
            "títulos" if re.search(r"head|display|title", role) else
            "sans" if role in ("", "sans", "body", "base", "default", "primary",
                               "declarada", "regular") or "sans" in role
            else role)
    for font in identity.fonts:
        if font.name.lower() == name.lower():
            if weights and not font.weights:
                font.weights = weights
            return
    identity.fonts.append(FontSpec(name=name, role=role, source=source,
                                   weights=weights))


# --- o que falta -----------------------------------------------------------

def _check_missing(app: Path, identity: Identity) -> None:
    roles = {a.role for a in identity.assets}
    checks = (
        ("favicon", "favicon (favicon.ico ou icon.svg)"),
        ("OG image", "OG image (opengraph-image, para link compartilhado)"),
        ("ícone iOS", "ícone iOS (apple-icon/apple-touch-icon)"),
    )
    for role, label in checks:
        if role not in roles:
            identity.missing.append(label)
    if not any(a.is_vector for a in identity.assets):
        identity.missing.append("versão vetorial (SVG) da marca: só há bitmap")
    if not identity.fonts:
        identity.missing.append("fonte declarada no código (next/font, @font-face "
                                "ou fontFamily do Tailwind)")
