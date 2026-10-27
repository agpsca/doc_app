#!/usr/bin/env python
"""Checagem do guia de identidade visual (tipo "slides").

Monta um app de mentira com marca (logo e símbolo em SVG, variáveis de cor,
fontes do next/font e metadados), confere o que a detecção afirma e gera a
apresentação de verdade, checando o que cada slide deve conter.

Uso:
    uv run python scripts/check_slides.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from doc_app import core
from doc_app.dsl import validate_block
from doc_app.extract import extract_facts
from doc_app.identity import detect_identity
from doc_app.skeleton import skeleton_blocks
from doc_app.theme import DOC_TYPES, SLIDE_PAGE

LOGO = """\
<svg xmlns="http://www.w3.org/2000/svg" width="240" height="120" viewBox="0 0 240 120">
  <rect x="10" y="10" width="100" height="100" rx="18" fill="#00664E"/>
  <rect x="130" y="40" width="90" height="40" fill="#05DC7F"/>
</svg>
"""
ICON = """\
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect x="48" y="48" width="416" height="416" rx="72" fill="#00664E"/>
</svg>
"""
GLOBALS_CSS = """\
:root {
  --color-brand-dark-green: #152E2B;
  --color-brand-green: #00664E;
  --color-brand-spring-green: #05DC7F;
  --background: #FFFFFF;
  --foreground: #202020;
  --radius: 10px;
  --radius-lg: var(--radius);
  --font-sans: var(--font-space-grotesk);
}
.dark {
  --color-brand-green: #0A3D2F;   /* tema escuro: deve ser ignorado */
}
"""
LAYOUT_TSX = """\
import { Geist_Mono, Space_Grotesk } from "next/font/google";

const sans = Space_Grotesk({ subsets: ["latin"], weight: ["400", "500"],
                             variable: "--font-sans" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata = {
  title: { default: "lojinha", template: "%s — lojinha" },
  description: "Gestão de pedidos em um só lugar",
};

export default function RootLayout({ children }) {
  return <html lang="pt-BR">{children}</html>;
}
"""


LOGIN_TSX = """\
"use client";

export function LoginForm() {
  return (
    <form>
      <h1>{"Entre na sua conta"}</h1>
      <p>{"Use suas credenciais da lojinha"}</p>
      <input placeholder="Seu e-mail de trabalho" />
      <span>{"Informe um e-mail válido."}</span>
      <span>{"Informe sua senha."}</span>
      <button>{"Entrar agora"}</button>
      <small>{"Esqueceu a senha? A gente te ajuda."}</small>
    </form>
  );
}
"""


def build_app(root: Path) -> Path:
    app = root / "lojinha"
    (app / "public" / "Brand").mkdir(parents=True)
    (app / "src" / "app").mkdir(parents=True)
    (app / "src" / "features" / "auth").mkdir(parents=True)
    (app / "public" / "Brand" / "logo.svg").write_text(LOGO, encoding="utf-8")
    (app / "public" / "Brand" / "icon.svg").write_text(ICON, encoding="utf-8")
    (app / "src" / "app" / "globals.css").write_text(GLOBALS_CSS, encoding="utf-8")
    (app / "src" / "app" / "layout.tsx").write_text(LAYOUT_TSX, encoding="utf-8")
    (app / "src" / "features" / "auth" / "login-form.tsx").write_text(
        LOGIN_TSX, encoding="utf-8")
    (app / "package.json").write_text(
        '{"name": "lojinha", "dependencies": {"next": "16.0.0", "react": "19.0.0"}}',
        encoding="utf-8")
    return app


def check_identity(app: Path):
    ident = detect_identity(app)
    assert not ident.empty
    assert ident.title == "lojinha", ident.title
    assert ident.description == "Gestão de pedidos em um só lugar", ident.description
    assert ident.lang == "pt-BR", ident.lang
    # cada metadado carrega o arquivo que o declara
    meta = {label: (value, source) for label, value, source in ident.meta}
    assert meta["Template de título"][0] == "%s — lojinha", meta
    assert meta["Descrição"][1] == "src/app/layout.tsx", meta
    assert meta["Nome declarado"][1] == "package.json", meta

    # a assinatura é o arquivo largo; o símbolo, o quadrado
    assert ident.signature().path == "public/Brand/logo.svg", ident.signature()
    assert ident.symbol().path == "public/Brand/icon.svg", ident.symbol()
    assert ident.signature().size == "240 × 120"

    # cores da marca em ordem de luminosidade, sem as do tema escuro
    assert [c.hex for c in ident.brand_colors] == ["#152E2B", "#00664E", "#05DC7F"], \
        ident.brand_colors
    assert all(c.source.endswith("globals.css") for c in ident.brand_colors)
    assert "#0A3D2F" not in [c.hex for c in ident.brand_colors]
    assert [c.hex for c in ident.semantic_colors] == ["#FFFFFF", "#202020"]

    fonts = {f.name: f.role for f in ident.fonts}
    assert fonts == {"Space Grotesk": "sans", "Geist Mono": "mono"}, fonts
    assert next(f for f in ident.fonts if f.name == "Space Grotesk").weights == "400, 500"
    assert ("Raio", "--radius", "10px") in ident.tokens, ident.tokens
    assert any("favicon" in m for m in ident.missing), ident.missing

    # o texto de interface é a evidência de tom de voz, e o agente precisa
    # receber o arquivo certo: o login, não o layout
    assert ident.ui_copy, "nenhum arquivo de texto de interface encontrado"
    first = ident.ui_copy[0]
    assert first.path.endswith("login-form.tsx"), first.path
    assert "Use suas credenciais da lojinha" in first.samples, first.samples
    assert all(s.lower() != "use client" for s in first.samples), first.samples
    return ident


def check_blocks(app: Path, ident):
    facts = extract_facts(app)
    blocks = skeleton_blocks(facts, "slides", ident)
    errors = [e for i, b in enumerate(blocks) for e in validate_block(b, f"bloco {i}")]
    assert not errors, errors

    kinds = [next(iter(b)) for b in blocks]
    for needed in ("logo", "clearspace", "swatches", "specimen"):
        assert needed in kinds, (needed, kinds)
    text = str(blocks)
    assert "Gestão de pedidos em um só lugar" in text
    assert "public/Brand/icon.syg" not in text          # caminho não inventado
    assert "public/Brand/icon.svg" in text
    assert "Space Grotesk" in text and "400, 500" in text
    assert "#05DC7F" in text
    # nada de plural "(s)" nem de instrução ao autor dentro do deck
    import re
    assert not re.search(r"\w\(s\)|\(is\)|\(ões\)", text), text[:200]
    assert not re.search(r"\b(Descreva|Explique|Complete|Documente)\b", text)
    # o guia pergunta o que nenhum arquivo responde, e nada além disso
    todos = [b for b in blocks if "(TODO)" in str(b)]
    assert 3 <= len(todos) <= 8, todos
    assert all("h1" not in b and "h2" not in b for b in todos), todos
    return blocks


def check_deck(app: Path, out_dir: Path):
    result = core.create_doc(app, "slides", overwrite=True)
    assert result.created and result.path.name == "slides.yaml"
    raw = result.path.read_text(encoding="utf-8")
    assert f"app_path: {app}" in raw, "o YAML precisa guardar a pasta do app"

    out = core.build(app.name, "slides", out_dir / "deck.pdf", mark="Uso interno")
    assert out.output.is_file() and out.output.stat().st_size > 10_000
    assert out.theme.page is SLIDE_PAGE or out.theme.page.width > out.theme.page.height
    assert out.theme.classification == "Uso interno"

    # o mesmo conteúdo também gera o PDF A4, com os blocos de marca em versão
    # equivalente (imagem, amostras pequenas, texto)
    import yaml
    from doc_app.loader import save_document
    doc = yaml.safe_load(result.path.read_text(encoding="utf-8"))
    save_document(core.doc_path(app.name, "brand"), doc["blocks"], "brand",
                  theme_overrides=doc.get("theme"), app_path=doc["app_path"])
    a4 = core.build(app.name, "brand", out_dir / "a4.pdf")
    assert a4.output.is_file() and a4.theme.page.height > a4.theme.page.width
    return out


def check_hints(app: Path, ident) -> None:
    """Toda seção com (TODO) precisa de uma dica: é o que permite ao agente
    preencher o guia sozinho, em qualquer repositório."""
    from doc_app import sections
    result = core.create_doc(app, "slides", overwrite=True)
    raw = sections.load_raw(result.path)
    pending = [s for s in sections.list_sections(raw) if s.todos]
    assert pending, "o guia deveria ter seções a completar"
    without = [s.title for s in pending if not sections.hint_for(s.title)]
    assert not without, f"seções com (TODO) e sem dica: {without}"
    # a dica de tom de voz manda ler o texto de interface, que a detecção achou
    voice = next(s for s in pending if "Tom de voz" in s.title)
    assert "interface" in sections.hint_for(voice.title)
    assert ident.ui_copy and ident.ui_copy[0].samples, ident.ui_copy
    assert all("use client" != s.lower() for c in ident.ui_copy for s in c.samples)


def check_generic_app(root: Path) -> None:
    """A mesma detecção num app sem Next: índice HTML, Sass e Google Fonts.

    É o que garante que o guia não depende de um framework específico.
    """
    app = root / "painel"
    (app / "src" / "styles").mkdir(parents=True)
    (app / "public").mkdir()
    (app / "index.html").write_text(
        '<!doctype html><html lang="es"><head><title>Panel de ventas</title>'
        '<meta name="description" content="Control de ventas y stock">'
        '<link href="https://fonts.googleapis.com/css2?family=Roboto+Slab:'
        'wght@400;700&display=swap" rel="stylesheet"></head><body></body></html>',
        encoding="utf-8")
    (app / "public" / "logo-marca.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100"'
        ' viewBox="0 0 300 100"><rect width="300" height="100" fill="#C2185B"/></svg>',
        encoding="utf-8")
    (app / "src" / "styles" / "main.scss").write_text(
        '$primary: #C2185B;\n$font-family-sans-serif: "Roboto Slab", serif;\n'
        '$font-size-base: 1rem;\n', encoding="utf-8")

    ident = detect_identity(app)
    assert ident.title == "Panel de ventas", ident.title
    assert ident.description == "Control de ventas y stock", ident.description
    assert ident.lang == "es", ident.lang
    assert [s for _, _, s in ident.meta] == ["index.html"] * 3, ident.meta
    names = {f.name: f.role for f in ident.fonts}
    assert "Roboto Slab" in names, names
    assert names["Roboto Slab"] == "sans", names
    assert "1rem" not in names, names                 # font-size não é família
    assert ident.signature().path == "public/logo-marca.svg", ident.signature()
    assert [c.hex for c in ident.brand_colors] == ["#C2185B"], ident.brand_colors

    facts = extract_facts(app)
    blocks = skeleton_blocks(facts, "slides", ident)
    errors = [e for i, b in enumerate(blocks) for e in validate_block(b, f"bloco {i}")]
    assert not errors, errors
    assert "Panel de ventas" in str(blocks)
    assert any("swatches" in b for b in blocks) and any("logo" in b for b in blocks)


def main() -> int:
    assert "slides" in DOC_TYPES, "o tipo slides precisa estar no menu"
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        app = build_app(tmp)
        ident = check_identity(app)
        check_blocks(app, ident)
        check_generic_app(tmp)
        try:
            out = check_deck(app, tmp)
            check_hints(app, ident)
        finally:
            for doc_type in ("slides", "brand"):
                core.doc_path(app.name, doc_type).unlink(missing_ok=True)
            cache = core.cache_dir(app.name)
            if cache.is_dir() and not any(cache.iterdir()):
                cache.rmdir()
    print(f"ok: identidade em app Next e em app genérico, blocos de marca "
          f"válidos, dicas por seção e deck gerado ({out.blocks} blocos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
