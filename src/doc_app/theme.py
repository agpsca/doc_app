"""Tema visual do documento: cores, fontes e dimensões de página.

O padrão (`DEFAULT_THEME`) usa a identidade própria do doc_app: discreta, em
grafite e cinza-azulado. Nenhuma marca de app fica no código: as cores de um
frontend são detectadas no próprio app (`brand.py`) e gravadas só no YAML do
workspace.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Palette:
    """Cores usadas na renderização. Os valores padrão são os do doc_app."""

    dark: RGB = (31, 41, 51)  # #1F2933  fundo da capa, h2
    brand: RGB = (51, 78, 104)  # #334E68  h1, chaves, sumário
    accent: RGB = (130, 154, 177)  # #829AB1  réguas, barra de callout
    ink: RGB = (31, 41, 51)  # #1F2933  texto principal
    muted: RGB = (123, 135, 148)  # #7B8794  texto secundário
    rule: RGB = (228, 231, 235)  # #E4E7EB  linhas finas
    code_bg: RGB = (245, 247, 250)  # #F5F7FA  fundo de bloco de código
    callout_bg: RGB = (240, 244, 248)  # #F0F4F8
    code_fg: RGB = (50, 62, 72)  # #323E48
    zebra: RGB = (249, 250, 251)  # #F9FAFB  faixa alternada das tabelas
    link: RGB = (51, 78, 104)  # #334E68  URLs clicáveis
    cover_text: RGB = (203, 210, 217)  # #CBD2D9  linha de apoio da capa
    cover_muted: RGB = (154, 165, 177)  # #9AA5B1  rodapé da capa
    white: RGB = (255, 255, 255)


# --- fontes: resolvidas na plataforma em uso ------------------------------

# Trios de fontes (regular, negrito, mono) procurados em cada pasta. DejaVu é
# a preferida (cobre mais caracteres); no Windows, Arial + Consolas servem.
_DEJAVU = ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf")
_ARIAL = ("arial.ttf", "arialbd.ttf", "consola.ttf")


def _font_dirs() -> list[str]:
    home = os.path.expanduser("~")
    windir = os.environ.get("WINDIR", r"C:\Windows")
    return [
        "/usr/share/fonts/truetype/dejavu",  # Debian, Ubuntu, WSL
        "/usr/share/fonts/dejavu",  # Fedora, Arch
        "/usr/local/share/fonts",
        os.path.join(home, ".local", "share", "fonts"),
        os.path.join(home, "Library", "Fonts"),  # macOS
        "/Library/Fonts",
        os.path.join(windir, "Fonts"),  # Windows
        "/mnt/c/Windows/Fonts",  # WSL sem fontes Linux
    ]


def _resolve_fonts(dirs: list[str] | None = None) -> tuple[str, str, str, str]:
    """Primeira pasta com um trio completo: (dir, regular, negrito, mono).

    `DOC_APP_FONT_DIR` tem prioridade. Sem nenhum trio, devolve dir vazio e
    `Fonts.path` explica o que instalar.
    """
    dirs = dirs if dirs is not None else _font_dirs()
    env = os.environ.get("DOC_APP_FONT_DIR")
    for d in [env, *dirs] if env else dirs:
        for trio in (_DEJAVU, _ARIAL):
            if all(os.path.isfile(os.path.join(d, f)) for f in trio):
                return (d, *trio)
    return ("", *_DEJAVU)


_FONT_DIR, _SANS, _SANS_BOLD, _MONO = _resolve_fonts()


@dataclass(frozen=True)
class Fonts:
    """Fontes TrueType. `dir` é resolvido na plataforma em uso (`_resolve_fonts`)."""

    dir: str = _FONT_DIR
    sans_regular: str = _SANS
    sans_bold: str = _SANS_BOLD
    mono_regular: str = _MONO

    def path(self, filename: str) -> str:
        full = os.path.join(self.dir, filename) if self.dir else filename
        if not os.path.isfile(full):
            raise FileNotFoundError(
                f"fonte não encontrada: {full or filename}. Instale as fontes "
                "DejaVu (Ubuntu, Debian ou WSL: sudo apt install "
                "fonts-dejavu-core) ou aponte DOC_APP_FONT_DIR para uma pasta "
                "com DejaVuSans.ttf, DejaVuSans-Bold.ttf e DejaVuSansMono.ttf."
            )
        return full


@dataclass(frozen=True)
class Page:
    """Dimensões de página em mm (A4 por padrão)."""

    width: float = 210.0
    height: float = 297.0
    margin: float = 20.0

    @property
    def content_width(self) -> float:
        return self.width - 2 * self.margin


# Slide 16:9 no tamanho padrão de apresentação (33,87 × 19,05 cm).
SLIDE_PAGE = Page(width=338.67, height=190.5, margin=24.0)


@dataclass(frozen=True)
class Cover:
    """Textos da capa."""

    title: str = "App"
    subtitle: str = "Documentação"
    tagline: str = "Uso da aplicação e regras de arquitetura"
    footnote: str = "Gerado pelo doc_app a partir do código-fonte do repositório."


@dataclass(frozen=True)
class Typography:
    """Tamanhos e espaçamentos que diferenciam os tipos de documentação.

    A paleta é a mesma entre os tipos; o que muda é a densidade/tipografia.
    Valores em pt (fontes) e mm (espaçamentos/leading).
    """

    h1_size: float = 17.0
    h2_size: float = 13.0
    h3_size: float = 11.0
    body_size: float = 10.5
    body_leading: float = 5.6  # altura de linha do parágrafo
    list_size: float = 10.5  # corpo dos itens de lista, igual em todos os tipos
    mono_size: float = 9.0
    h1_gap_before: float = 7.0
    h2_gap_before: float = 5.0
    cover_big: bool = True  # capa original (brand/full) vs. variação (development)


@dataclass(frozen=True)
class Theme:
    """Tema completo: paleta, fontes, página, capa e textos de cabeçalho."""

    palette: Palette = field(default_factory=Palette)
    fonts: Fonts = field(default_factory=Fonts)
    page: Page = field(default_factory=Page)
    cover: Cover = field(default_factory=Cover)
    typography: Typography = field(default_factory=Typography)
    header_left: str = "Documentação"
    header_right: str = "Uso e regras"
    footer_left: str = "doc_app"
    # Pasta do app, para resolver os caminhos de imagem dos blocos de marca
    # (logo, clearspace). Preenchida pelo loader a partir do YAML.
    assets_root: str | None = None
    # Classificação do documento (ex.: "Uso interno", "Confidencial"). Quando
    # definida, gera marca d'água, selo na capa e aviso no rodapé.
    classification: str | None = None


# --- Tipos de documentação, mesma paleta -----------------------------------

# "brand": marca e regras. Editorial, títulos grandes, capa original.
BRAND_THEME = Theme(
    typography=Typography(),
    header_right="Uso e regras",
)

# "full": marca + código no mesmo PDF. Usa a tipografia editorial da brand.
FULL_THEME = Theme(
    typography=Typography(),
    cover=Cover(
        subtitle="Documentação completa",
        tagline="Uso, regras de arquitetura e referência de código",
    ),
    header_right="Uso, regras e código",
)

# "development": código. Técnica e compacta, variação da capa original.
DEVELOPMENT_THEME = Theme(
    typography=Typography(
        h1_size=15.0,
        h2_size=12.0,
        h3_size=10.5,
        body_size=10.0,
        body_leading=5.2,
        mono_size=9.0,
        h1_gap_before=5.0,
        h2_gap_before=3.5,
        cover_big=False,
    ),
    cover=Cover(
        subtitle="Documentação técnica",
        tagline="Referência de código: módulos, componentes e APIs",
    ),
    header_right="Referência de código",
)

# "slides": guia de identidade visual, em 16:9 para projeção. Tipografia
# grande; capa e divisórias sangram na cor escura da marca.
SLIDES_THEME = Theme(
    page=SLIDE_PAGE,
    typography=Typography(
        h1_size=34.0,       # divisória de seção
        h2_size=22.0,       # título do slide
        h3_size=13.0,
        body_size=13.0,
        body_leading=7.0,
        mono_size=11.0,
        h1_gap_before=0.0,
        h2_gap_before=0.0,
    ),
    cover=Cover(
        subtitle="Guia de identidade visual",
        tagline="Marca, cores, tipografia e aplicação, extraídos do repositório",
    ),
    header_right="Identidade visual",
)

# Tipo de documentação -> tema. A ordem define a ordem do menu.
DOC_TYPES = {
    "brand": BRAND_THEME,
    "development": DEVELOPMENT_THEME,
    "full": FULL_THEME,
    "slides": SLIDES_THEME,
}

# Rótulos exibidos no painel interativo.
DOC_TYPE_LABELS = {
    "brand": "🏷️  Marca e regras        (uso, arquitetura, convenções)",
    "development": "🛠️  Código                 (estrutura, módulos, APIs, testes)",
    "full": "📚  Completa               (marca + código no mesmo PDF)",
    "slides": "🎞️  Identidade visual      (apresentação 16:9: marca, cores, tipografia)",
}

DEFAULT_THEME = BRAND_THEME
