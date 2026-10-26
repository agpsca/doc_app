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

    dark: RGB = (31, 41, 51)          # #1F2933  fundo da capa, h2
    brand: RGB = (51, 78, 104)        # #334E68  h1, chaves, sumário
    accent: RGB = (130, 154, 177)     # #829AB1  réguas, barra de callout
    ink: RGB = (31, 41, 51)           # #1F2933  texto principal
    muted: RGB = (123, 135, 148)      # #7B8794  texto secundário
    rule: RGB = (228, 231, 235)       # #E4E7EB  linhas finas
    code_bg: RGB = (245, 247, 250)    # #F5F7FA  fundo de bloco de código
    callout_bg: RGB = (240, 244, 248) # #F0F4F8
    code_fg: RGB = (50, 62, 72)       # #323E48
    zebra: RGB = (249, 250, 251)      # #F9FAFB  faixa alternada das tabelas
    link: RGB = (51, 78, 104)         # #334E68  URLs clicáveis
    cover_text: RGB = (203, 210, 217) # #CBD2D9  linha de apoio da capa
    cover_muted: RGB = (154, 165, 177)# #9AA5B1  rodapé da capa
    white: RGB = (255, 255, 255)


@dataclass(frozen=True)
class Fonts:
    """Fontes TrueType. `dir` aponta para o diretório das DejaVu."""

    dir: str = "/usr/share/fonts/truetype/dejavu"
    sans_regular: str = "DejaVuSans.ttf"
    sans_bold: str = "DejaVuSans-Bold.ttf"
    mono_regular: str = "DejaVuSansMono.ttf"

    def path(self, filename: str) -> str:
        return os.path.join(self.dir, filename)


@dataclass(frozen=True)
class Page:
    """Dimensões de página em mm (A4 por padrão)."""

    width: float = 210.0
    height: float = 297.0
    margin: float = 20.0

    @property
    def content_width(self) -> float:
        return self.width - 2 * self.margin


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
    body_leading: float = 5.6   # altura de linha do parágrafo
    mono_size: float = 9.0
    h1_gap_before: float = 7.0
    h2_gap_before: float = 5.0
    cover_big: bool = True      # capa original (brand/full) vs. variação (development)


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

# Tipo de documentação -> tema. A ordem define a ordem do menu.
DOC_TYPES = {
    "brand": BRAND_THEME,
    "development": DEVELOPMENT_THEME,
    "full": FULL_THEME,
}

# Rótulos exibidos no painel interativo.
DOC_TYPE_LABELS = {
    "brand": "🏷️  Marca e regras        (uso, arquitetura, convenções)",
    "development": "🛠️  Código                 (estrutura, módulos, APIs, testes)",
    "full": "📚  Completa               (marca + código no mesmo PDF)",
}

DEFAULT_THEME = BRAND_THEME
