"""Apresentação em 16:9 a partir dos mesmos blocos do documento.

O tipo "slides" é o guia de identidade visual: capa e divisórias sangrando na
cor escura da marca, um slide por subseção e blocos próprios para o que um
guia precisa mostrar — o arquivo do logotipo, a área de proteção medida, as
amostras de cor e o especimen tipográfico.

O que um slide não comporta continua no slide seguinte, marcado "(cont.)": a
quebra automática do fpdf2 cuida disso, e `header()` repinta o fundo.
"""

from __future__ import annotations

from pathlib import Path

from .dsl import Block
from .renderer import DocPDF, Renderer
from .theme import SLIDES_THEME, Theme

# Alturas fixas do slide, em mm.
LABEL_Y = 12.0          # etiquetas do topo
TITLE_Y = 22.0          # título do slide
BODY_Y = 46.0           # início do corpo
MAX_LOGO_H = 62.0       # altura máxima de um asset desenhado


class SlidePDF(DocPDF):
    """Página 16:9. O fundo, as etiquetas e o número do slide são por página,
    então moram no `header`/`footer`, que o fpdf2 chama a cada página nova."""

    def __init__(self, theme: Theme):
        super().__init__(theme)
        self.set_auto_page_break(auto=True, margin=20)
        self.kind = "content"        # cover | divider | content
        self.kinds: dict[int, str] = {}   # tipo de cada página já aberta
        self.slide_title = ""
        self.section = ""
        self.continuing = False
        self.drawn = 0               # blocos já desenhados no slide atual

    def page_kind(self) -> str:
        """Tipo da página corrente. O `footer` roda quando a página fecha, já
        com `kind` apontando para o slide seguinte, então ele consulta aqui."""
        return self.kinds.get(self.page_no(), self.kind)

    def header(self):
        t = self.theme
        p, pal = t.page, t.palette
        self.kinds[self.page_no()] = self.kind
        self.set_fill_color(*(pal.dark if self.kind in ("cover", "divider")
                              else pal.callout_bg))
        self.rect(0, 0, p.width, p.height, style="F")
        if self.kind != "content":
            return

        self.set_font("DejaVu", "", 8)
        self.set_text_color(*pal.muted)
        self.set_xy(p.margin, LABEL_Y)
        self.cell(p.content_width / 2, 4, t.header_left.upper(), align="L")
        self.set_xy(p.margin + p.content_width / 2, LABEL_Y)
        self.cell(p.content_width / 2, 4, (self.section or t.header_right).upper(),
                  align="R")
        if self.continuing and self.slide_title:
            self._draw_title(f"{self.slide_title} (cont.)")
        self.set_y(BODY_Y)

    def _draw_title(self, text: str):
        t = self.theme
        p, pal = t.page, t.palette
        self.set_xy(p.margin, TITLE_Y)
        self.set_font("DejaVu", "B", t.typography.h2_size)
        self.set_text_color(*pal.brand)
        self.cell(p.content_width, 10, text, align="L")
        self.set_draw_color(*pal.accent)
        self.set_line_width(0.8)
        self.line(p.margin, TITLE_Y + 13, p.margin + 24, TITLE_Y + 13)

    def footer(self):
        t = self.theme
        p, pal = t.page, t.palette
        kind = self.page_kind()
        if t.classification and kind == "content":
            self._draw_watermark(t.classification)
        if kind == "cover":
            return
        self.set_y(p.height - 12)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*(pal.cover_muted if kind == "divider" else pal.muted))
        label = str(self.page_no())
        if t.classification and kind == "content":
            self.set_x(p.margin)
            self.set_font("DejaVu", "B", 8)
            self.set_text_color(*pal.brand)
            self.cell(p.content_width / 2, 5,
                      f"{t.classification.upper()} · não distribuir", align="L")
            self.set_font("DejaVu", "", 8)
            self.set_text_color(*pal.muted)
        self.set_x(p.margin)
        self.cell(p.content_width, 5, label, align="R")


class SlidesRenderer(Renderer):
    """Desenha os blocos como slides. Herda do `Renderer` o desenho de
    parágrafo, listas, código, tabela, kv e callout."""

    def __init__(self, theme: Theme):
        self.theme = theme
        self.pdf = SlidePDF(theme)
        self._glyphs = self._supported_codepoints()
        self._section = ""

    # -- estrutura ---------------------------------------------------------

    def asset_path(self, rel: str) -> Path | None:
        """Caminho absoluto de um asset do app. None quando não existe."""
        root = self.theme.assets_root
        path = Path(rel).expanduser()
        if not path.is_absolute():
            if not root:
                return None
            path = Path(root).expanduser() / rel
        return path if path.is_file() else None

    def draw_cover(self, logo: str | None = None):
        pdf, t = self.pdf, self.theme
        p, pal, cov = t.page, t.palette, t.cover
        pdf.kind = "cover"
        pdf.add_page()
        pdf.set_auto_page_break(auto=False)   # a capa é desenhada por posição

        y = 52.0
        found = self.asset_path(logo) if logo else None
        if found:
            try:
                pdf.image(str(found), x=p.margin, y=y - 30, h=24)
            except (RuntimeError, ValueError):
                found = None
        pdf.set_xy(p.margin, y)
        pdf.set_text_color(*pal.accent)
        pdf.set_font("DejaVu", "B", 40)
        pdf.cell(0, 18, cov.title, align="L")

        pdf.set_xy(p.margin, y + 24)
        pdf.set_text_color(*pal.white)
        pdf.set_font("DejaVu", "", 16)
        pdf.cell(0, 9, cov.subtitle, align="L")

        pdf.set_fill_color(*pal.accent)
        pdf.rect(p.margin, y + 40, 40, 1.6, style="F")

        pdf.set_xy(p.margin, y + 48)
        pdf.set_text_color(*pal.cover_text)
        pdf.set_font("DejaVu", "", 11)
        pdf.multi_cell(p.content_width * 0.7, 6, cov.tagline)

        pdf.set_xy(p.margin, p.height - 24)
        pdf.set_text_color(*pal.cover_muted)
        pdf.set_font("DejaVu", "", 9)
        pdf.multi_cell(p.content_width * 0.7, 5, cov.footnote)
        if t.classification:
            self._draw_cover_badge(pdf, p, pal, t.classification)
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.drawn = 1        # a capa é conteúdo: o próximo slide é página nova

    def new_slide(self, kind: str) -> None:
        """Começa um slide. Uma página ainda vazia (a que o sumário deixa
        reservada, por exemplo) é reaproveitada em vez de virar slide em
        branco."""
        pdf = self.pdf
        pdf.kind = kind
        if pdf.page_no() and not pdf.drawn:
            pdf.header()          # repinta o fundo e as etiquetas desta página
        else:
            pdf.add_page()
        pdf.drawn = 0

    def render_agenda(self, pdf, outline):
        """Sumário em duas colunas, com o número do slide de cada seção.

        Chamado pelo fpdf2 no fim da geração, na página reservada: o título
        também é desenhado aqui, porque o conteúdo daquela página é refeito.
        """
        t = self.theme
        p, pal = t.page, t.palette
        pdf.kind = "content"
        pdf._draw_title("Conteúdo")
        pdf.set_y(BODY_Y)
        entries = [s for s in outline if s.level <= 1]
        if not entries:
            return
        col_w = p.content_width / 2 - 6
        per_col = (len(entries) + 1) // 2
        for i, section in enumerate(entries):
            col, row = divmod(i, per_col) if per_col else (0, 0)
            x = p.margin + col * (col_w + 12)
            y = BODY_Y + row * 10.5
            link = pdf.add_link(page=section.page_number)
            pdf.set_xy(x, y)
            if section.level == 0:
                pdf.set_font("DejaVu", "B", 13)
                pdf.set_text_color(*pal.brand)
            else:
                pdf.set_font("DejaVu", "", 11)
                pdf.set_text_color(*pal.ink)
            pdf.cell(col_w - 10, 7, section.name, link=link)
            pdf.set_xy(x + col_w - 10, y)
            pdf.set_font("DejaVu", "", 9)
            pdf.set_text_color(*pal.muted)
            pdf.cell(10, 7, str(section.page_number), align="R", link=link)

    def heading(self, text: str, level: int, anchor_id: str | None = None,
                reserve: float | None = None):
        """h1 abre uma divisória de seção; h2 abre um slide novo; h3 é
        subtítulo dentro do slide."""
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        if level == 1:
            self._section = text
            pdf.continuing = False
            self.new_slide("divider")
            pdf.start_section(text, level=0)
            pdf.set_xy(p.margin, p.height / 2 - 18)
            pdf.set_font("DejaVu", "B", t.typography.h1_size)
            pdf.set_text_color(*pal.accent)
            pdf.multi_cell(p.content_width, 16, text, align="L")
            pdf.set_fill_color(*pal.accent)
            pdf.rect(p.margin, p.height / 2 + 14, 40, 1.6, style="F")
            pdf.drawn = 1
            return
        if level == 2:
            pdf.section = self._section
            pdf.slide_title = text
            pdf.continuing = False
            self.new_slide("content")
            pdf.start_section(text, level=1)
            pdf._draw_title(text)
            pdf.set_y(BODY_Y)
            pdf.continuing = True
            return
        pdf.ln(2)
        pdf.set_font("DejaVu", "B", t.typography.h3_size)
        pdf.set_text_color(*pal.dark)
        pdf.multi_cell(p.content_width, 6.5, text, align="L")
        pdf.ln(1.5)

    # -- blocos de identidade ---------------------------------------------

    def logo_block(self, spec: dict):
        """Asset da marca, desenhado no tamanho que couber no slide. Com
        `on: both`, mostra a mesma marca sobre fundo claro e sobre escuro —
        é a prova de que ela funciona nos dois."""
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        caption = spec.get("caption") or spec["path"]
        top = pdf.get_y()
        height = min(MAX_LOGO_H, p.height - 34 - top)
        if spec.get("on") == "both":
            self._two_panels(spec, top, height)
        else:
            dark = spec.get("on") == "dark"
            if dark:
                pdf.set_fill_color(*pal.dark)
                pdf.rect(p.margin, top, p.content_width, height, style="F")
            self._place(spec["path"], p.margin + 8, top + 6, height - 12,
                        p.content_width - 16)
        pdf.set_xy(p.margin, top + height + 1)
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*pal.muted)
        pdf.multi_cell(p.content_width, 5, caption)
        pdf.ln(2)

    def _two_panels(self, spec: dict, top: float, height: float) -> None:
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        half = (p.content_width - 8) / 2
        pdf.set_fill_color(*pal.white)
        pdf.set_draw_color(*pal.rule)
        pdf.set_line_width(0.2)
        pdf.rect(p.margin, top, half, height, style="DF")
        pdf.set_fill_color(*pal.dark)
        pdf.rect(p.margin + half + 8, top, half, height, style="F")
        self._place(spec["path"], p.margin + 6, top + 8, height - 22, half - 12)
        self._place(spec.get("path_dark") or spec["path"],
                    p.margin + half + 14, top + 8, height - 22, half - 12)
        pdf.set_font("DejaVu", "", 8)
        for x, label, color in ((p.margin, "SOBRE FUNDO CLARO", pal.muted),
                                (p.margin + half + 8, "SOBRE FUNDO ESCURO",
                                 pal.cover_muted)):
            pdf.set_xy(x, top + height - 9)
            pdf.set_text_color(*color)
            pdf.cell(half, 5, f"  {label}", align="L")

    def _place(self, rel: str, x: float, y: float, h: float, w: float) -> None:
        """Desenha a imagem dentro da caixa, ou um aviso quando falta."""
        pdf = self.pdf
        found = self.asset_path(rel)
        if found:
            try:
                pdf.image(str(found), x=x, y=y, h=h, w=w,
                          keep_aspect_ratio=True)
                return
            except (RuntimeError, ValueError):
                pass
        pdf.set_xy(x, y + h / 2 - 3)
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*self.theme.palette.muted)
        pdf.cell(w, 6, f"arquivo não encontrado: {rel}", align="C")

    def _missing_box(self, rel: str, height: float):
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        top = pdf.get_y()
        pdf.set_draw_color(*pal.rule)
        pdf.set_line_width(0.3)
        pdf.set_dash_pattern(dash=2, gap=2)
        pdf.rect(p.margin, top, p.content_width, height, style="D")
        pdf.set_dash_pattern()
        pdf.set_xy(p.margin, top + height / 2 - 3)
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*pal.muted)
        pdf.cell(p.content_width, 6, f"arquivo não encontrado: {rel}", align="C")
        pdf.set_y(top)

    def clearspace_block(self, spec: dict):
        """Área de proteção: o símbolo sobre uma grade de ¼H, com a margem
        mínima tracejada em volta. H é a altura do símbolo."""
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        ratio = float(spec.get("ratio") or 0.5)
        found = self.asset_path(spec["path"])
        top = pdf.get_y() + 4
        H = 36.0                       # altura do símbolo no desenho
        pad = H * ratio
        box_w = box_h = H + 2 * pad
        x0 = p.margin + (p.content_width - box_w) / 2
        module = H / 4

        # grade de módulos, discreta, atrás de tudo
        pdf.set_draw_color(*pal.rule)
        pdf.set_line_width(0.1)
        grid_w = box_w + 2 * module
        grid_h = box_h + 2 * module
        gx, gy = x0 - module, top - module
        steps_x = int(grid_w / module)
        steps_y = int(grid_h / module)
        for i in range(steps_x + 1):
            pdf.line(gx + i * module, gy, gx + i * module, gy + steps_y * module)
        for i in range(steps_y + 1):
            pdf.line(gx, gy + i * module, gx + steps_x * module, gy + i * module)

        if found is None:
            pdf.set_xy(x0 + pad, top + pad)
            self._missing_box(spec["path"], H)
        else:
            try:
                pdf.image(str(found), x=x0 + pad, y=top + pad, h=H, w=H,
                          keep_aspect_ratio=True)
            except (RuntimeError, ValueError):
                found = None

        # limite da área de proteção
        pdf.set_draw_color(*pal.accent)
        pdf.set_line_width(0.5)
        pdf.set_dash_pattern(dash=2, gap=2)
        pdf.rect(x0, top, box_w, box_h, style="D")
        pdf.set_dash_pattern()

        # cotas: H do símbolo e o respiro
        label = "½H" if abs(ratio - 0.5) < 0.01 else f"{ratio:g} H".replace(".", ",")
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*pal.brand)
        pdf.text(x0 + pad / 2 - 3, top + pad / 2 + 1, label)
        pdf.set_text_color(*pal.dark)
        pdf.text(x0 + box_w + 2, top + box_h / 2, "H")
        pdf.set_draw_color(*pal.dark)
        pdf.set_line_width(0.3)
        pdf.line(x0 + box_w + 1, top + pad, x0 + box_w + 1, top + pad + H)

        pdf.set_y(top + box_h + module + 3)
        pdf.set_xy(p.margin, pdf.get_y())
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*pal.muted)
        caption = spec.get("caption") or (
            f"H é a altura do símbolo ({spec['path']}). Respiro mínimo de "
            f"{label} nos quatro lados; a grade é de ¼H.")
        pdf.multi_cell(p.content_width, 5, caption)
        pdf.ln(2)

    def swatches_block(self, spec: dict):
        """Amostras de cor com nome, código e arquivo de origem."""
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        items = spec["items"]
        per_row = min(6, max(1, len(items)))
        chip = min(40.0 if len(items) <= 6 else 32.0,
                   (p.content_width - (per_row - 1) * 6) / per_row)
        pdf.ln(1)
        for start in range(0, len(items), per_row):
            row = items[start:start + per_row]
            top = pdf.get_y()
            if top + chip + 18 > p.height - 24:
                pdf.add_page()
                top = pdf.get_y()
            for i, item in enumerate(row):
                x = p.margin + i * (chip + 6)
                rgb = _rgb(item["hex"])
                pdf.set_fill_color(*rgb)
                pdf.set_draw_color(*pal.rule)
                pdf.set_line_width(0.2)
                pdf.rect(x, top, chip, chip, style="DF")
                pdf.set_xy(x, top + chip + 1.5)
                pdf.set_font("DejaVu", "B", 8.5)
                pdf.set_text_color(*pal.dark)
                pdf.multi_cell(chip, 4.2, item["name"].lstrip("-$@"))
                pdf.set_x(x)
                pdf.set_font("Mono", "", 8)
                pdf.set_text_color(*pal.brand)
                pdf.cell(chip, 4, item["hex"].upper())
                if item.get("source"):
                    pdf.set_xy(x, pdf.get_y() + 4)
                    pdf.set_font("DejaVu", "", 7)
                    pdf.set_text_color(*pal.muted)
                    pdf.multi_cell(chip, 3.4, item["source"])
            pdf.set_y(top + chip + 20)
        pdf.ln(1)

    def specimen_block(self, spec: dict):
        """Especimen tipográfico: a família declarada no código, o papel dela e
        uma amostra. A amostra é desenhada com a fonte do PDF, não com a fonte
        da marca (que o repositório não embute)."""
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        sample = spec.get("sample") or "Aa Bb Cc 0123456789"
        pdf.ln(1)
        top = pdf.get_y()
        pdf.set_font("DejaVu", "B", 34)
        pdf.set_text_color(*pal.dark)
        pdf.set_xy(p.margin, top)
        pdf.cell(p.content_width, 16, sample)
        pdf.set_xy(p.margin, top + 18)
        pdf.set_font("DejaVu", "B", 12)
        pdf.set_text_color(*pal.brand)
        role = f" · {spec['role']}" if spec.get("role") else ""
        pdf.cell(p.content_width, 6, f"{spec['font']}{role}")
        lines = []
        if spec.get("weights"):
            lines.append(f"Pesos declarados: {spec['weights']}")
        if spec.get("source"):
            lines.append(f"Declarada em {spec['source']}")
        lines.append("Amostra desenhada com a fonte do PDF; o arquivo da fonte "
                     "não está no repositório.")
        pdf.set_xy(p.margin, top + 25)
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*pal.muted)
        pdf.multi_cell(p.content_width, 4.8, "\n".join(lines))
        pdf.ln(2)


def _rgb(value: str) -> tuple[int, int, int]:
    h = value.strip().lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# --- montagem ---------------------------------------------------------------

def build_slides(blocks: list[Block], output_path: str | Path,
                 theme: Theme | None = None, cover_logo: str | None = None) -> Path:
    """Gera a apresentação em `output_path` a partir dos `blocks`."""
    theme = theme or SLIDES_THEME
    r = SlidesRenderer(theme)
    pdf = r.pdf

    r.draw_cover(cover_logo)
    pdf.slide_title = "Conteúdo"
    pdf.continuing = False
    r.new_slide("content")
    pdf.insert_toc_placeholder(r.render_agenda, pages=1, allow_extra_pages=True)

    for block in blocks:
        _render(r, block)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    return out


# Altura mínima (mm) que estes blocos pedem; abaixo disso, vão para o slide
# seguinte em vez de ficarem comprimidos no pé.
_NEEDS = {"logo": 70.0, "clearspace": 95.0, "swatches": 65.0, "specimen": 45.0,
          "table": 30.0, "code": 25.0}


def _render(r: SlidesRenderer, block: Block) -> None:
    pdf, typ = r.pdf, block.type
    content = r.clean_content(block.content, keep_spacing=(typ == "code"))
    if typ in ("h1", "h2", "h3"):
        if typ == "h3" and pdf.kind == "divider":
            r.new_slide("content")
        r.heading(content, int(typ[1]))
        return
    if pdf.kind == "divider":      # bloco solto depois de uma divisória
        r.new_slide("content")
        pdf.set_y(BODY_Y)
    need = _NEEDS.get(typ, 0.0)
    if need and pdf.get_y() + need > r.theme.page.height - 24:
        pdf.add_page()
    if typ == "p":
        r.paragraph(content)
    elif typ == "bullet":
        r.bullets(content)
    elif typ == "num":
        r.bullets(content, numbered=True)
    elif typ == "code":
        r.code_block(content)
    elif typ == "callout":
        r.callout(content["title"], content["text"])
    elif typ == "kv":
        r.kv_block([(p["key"], p["value"]) for p in content])
    elif typ == "table":
        r.table_block(content)
    elif typ == "logo":
        r.logo_block(content)
    elif typ == "clearspace":
        r.clearspace_block(content)
    elif typ == "swatches":
        r.swatches_block(content)
    elif typ == "specimen":
        r.specimen_block(content)
    elif typ == "spacer":
        pdf.ln(content)
    pdf.drawn += 1
