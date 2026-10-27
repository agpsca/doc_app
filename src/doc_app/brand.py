"""Detecção das cores de marca de um frontend (determinística, sem IA).

Lê as variáveis CSS do próprio app (ex.: `--primary`, `--color-brand-*`), o
`tailwind.config` e o manifest, e monta uma paleta para o PDF:

  brand   cor principal: títulos e links. Precisa ser legível sobre branco.
  dark    versão escura: fundo da capa e cabeçalho das tabelas.
  accent  destaque: réguas, barras e título da capa. Precisa aparecer sobre `dark`.

As demais cores (fundos claros, linhas, textos de apoio) são derivadas dessas
três. Nenhuma marca fica no código do doc_app: o resultado é gravado só no
YAML do workspace, e o usuário pode ajustar lá.

Formatos de cor entendidos: #rgb, #rrggbb(aa), rgb()/rgba(), hsl()/hsla(),
tripla HSL "H S% L%" (shadcn v3), oklch(), var(--x) e color-mix().
Valores definidos dentro de seletores de tema escuro (.dark, [data-theme=dark],
@media (prefers-color-scheme: dark)) são ignorados.
"""

from __future__ import annotations

import colorsys
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from .textio import read_text

RGB = tuple[int, int, int]

MAX_READ = 512 * 1024
IGNORED_DIRS = {"node_modules", ".git", ".next", ".nuxt", "dist", "build", "out",
                "coverage", ".turbo", ".cache", "storybook-static"}

CSS_CANDIDATES = [
    "src/app/globals.css", "app/globals.css", "src/styles/globals.css",
    "styles/globals.css", "src/index.css", "src/main.css", "src/App.css",
    "src/styles.css", "src/style.css", "src/assets/main.css",
    "src/styles/index.css", "src/app.css", "assets/css/main.css",
]
TAILWIND_CONFIGS = ["tailwind.config.ts", "tailwind.config.js",
                    "tailwind.config.mjs", "tailwind.config.cjs"]
MANIFESTS = ["public/manifest.json", "public/site.webmanifest",
             "public/manifest.webmanifest", "static/manifest.json"]

BRAND_NAME = re.compile(r"brand|primary|accent|highlight|theme-color|main", re.I)
PRIMARY_NAMES = ["--primary", "--color-primary", "--brand", "--color-brand",
                 "--brand-primary", "--color-brand-primary", "--primary-color",
                 "--main-color", "$primary", "$brand-primary", "$brand",
                 "$color-primary", "@primary", "@brand-primary", "@primary-color"]
DARK_SELECTOR = re.compile(r"\.dark\b|dark\]|theme=.?dark|prefers-color-scheme:\s*dark",
                           re.I)

WHITE: RGB = (255, 255, 255)
BLACK: RGB = (0, 0, 0)


@dataclass
class CssVar:
    """Variável de estilo declarada no app (cor ou outro token)."""
    name: str
    raw: str
    source: str
    color: RGB | None = None


@dataclass
class BrandColors:
    brand: RGB
    dark: RGB
    accent: RGB
    sources: list[str] = field(default_factory=list)  # "arquivo: --var"

    def palette_overrides(self) -> dict[str, str]:
        """Cores no formato do YAML (`theme: palette:`), em #RRGGBB."""
        b, d, a = self.brand, self.dark, self.accent
        colors = {
            "brand": b,
            "link": b,
            "dark": d,
            "accent": a,
            "callout_bg": mix(a, WHITE, 0.10),
            "code_bg": mix(d, WHITE, 0.04),
            "zebra": mix(d, WHITE, 0.025),
            "rule": mix(d, WHITE, 0.13),
            "cover_text": mix(WHITE, d, 0.85),   # 85% branco: legível sobre `dark`
            "cover_muted": mix(WHITE, d, 0.60),
        }
        return {k: to_hex(v) for k, v in colors.items()}


def css_variables(app_path: Path) -> list[CssVar]:
    """Variáveis declaradas nos estilos do app, na ordem dos arquivos mais
    prováveis de definirem a marca. A primeira definição de cada nome vence.

    Usada pelo guia de identidade visual: além das cores, interessam os tokens
    de raio, espaçamento e fonte, que não são cor nenhuma.
    """
    out: list[CssVar] = []
    seen: set[str] = set()
    for css in _css_files(app_path):
        text = _read(css)
        if not text:
            continue
        rel = css.relative_to(app_path).as_posix()
        variables = _light_variables(text)
        for name, raw in variables.items():
            if name in seen:
                continue
            seen.add(name)
            out.append(CssVar(name=name, raw=raw, source=rel,
                              color=_resolve(name, variables, set())))
    return out


def detect_brand(app_path: Path) -> BrandColors | None:
    """Procura cores de marca no app. Devolve None se não achar nada confiável."""
    candidates: list[tuple[str, RGB, str]] = []   # (nome, cor, origem)
    primary: tuple[RGB, str] | None = None

    for css in _css_files(app_path):
        text = _read(css)
        if not text:
            continue
        rel = str(css.relative_to(app_path))
        variables = _light_variables(text)
        resolved = {name: _resolve(name, variables, set()) for name in variables}
        for name in PRIMARY_NAMES:
            if primary is None and resolved.get(name):
                primary = (resolved[name], f"{rel}: {name}")
        for name, color in resolved.items():
            if color and BRAND_NAME.search(name):
                candidates.append((name, color, f"{rel}: {name}"))

    for cfg in TAILWIND_CONFIGS:
        text = _read(app_path / cfg)
        if text:
            for name, color in _tailwind_colors(text):
                candidates.append((name, color, f"{cfg}: {name}"))
                if primary is None and name in ("primary", "brand"):
                    primary = (color, f"{cfg}: {name}")

    for man in MANIFESTS:
        data = _read(app_path / man)
        if data:
            try:
                theme_color = json.loads(data).get("theme_color")
            except (json.JSONDecodeError, AttributeError):
                theme_color = None
            color = parse_color(theme_color) if isinstance(theme_color, str) else None
            if color:
                candidates.append(("theme_color", color, f"{man}: theme_color"))

    vivid = [c for c in candidates if _chroma(c[1]) >= 40]
    if primary is None and not vivid:
        return None
    # Cores escuras de marca costumam ser pouco saturadas: entram com um
    # filtro mais brando, só para excluir cinzas puros e preto.
    tinted_darks = [(c, src) for _, c, src in candidates
                    if luminance(c) < 0.06 and _chroma(c) >= 15]
    return _pick(primary, vivid, tinted_darks)


# --- escolha das três cores -------------------------------------------------

def _pick(primary: tuple[RGB, str] | None,
          vivid: list[tuple[str, RGB, str]],
          tinted_darks: list[tuple[RGB, str]]) -> BrandColors:
    sources: list[str] = []
    pool = [(c, src) for _, c, src in vivid]
    if primary and _chroma(primary[0]) >= 25:
        pool.insert(0, primary)

    # brand: a primeira cor legível sobre branco (contraste >= 4.5); se nenhuma
    # for, escurece a mais forte até ficar legível.
    brand_src = next(((c, s) for c, s in pool if contrast(c, WHITE) >= 4.5), None)
    if brand_src is None:
        base = pool[0] if pool else (primary or ((51, 78, 104), "padrão"))
        brand_src = (_darken_until(base[0], WHITE, 4.5), base[1] + " (escurecida)")
    brand, src = brand_src
    sources.append(f"principal: {src}")

    # dark: a cor de marca mais escura (luminância < 0.06); senão, deriva.
    darks = [(c, s) for c, s in pool if luminance(c) < 0.06] + tinted_darks
    if darks:
        dark, src = min(darks, key=lambda cs: luminance(cs[0]))
        sources.append(f"escura: {src}")
    else:
        dark = mix(brand, BLACK, 0.45)
        sources.append("escura: derivada da principal")

    # accent: a cor mais viva, diferente da principal, que apareça sobre a escura.
    accents = [(c, s) for c, s in pool
               if c != brand and contrast(c, dark) >= 3.0 and _chroma(c) >= 60]
    if accents:
        accent, src = max(accents, key=lambda cs: (_chroma(cs[0]), luminance(cs[0])))
        sources.append(f"destaque: {src}")
    else:
        accent = _lighten_until(brand, dark, 3.0)
        sources.append("destaque: derivado da principal")

    return BrandColors(brand=brand, dark=dark, accent=accent, sources=sources)


def _darken_until(c: RGB, bg: RGB, ratio: float) -> RGB:
    for t in range(1, 21):
        cand = mix(c, BLACK, 1 - t * 0.05)
        if contrast(cand, bg) >= ratio:
            return cand
    return mix(c, BLACK, 0.2)


def _lighten_until(c: RGB, bg: RGB, ratio: float) -> RGB:
    for t in range(1, 21):
        cand = mix(c, WHITE, 1 - t * 0.05)
        if contrast(cand, bg) >= ratio:
            return cand
    return mix(c, WHITE, 0.4)


# --- leitura de CSS ---------------------------------------------------------

def _read(path: Path) -> str | None:
    return read_text(path, MAX_READ)


STYLE_HINT = re.compile(r"variables|theme|tokens|colou?rs|palette|brand", re.I)


def _css_files(app: Path, limit: int = 30) -> list[Path]:
    """Arquivos de estilo do app (CSS, SCSS, Sass, Less), dos mais prováveis de
    definir a marca (variables, theme, tokens...) para os menos."""
    found = [app / c for c in CSS_CANDIDATES if (app / c).is_file()]
    others: list[Path] = []
    for base in (app / "src", app / "app", app / "styles", app / "assets"):
        if not base.is_dir():
            continue
        for ext in ("*.css", "*.scss", "*.sass", "*.less"):
            for f in base.rglob(ext):
                if any(part in IGNORED_DIRS for part in f.relative_to(app).parts):
                    continue
                if f not in found and f not in others:
                    others.append(f)
    others.sort(key=lambda f: (not STYLE_HINT.search(f.name), len(f.parts), str(f)))
    return (found + others)[:limit]


def _light_variables(css: str) -> dict[str, str]:
    """Variáveis de cor fora de seletores de tema escuro.

    Entende propriedades CSS (`--x: valor`) e variáveis de Sass (`$x: valor`)
    e Less (`@x: valor`). Percorre o arquivo acompanhando a pilha de seletores
    pelas chaves; a primeira definição de cada variável vence.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"(^|[\s;{}])//[^\n]*", r"\1", css)  # comentários de linha (Sass/Less)
    variables: dict[str, str] = {}
    stack: list[str] = []
    buf = ""
    for ch in css:
        if ch == "{":
            stack.append(buf.strip())
            buf = ""
        elif ch == "}":
            _collect(buf, stack, variables)
            buf = ""
            if stack:
                stack.pop()
        elif ch == ";":
            _collect(buf, stack, variables)
            buf = ""
        else:
            buf += ch
    return variables


def _collect(decl: str, stack: list[str], out: dict[str, str]) -> None:
    m = re.match(r"\s*((?:--|\$|@)[\w-]+)\s*:\s*(.+)", decl, re.S)
    if not m or any(DARK_SELECTOR.search(sel) for sel in stack):
        return
    name, value = m.group(1), " ".join(m.group(2).split())
    value = re.sub(r"\s*!(default|global)\s*$", "", value)
    out.setdefault(name, value)


def _resolve(name: str, variables: dict[str, str], seen: set[str]) -> RGB | None:
    if name in seen or name not in variables:
        return None
    seen = seen | {name}
    return _eval(variables[name], variables, seen)


def _eval(value: str, variables: dict[str, str], seen: set[str]) -> RGB | None:
    value = value.strip().removesuffix("!important").strip()
    if re.fullmatch(r"[$@][\w-]+", value):      # referência Sass/Less
        return _resolve(value, variables, seen)
    m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*(?:,\s*(.+))?\)", value)
    if m:
        got = _resolve(m.group(1), variables, seen)
        if got is None and m.group(2):
            got = _eval(m.group(2), variables, seen)
        return got
    if value.startswith("color-mix("):
        return _color_mix(value, variables, seen)
    return parse_color(value)


def _color_mix(value: str, variables: dict[str, str], seen: set[str]) -> RGB | None:
    inner = value[len("color-mix("):-1]
    parts = _split_top(inner)
    if len(parts) != 3:
        return None
    (c1, p1), (c2, p2) = _mix_arg(parts[1]), _mix_arg(parts[2])
    if c2.strip() == "transparent":
        return _eval(c1, variables, seen)
    a, b = _eval(c1, variables, seen), _eval(c2, variables, seen)
    if a is None or b is None:
        return None
    if p1 is None and p2 is None:
        p1 = 0.5
    elif p1 is None:
        p1 = 1 - p2
    return mix(a, b, p1)


def _mix_arg(arg: str) -> tuple[str, float | None]:
    m = re.match(r"(.+?)\s+(\d+(?:\.\d+)?)%\s*$", arg.strip())
    return (m.group(1), float(m.group(2)) / 100) if m else (arg.strip(), None)


def _split_top(s: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def _tailwind_colors(text: str) -> list[tuple[str, RGB]]:
    """Cores com nome de marca no tailwind.config: `primary: '#...'` ou
    `brand: { DEFAULT: '#...' }`."""
    out = []
    for m in re.finditer(r"['\"]?(\w*(?:brand|primary|accent)\w*)['\"]?\s*:\s*"
                         r"(?:\{[^}]*?DEFAULT['\"]?\s*:\s*)?['\"](#[0-9a-fA-F]{3,8})['\"]",
                         text):
        color = parse_color(m.group(2))
        if color:
            out.append((m.group(1), color))
    return out


# --- cores ------------------------------------------------------------------

def parse_color(value: str) -> RGB | None:
    v = value.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3,8})", v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h[:3])
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) if len(h) >= 6 else None
    m = re.fullmatch(r"rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?).*\)", v)
    if m:
        return tuple(_channel(x) for x in m.groups())
    m = re.fullmatch(r"(?:hsla?\()?\s*([\d.]+)(?:deg)?[\s,]+([\d.]+)%[\s,]+([\d.]+)%"
                     r"(?:\s*[/,]\s*[\d.]+%?)?\s*\)?", v)
    if m:
        h, s, light = (float(x) for x in m.groups())
        r, g, b = colorsys.hls_to_rgb((h % 360) / 360, light / 100, s / 100)
        return _clamp((r * 255, g * 255, b * 255))
    m = re.fullmatch(r"oklch\(\s*([\d.]+)(%?)\s+([\d.]+)%?\s+([\d.]+)(?:deg)?"
                     r"(?:\s*/\s*[\d.]+%?)?\s*\)", v)
    if m:
        light = float(m.group(1)) / (100 if m.group(2) else 1)
        return _oklch_to_rgb(light, float(m.group(3)), float(m.group(4)))
    return None


def _channel(x: str) -> int:
    return round(float(x[:-1]) * 2.55) if x.endswith("%") else round(float(x))


def _oklch_to_rgb(L: float, C: float, H: float) -> RGB:
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)

    def gamma(x: float) -> float:
        x = min(max(x, 0.0), 1.0)
        return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055

    return _clamp(tuple(gamma(x) * 255 for x in lin))


def _clamp(c) -> RGB:
    return tuple(max(0, min(255, round(x))) for x in c)


def mix(a: RGB, b: RGB, weight_a: float) -> RGB:
    """Mistura `a` e `b`; `weight_a` é a proporção de `a` (0 a 1)."""
    return _clamp(tuple(x * weight_a + y * (1 - weight_a) for x, y in zip(a, b)))


def luminance(c: RGB) -> float:
    def lin(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: RGB, b: RGB) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _chroma(c: RGB) -> int:
    return max(c) - min(c)


def to_hex(c: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*c)
