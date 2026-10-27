"""Engine de renderização em PDF (fpdf2).

Desacoplada do conteúdo: todas as cores, fontes e dimensões vêm de um
`Theme`. A classe `Renderer` sabe desenhar cada tipo de bloco da DSL.
"""

from __future__ import annotations

import re

from fpdf import FPDF

from .sections import TODO as TODO_MARK
from .theme import Theme


class DocPDF(FPDF):
    """FPDF com cabeçalho/rodapé da marca, fontes e metadados."""

    def __init__(self, theme: Theme):
        p = theme.page
        super().__init__(format=(p.width, p.height), unit="mm")
        self.theme = theme
        self.set_auto_page_break(auto=True, margin=22)
        self.set_margins(p.margin, p.margin, p.margin)
        f = theme.fonts
        self.add_font("DejaVu", "", f.path(f.sans_regular))
        self.add_font("DejaVu", "B", f.path(f.sans_bold))
        self.add_font("Mono", "", f.path(f.mono_regular))
        self.cover = False
        self._apply_metadata()

    def _apply_metadata(self):
        """Metadados do documento, exibidos nas propriedades do leitor de PDF."""
        cov = self.theme.cover
        title = f"{cov.title} — {cov.subtitle}" if cov.subtitle else cov.title
        self.set_title(title)
        self.set_subject(cov.tagline)
        self.set_creator("doc_app")
        self.set_lang("pt-BR")
        if self.theme.classification:
            self.set_keywords(self.theme.classification)

    def header(self):
        if self.cover or self.page_no() == 1:
            return
        t = self.theme
        p = t.page
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*t.palette.muted)
        self.set_y(10)
        self.cell(0, 5, t.header_left, align="L")
        self.set_x(p.margin)
        self.cell(p.content_width, 5, t.header_right, align="R")
        self.set_draw_color(*t.palette.rule)
        self.set_line_width(0.2)
        self.line(p.margin, 16, p.width - p.margin, 16)
        self.set_y(p.margin)

    def _draw_watermark(self, label: str):
        """Texto diagonal semitransparente no centro da página.

        Desenhado no rodapé (por último), por cima do conteúdo: assim fundos
        de tabela e caixas não o cobrem, e a transparência mantém o texto
        da página legível.
        """
        t = self.theme
        p = t.page
        text = label.upper()
        size = 64
        self.set_font("DejaVu", "B", size)
        # reduz a fonte se o texto for longo demais para a diagonal
        while size > 24 and self.get_string_width(text) > p.height * 0.75:
            size -= 4
            self.set_font("DejaVu", "B", size)
        w = self.get_string_width(text)
        cx, cy = p.width / 2, p.height / 2
        with self.local_context(fill_opacity=0.07, text_color=t.palette.brand):  # noqa: SIM117
            with self.rotation(angle=45, x=cx, y=cy):
                # 1pt = 0.3528mm; desloca 1/3 da altura para centralizar
                self.text(cx - w / 2, cy + size * 0.3528 / 3, text)

    def footer(self):
        if self.cover or self.page_no() == 1:
            return
        t = self.theme
        p = t.page
        if t.classification:
            self._draw_watermark(t.classification)
        # régua fina acima do rodapé
        self.set_draw_color(*t.palette.rule)
        self.set_line_width(0.2)
        self.line(p.margin, p.height - 14, p.width - p.margin, p.height - 14)
        self.set_y(-12)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*t.palette.muted)
        # esquerda: título curto; centro: classificação; direita: Página X de Y
        third = p.content_width / 3
        self.cell(third, 5, t.footer_left, align="L")
        if t.classification:
            self.set_x(p.margin + third)
            self.set_font("DejaVu", "B", 8)
            self.set_text_color(*t.palette.brand)
            self.cell(third, 5, f"{t.classification.upper()} · não distribuir",
                      align="C")
            self.set_font("DejaVu", "", 8)
            self.set_text_color(*t.palette.muted)
        self.set_x(p.margin + 2 * third)
        self.cell(third, 5, f"Página {self.page_no()} de {{nb}}", align="R")


class Renderer:
    """Desenha blocos da DSL num `DocPDF`."""

    def __init__(self, theme: Theme):
        self.theme = theme
        self.pdf = DocPDF(theme)
        self._glyphs = self._supported_codepoints()

    def _supported_codepoints(self) -> set[int]:
        """Caracteres que as fontes registradas sabem desenhar."""
        pdf = self.pdf
        codes: set[int] = set()
        for family in ("DejaVu", "Mono"):
            pdf.set_font(family, "", 10)
            codes |= set(pdf.current_font.cmap)
        return codes

    def clean(self, text: str, keep_spacing: bool = False) -> str:
        """Remove caracteres sem desenho na fonte (emojis, seletores de
        variação), que sairiam como quadrados no PDF. Com `keep_spacing`
        (blocos de código), não mexe nos espaços."""
        if not isinstance(text, str):
            return text
        out = "".join(ch for ch in text
                      if ch in "\n\t" or ord(ch) in self._glyphs)
        if out == text or keep_spacing:
            return out
        # tira espaços duplos e espaço no início de linha deixados pelo corte
        out = re.sub(r"[ \t]{2,}", " ", out)
        return re.sub(r"(^|\n) ", r"\1", out).strip()

    def clean_content(self, content, keep_spacing: bool = False):
        """Aplica `clean` em todo texto de um bloco (listas e mapas inclusos)."""
        if isinstance(content, str):
            return self.clean(content, keep_spacing)
        if isinstance(content, list):
            return [self.clean_content(c, keep_spacing) for c in content]
        if isinstance(content, dict):
            return {k: self.clean_content(v, keep_spacing) for k, v in content.items()}
        return content

    # -- estrutura ---------------------------------------------------------

    def draw_cover(self):
        pdf, t = self.pdf, self.theme
        p, pal, cov = t.page, t.palette, t.cover
        pdf.cover = True
        pdf.add_page()

        if t.typography.cover_big:
            self._draw_cover_brand(pdf, p, pal, cov)
        else:
            self._draw_cover_development(pdf, p, pal, cov)
        pdf.cover = False

    def _draw_cover_brand(self, pdf, p, pal, cov):
        """Capa original: fundo escuro, título grande. Tipos 'brand' e 'full'."""
        self._draw_cover_base(pdf, p, pal, cov, accent_y=150.0, top_mark=False)

    def _draw_cover_development(self, pdf, p, pal, cov):
        """Mesma capa da 'brand', com uma variação sutil: filete no topo e a
        faixa de destaque posicionada mais acima. Mantém a identidade."""
        self._draw_cover_base(pdf, p, pal, cov, accent_y=96.0, top_mark=True)

    def _draw_cover_base(self, pdf, p, pal, cov, accent_y, top_mark):
        """Capa escura cheia com título grande (base das duas caras).

        accent_y: altura (mm) da faixa de destaque horizontal.
        top_mark: se True, desenha um filete fino no topo (variação development).
        """
        pdf.set_fill_color(*pal.dark)
        pdf.rect(0, 0, p.width, p.height, style="F")

        if top_mark:
            pdf.set_fill_color(*pal.accent)
            pdf.rect(0, 0, p.width, 3, style="F")

        pdf.set_fill_color(*pal.accent)
        pdf.rect(0, accent_y, p.width, 2, style="F")

        pdf.set_xy(p.margin, 110)
        pdf.set_text_color(*pal.accent)
        pdf.set_font("DejaVu", "B", 42)
        pdf.cell(0, 20, cov.title, align="L")

        pdf.set_xy(p.margin, 134)
        pdf.set_text_color(*pal.white)
        pdf.set_font("DejaVu", "", 16)
        pdf.cell(0, 10, cov.subtitle, align="L")

        pdf.set_xy(p.margin, 158)
        pdf.set_text_color(*pal.cover_text)
        pdf.set_font("DejaVu", "", 12)
        pdf.cell(0, 8, cov.tagline, align="L")

        pdf.set_xy(p.margin, 250)
        pdf.set_text_color(*pal.cover_muted)
        pdf.set_font("DejaVu", "", 10)
        pdf.multi_cell(p.content_width, 6, cov.footnote)

        if self.theme.classification:
            self._draw_cover_badge(pdf, p, pal, self.theme.classification)

    def _draw_cover_badge(self, pdf, p, pal, label):
        """Selo de classificação (ex.: USO INTERNO) no canto superior direito."""
        text = label.upper()
        pdf.set_font("DejaVu", "B", 9)
        pad_x, h = 4.0, 8.0
        w = pdf.get_string_width(text) + 2 * pad_x
        x, y = p.width - p.margin - w, 18.0
        pdf.set_draw_color(*pal.accent)
        pdf.set_line_width(0.5)
        pdf.rect(x, y, w, h, style="D")
        pdf.set_xy(x, y)
        pdf.set_text_color(*pal.accent)
        pdf.cell(w, h, text, align="C")

    def render_toc(self, pdf, outline):
        """Renderiza o sumário com líderes pontilhados e números de página.

        Chamada por `insert_toc_placeholder` no fim da geração, quando a página
        de cada seção já é conhecida. Os destinos vêm do `outline` (alimentado
        por `start_section`), então cada linha é clicável.
        """
        t = self.theme
        p, pal = t.page, t.palette

        # Chamada no fim da geração: reposiciona no topo-esquerdo da página.
        pdf.set_xy(p.margin, p.margin)
        pdf.set_text_color(*pal.brand)
        pdf.set_font("DejaVu", "B", 17)
        pdf.multi_cell(p.content_width, 9, "Sumário")
        pdf.set_draw_color(*pal.accent)
        pdf.set_line_width(0.6)
        y = pdf.get_y() + 1
        pdf.line(p.margin, y, p.margin + 28, y)
        pdf.ln(7)

        if not outline:
            pdf.set_font("DejaVu", "", 10)
            pdf.set_text_color(*pal.muted)
            pdf.multi_cell(p.content_width, 6,
                           "Nenhuma seção ainda. Adicione títulos (h1/h2/h3) ao documento.")
            return

        # Estilo por nível: (indent_mm, fonte_estilo, tamanho, cor, altura_linha, gap_antes)
        levels = {
            0: (0.0, "B", 11.0, pal.brand, 7.0, 2.0),
            1: (7.0, "",  10.0, pal.ink,   6.0, 0.5),
            2: (14.0, "", 9.0,  pal.muted, 5.4, 0.0),
        }

        for section in outline:
            indent, style, size, color, line_h, gap = levels.get(
                section.level, levels[1])
            if gap:
                pdf.ln(gap)

            page_label = str(section.page_number)
            link = pdf.add_link(page=section.page_number)
            y0 = pdf.get_y()
            x_start = p.margin + indent

            # título à esquerda
            pdf.set_font("DejaVu", style, size)
            pdf.set_text_color(*color)
            pdf.set_xy(x_start, y0)
            title_w = pdf.get_string_width(section.name)
            pdf.cell(title_w + 1, line_h, section.name, link=link)

            # número de página à direita
            pdf.set_font("DejaVu", "", max(size - 1, 8))
            pdf.set_text_color(*pal.muted)
            num_w = pdf.get_string_width(page_label) + 1
            pdf.set_xy(p.width - p.margin - num_w, y0)
            pdf.cell(num_w, line_h, page_label, align="R", link=link)

            # líderes pontilhados entre o título e o número
            dot_left = x_start + title_w + 2
            dot_right = p.width - p.margin - num_w - 2
            if dot_right > dot_left:
                pdf.set_draw_color(*pal.rule)
                pdf.set_line_width(0.2)
                pdf.set_dash_pattern(dash=0.3, gap=1.2)
                ymid = y0 + line_h - 1.8
                pdf.line(dot_left, ymid, dot_right, ymid)
                pdf.set_dash_pattern()  # reseta

            pdf.set_xy(p.margin, y0 + line_h)

    # -- blocos ------------------------------------------------------------

    def heading(self, text: str, level: int, anchor_id: str | None = None,
                reserve: float | None = None):
        """Título. `reserve` (mm) é o espaço mínimo que o bloco seguinte
        precisa na mesma página; se não couber, o título vai para a próxima."""
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        typo = t.typography
        sizes = {1: typo.h1_size, 2: typo.h2_size, 3: typo.h3_size}

        # Decide a quebra de página ANTES de registrar a seção, para o sumário
        # apontar para a página onde o título realmente fica.
        gap = {1: typo.h1_gap_before, 2: typo.h2_gap_before}.get(level, 3.0)
        title_h = {1: 9 + 6.5, 2: 7 + 2}.get(level, 6 + 1.5)
        if reserve is None:
            reserve = 2 * typo.body_leading
        needed = gap + title_h + reserve
        if pdf.get_y() + needed > p.height - 22:
            pdf.add_page()
            gap = 0  # no topo da página não precisa de espaço antes
        elif pdf.get_y() <= p.margin + 1:
            gap = 0

        if anchor_id is not None and level in (1, 2, 3):
            # O fpdf exige hierarquia contínua nos marcadores: um h3 solto
            # (seção sem h2, caso comum quando o texto vem do README) entraria
            # como nível 2 depois de um nível 0 e quebraria a geração.
            last = self.pdf._outline[-1].level if self.pdf._outline else -1
            pdf.start_section(text, level=min(level - 1, last + 1))

        if level == 1:
            pdf.ln(gap)
            pdf.set_text_color(*pal.brand)
            pdf.set_font("DejaVu", "B", sizes[1])
            pdf.multi_cell(p.content_width, 9, text, align="L")
            pdf.set_draw_color(*pal.accent)
            pdf.set_line_width(0.6)
            y = pdf.get_y() + 1.5
            pdf.line(p.margin, y, p.margin + 28, y)
            pdf.ln(5)
        elif level == 2:
            pdf.ln(gap)
            pdf.set_text_color(*pal.dark)
            pdf.set_font("DejaVu", "B", sizes[2])
            pdf.multi_cell(p.content_width, 7, text, align="L")
            pdf.ln(2)
        else:
            pdf.ln(gap)
            pdf.set_text_color(*pal.ink)
            pdf.set_font("DejaVu", "B", sizes[3])
            pdf.multi_cell(p.content_width, 6, text, align="L")
            pdf.ln(1.5)

    @staticmethod
    def pending(text: str) -> tuple[bool, str]:
        """Separa a marca de pendência do texto.

        O YAML guarda "(TODO) ..." porque é o que as ferramentas contam; no
        PDF isso vira uma anotação discreta ("A DEFINIR") quando abre o
        parágrafo, e "a definir:" quando aparece no meio de uma frase.
        """
        stripped = text.lstrip()
        if stripped.startswith(TODO_MARK):
            return True, Renderer._inline_pending(stripped[len(TODO_MARK):].lstrip())
        return False, Renderer._inline_pending(text)

    @staticmethod
    def _inline_pending(text: str) -> str:
        if TODO_MARK not in text:
            return text
        return (text.replace(f"{TODO_MARK} ", "a definir: ")
                .replace(TODO_MARK, "a definir"))

    def paragraph(self, text: str, keep_with: float = 0.0):
        """Parágrafo. `keep_with` (mm) reserva espaço para o bloco seguinte
        (usado em frases de introdução, como 'Estrutura de src/:')."""
        pdf, t = self.pdf, self.theme
        typo = t.typography
        open_item, text = self.pending(text)
        indent = 0.0
        if open_item:
            indent = 6.0
        width = t.page.content_width - indent
        pdf.set_font("DejaVu", "", typo.body_size)
        if keep_with:
            lines = pdf.multi_cell(width, typo.body_leading, text,
                                   dry_run=True, output="LINES")
            own = len(lines) * typo.body_leading + 2.2
            if pdf.get_y() + own + keep_with > t.page.height - 24:
                pdf.add_page()
        if open_item:
            self._pending_mark(width, text)
            return
        pdf.set_text_color(*t.palette.ink)
        pdf.multi_cell(width, typo.body_leading, text, align="L")
        pdf.ln(2.2)

    def _pending_mark(self, width: float, text: str):
        """Anotação de pendência: filete, rótulo e o assunto, em tom de apoio."""
        pdf, t = self.pdf, self.theme
        p, pal, typo = t.page, t.palette, t.typography
        x0, y0 = p.margin, pdf.get_y()
        pdf.set_font("DejaVu", "B", max(typo.body_size - 3.0, 7.0))
        label = "A DEFINIR"
        label_w = pdf.get_string_width(label) + 3
        pdf.set_xy(x0 + 6, y0)
        pdf.set_text_color(*pal.muted)
        pdf.cell(label_w, typo.body_leading, label)
        pdf.set_font("DejaVu", "", typo.body_size)
        pdf.set_xy(x0 + 6 + label_w, y0)
        pdf.multi_cell(width - label_w, typo.body_leading, text, align="L")
        height = max(pdf.get_y() - y0, typo.body_leading)
        pdf.set_draw_color(*pal.rule)
        pdf.set_line_width(1.2)
        pdf.line(x0 + 1, y0 + 1, x0 + 1, y0 + height - 1)
        pdf.set_xy(x0, y0 + height)
        pdf.ln(2.4)

    def bullets(self, items, numbered=False):
        pdf, t = self.pdf, self.theme
        pdf.set_font("DejaVu", "", 10.5)
        for i, it in enumerate(items, 1):
            open_item, it = self.pending(it)
            marker = f"{i}." if numbered else "•"
            x = pdf.get_x()
            pdf.set_text_color(*(t.palette.muted if open_item else t.palette.ink))
            pdf.cell(7, 5.6, "·" if open_item else marker)
            pdf.set_x(x + 7)
            if open_item:
                pdf.set_font("DejaVu", "B", 7.5)
                width = pdf.get_string_width("A DEFINIR") + 3
                pdf.cell(width, 5.6, "A DEFINIR")
                pdf.set_font("DejaVu", "", 10.5)
                pdf.set_x(x + 7 + width)
                pdf.multi_cell(t.page.content_width - 7 - width, 5.6, it, align="L")
            else:
                pdf.multi_cell(t.page.content_width - 7, 5.6, it, align="L")
            pdf.ln(0.8)
        pdf.set_text_color(*t.palette.ink)
        pdf.ln(1.6)

    def code_block(self, text: str):
        """Bloco monoespaçado. Blocos curtos não se dividem; blocos longos
        continuam na página seguinte em vez de deixar um vazio grande."""
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        pdf.ln(1)
        pdf.set_font("Mono", "", 9)
        line_h = 5.0
        pad = 3
        bottom = p.height - 24
        max_w = p.content_width - 2 * pad

        lines = []
        for ln in text.split("\n"):
            if pdf.get_string_width(ln) > max_w:
                while ln and pdf.get_string_width(ln + "…") > max_w:
                    ln = ln[:-1]
                ln += "…"
            lines.append(ln)

        # Blocos de até 8 linhas ficam inteiros; maiores podem se dividir,
        # desde que caibam ao menos 4 linhas na página atual.
        min_chunk = len(lines) if len(lines) <= 8 else 4
        if pdf.get_y() + line_h * min_chunk + 2 * pad > bottom:
            pdf.add_page()

        i = 0
        while i < len(lines):
            y0 = pdf.get_y()
            fit = max(1, int((bottom - y0 - 2 * pad) // line_h))
            chunk = lines[i:i + fit]
            height = line_h * len(chunk) + 2 * pad
            pdf.set_fill_color(*pal.code_bg)
            pdf.set_draw_color(*pal.rule)
            pdf.set_line_width(0.2)
            pdf.rect(p.margin, y0, p.content_width, height, style="DF")
            pdf.set_text_color(*pal.code_fg)
            pdf.set_font("Mono", "", 9)
            pdf.set_y(y0 + pad)
            for ln in chunk:
                pdf.set_x(p.margin + pad)
                pdf.cell(max_w, line_h, ln)
                pdf.ln(line_h)
            pdf.set_y(y0 + height)
            i += len(chunk)
            if i < len(lines):
                pdf.add_page()
        pdf.ln(3)

    def callout(self, title: str, text: str):
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        open_item, text = self.pending(text)
        if open_item:
            text = f"A definir: {text}"
        pdf.ln(1)
        pad = 3.5
        bar = 2.5
        gap = 2.0  # respiro entre a barra e o texto
        text_x = p.margin + bar + gap + pad
        inner_w = p.content_width - bar - gap - 2 * pad
        line_h = 5.2
        full = f"{title}. {text}"

        # Mede a altura na MESMA largura do desenho (inner_w), com DejaVu.
        pdf.set_font("DejaVu", "", 10)
        body_lines = pdf.multi_cell(inner_w, line_h, full,
                                    dry_run=True, output="LINES")
        height = line_h * len(body_lines) + 2 * pad

        x0, y0 = p.margin, pdf.get_y()
        if y0 + height > p.height - 27:
            pdf.add_page()
            y0 = pdf.get_y()

        pdf.set_fill_color(*pal.callout_bg)
        pdf.rect(x0, y0, p.content_width, height, style="F")
        pdf.set_fill_color(*pal.accent)
        pdf.rect(x0, y0, bar, height, style="F")

        # Confina a quebra de linha do write() à coluna do texto: ajustamos
        # AMBAS as margens (esquerda = text_x, direita = após inner_w) para que
        # as linhas que quebram voltem para a coluna do texto, nunca para cima
        # da barra verde.
        saved_lmargin = pdf.l_margin
        saved_rmargin = pdf.r_margin
        pdf.set_left_margin(text_x)
        pdf.set_right_margin(p.width - (text_x + inner_w))

        pdf.set_xy(text_x, y0 + pad)
        pdf.set_text_color(*pal.dark)
        pdf.set_font("DejaVu", "B", 10)
        pdf.write(line_h, f"{title}. ")
        pdf.set_text_color(*pal.ink)
        pdf.set_font("DejaVu", "", 10)
        pdf.write(line_h, text)

        pdf.set_left_margin(saved_lmargin)
        pdf.set_right_margin(saved_rmargin)
        pdf.set_y(y0 + height)
        pdf.ln(3)

    def kv_block(self, pairs):
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        for key, val in pairs:
            open_item, val = self.pending(val)
            if open_item:
                val = f"A definir: {val}"
            if pdf.get_y() > p.height - 45:
                pdf.add_page()
            y0 = pdf.get_y()
            # filete da cor de marca à esquerda da chave
            pdf.set_fill_color(*pal.accent)
            pdf.rect(p.margin, y0 + 0.6, 1.4, 4.2, style="F")
            pdf.set_xy(p.margin + 4, y0)
            pdf.set_font("Mono", "", 9.5)
            pdf.set_text_color(*pal.brand)
            pdf.multi_cell(p.content_width - 4, 5.4, key, align="L")
            pdf.set_font("DejaVu", "", 10)
            pdf.set_text_color(*pal.ink)
            pdf.set_x(p.margin + 4)
            pdf.multi_cell(p.content_width - 4, 5.2, val, align="L")
            pdf.ln(2.5)
        pdf.ln(0.5)

    def table_block(self, spec):
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        header = [self._inline_pending(str(c)) for c in spec["header"]]
        rows = [[self._inline_pending(str(c)) for c in row] for row in spec["rows"]]
        widths = spec.get("widths", [p.content_width / len(header)] * len(header))
        line_h = 5.2

        def row_height(cells):
            maxlines = 1
            for c, w in zip(cells, widths):
                pdf.set_font("DejaVu", "", 9.5)
                lines = pdf.multi_cell(w - 4, line_h, str(c),
                                       dry_run=True, output="LINES")
                maxlines = max(maxlines, len(lines))
            return maxlines * line_h + 3.2

        def draw_row(cells, head=False, zebra=False):
            h = row_height(cells)
            if pdf.get_y() + h > p.height - 25:
                pdf.add_page()
                draw_header()
            x = p.margin
            y = pdf.get_y()
            if head:
                pdf.set_fill_color(*pal.dark)
                pdf.rect(x, y, p.content_width, h, style="F")
                pdf.set_text_color(*pal.white)
                pdf.set_font("DejaVu", "B", 9.5)
            else:
                if zebra:
                    pdf.set_fill_color(*pal.zebra)
                    pdf.rect(x, y, p.content_width, h, style="F")
                pdf.set_draw_color(*pal.rule)
                pdf.set_line_width(0.2)
                pdf.line(x, y + h, x + p.content_width, y + h)
                pdf.set_text_color(*pal.ink)
                pdf.set_font("DejaVu", "", 9.5)
            for c, w in zip(cells, widths):
                pdf.set_xy(x + 2, y + 1.6)
                pdf.multi_cell(w - 4, line_h, str(c), align="L")
                x += w
                pdf.set_xy(x, y)
            pdf.set_y(y + h)

        def draw_header():
            draw_row(header, head=True)

        pdf.ln(1.5)
        draw_header()
        for i, r in enumerate(rows):
            draw_row(r, zebra=(i % 2 == 1))
        # borda externa sutil ao redor da tabela inteira não é trivial com
        # quebra de página; mantemos as linhas inferiores por linha.
        pdf.ln(4)

    # -- blocos de identidade visual (versão para o documento A4) ----------
    #
    # No tipo "slides" estes blocos têm desenho próprio (grade da área de
    # proteção, amostras grandes, especimen). Aqui valem como registro: a
    # imagem no tamanho da coluna, as cores em amostras pequenas e a fonte
    # como texto.

    def image_block(self, spec: dict, clearspace: bool = False):
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        path = self._asset(spec.get("path", ""))
        caption = spec.get("caption") or spec.get("path", "")
        if clearspace:
            ratio = float(spec.get("ratio") or 0.5)
            label = "½H" if abs(ratio - 0.5) < 0.01 else f"{ratio:g} H"
            caption = spec.get("caption") or (
                f"Área de proteção: respiro mínimo de {label} (H é a altura do "
                f"símbolo) nos quatro lados.")
        pdf.ln(1)
        drawn = False
        if path:
            try:
                pdf.image(str(path), x=p.margin, y=pdf.get_y(), h=48,
                          keep_aspect_ratio=True)
                pdf.ln(50)
                drawn = True
            except (RuntimeError, ValueError):
                drawn = False
        if not drawn:
            pdf.set_font("DejaVu", "", 9.5)
            pdf.set_text_color(*pal.muted)
            pdf.multi_cell(p.content_width, 5.4,
                           f"[imagem não disponível: {spec.get('path', '—')}]")
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*pal.muted)
        pdf.multi_cell(p.content_width, 5, caption)
        pdf.ln(2)

    def _asset(self, rel: str):
        from pathlib import Path
        if not rel:
            return None
        path = Path(rel).expanduser()
        if not path.is_absolute():
            root = self.theme.assets_root
            if not root:
                return None
            path = Path(root).expanduser() / rel
        return path if path.is_file() else None

    def swatch_table(self, spec: dict):
        """Amostras pequenas com nome e código, em linhas de seis."""
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        items = spec["items"]
        per_row = 6
        chip = (p.content_width - (per_row - 1) * 3) / per_row
        pdf.ln(1)
        for start in range(0, len(items), per_row):
            row = items[start:start + per_row]
            top = pdf.get_y()
            if top + chip + 14 > p.height - 24:
                pdf.add_page()
                top = pdf.get_y()
            for i, item in enumerate(row):
                x = p.margin + i * (chip + 3)
                h = item["hex"].strip().lstrip("#")
                rgb = tuple(int(h[j:j + 2], 16) for j in (0, 2, 4))
                pdf.set_fill_color(*rgb)
                pdf.set_draw_color(*pal.rule)
                pdf.set_line_width(0.2)
                pdf.rect(x, top, chip, chip * 0.7, style="DF")
                pdf.set_xy(x, top + chip * 0.7 + 1)
                pdf.set_font("Mono", "", 7)
                pdf.set_text_color(*pal.brand)
                pdf.cell(chip, 3.6, item["hex"].upper())
                pdf.set_xy(x, top + chip * 0.7 + 4.6)
                pdf.set_font("DejaVu", "", 6.5)
                pdf.set_text_color(*pal.muted)
                pdf.multi_cell(chip, 3.2, item["name"].lstrip("-$@"))
            pdf.set_y(top + chip * 0.7 + 13)
        pdf.ln(1)

    def specimen_lines(self, spec: dict):
        pdf, t = self.pdf, self.theme
        p, pal = t.page, t.palette
        parts = [spec["font"]]
        if spec.get("role"):
            parts.append(f"papel: {spec['role']}")
        if spec.get("weights"):
            parts.append(f"pesos: {spec['weights']}")
        if spec.get("source"):
            parts.append(f"declarada em {spec['source']}")
        pdf.set_font("DejaVu", "B", 11)
        pdf.set_text_color(*pal.dark)
        pdf.multi_cell(p.content_width, 6, " · ".join(parts))
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(*pal.muted)
        pdf.multi_cell(p.content_width, 5,
                       "O arquivo da fonte não está no repositório; o PDF usa a "
                       "fonte do documento.")
        pdf.ln(2)
