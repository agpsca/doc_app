"""Servidor MCP do doc_app.

Expõe o doc_app como ferramentas para um agente (ex.: Kiro). O agente lê o
código do app com as próprias ferramentas e escreve o texto das seções; o
doc_app extrai os fatos, valida o formato, grava no workspace e gera o PDF.
Assim o doc_app não precisa de chave de API nem de modelo próprio.

Uso (configurado no cliente MCP):
    uv run --project <raiz do doc_app> doc-app-mcp

Fala MCP por stdio: nada aqui pode escrever em stdout além do protocolo.
"""

from __future__ import annotations

import functools
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import core, sections
from .dsl import BLOCK_TYPES
from .theme import DOC_TYPES

INSTRUCTIONS = """\
O doc_app gera documentação em PDF de um app (repositório local).

Fluxo recomendado:
1. inspect_app(app_path): fatos do app e documentos já existentes.
2. create_doc(app_path, doc_type): cria o documento inicial com os fatos
   extraídos dos arquivos. Tipos: brand (uso e regras), development (código),
   full (os dois). Se já existir, é reaproveitado.
3. list_sections(app_path, doc_type): seções e quantos trechos (TODO) cada uma
   tem, com uma dica de onde procurar a informação.
4. Para cada seção com TODO: read_section, leia os arquivos do app com as suas
   próprias ferramentas e depois write_section com o corpo completo da seção.
   Para títulos com (TODO), passe também `title`. Use add_section para criar
   subseções (por exemplo, uma por módulo) e remove_section para as que não se
   aplicam ao app.
5. build_pdf(app_path, doc_type) e informe o caminho do PDF ao usuário.

Regras de conteúdo:
- Escreva em português do Brasil, frases diretas, sem marketing.
- Só afirme o que o código ou os arquivos confirmam. Quando citar uma regra ou
  comportamento, diga o arquivo que o garante (ex.: "src/lib/nav.ts").
- Se não der para confirmar algo, mantenha um trecho "(TODO) ..." explicando o
  que falta, em vez de inventar.
- Não apague fatos que já estão no documento (tabelas de scripts, dependências,
  variáveis, árvore de pastas) a não ser que estejam errados.
- Não copie segredos: valores de .env, tokens, senhas, chaves.

Formato dos blocos (cada bloco é um objeto de uma única chave):
  {"p": "parágrafo"}
  {"h3": "subtítulo dentro da seção"}
  {"bullet": ["item", "item"]}          {"num": ["passo 1", "passo 2"]}
  {"code": "linha 1\\nlinha 2"}
  {"callout": {"title": "Regra", "text": "..."}}
  {"kv": [{"key": "NOME", "value": "descrição"}]}
  {"table": {"header": ["A", "B"], "rows": [["a1", "b1"]], "widths": [50, 120]}}
h1/h2 não vão dentro de blocos: são os títulos das seções. A largura útil da
página é 170 mm (soma de widths).
"""

server = MCPServer(name="doc-app", title="doc_app",
                   description="Gera documentação em PDF de apps locais.",
                   instructions=INSTRUCTIONS)


def tool(fn):
    """Registra a ferramenta. Erros previstos (caminho inválido, seção que não
    existe, blocos fora do formato) voltam para o agente com a mensagem
    completa, para ele corrigir a chamada."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (sections.SectionError, ValueError, FileNotFoundError) as exc:
            raise ToolError(str(exc)) from exc
    return server.tool()(wrapper)


def _ctx(app_path: str, doc_type: str):
    app = core.app_dir(app_path)
    core.check_doc_type(doc_type)
    return app, core.doc_path(app.name, doc_type)


def _summary(s: sections.Section) -> dict:
    out: dict[str, Any] = {"id": s.id, "level": s.level, "title": s.title,
                           "todos": s.todos}
    if s.todos and (hint := sections.hint_for(s.title)):
        out["hint"] = hint
    return out


@tool
def inspect_app(app_path: str) -> dict:
    """Fatos do app (stack, tipo, o que foi encontrado) e documentos já no cache."""
    from .extract import extract_facts
    app = core.app_dir(app_path)
    f = extract_facts(app)
    existing = {t: str(core.doc_path(app.name, t)) for t in DOC_TYPES
                if core.doc_path(app.name, t).exists()}
    return {
        "app": app.name,
        "path": str(app),
        "kind": f.stack.kind,
        "stack": f.stack.summary(),
        "readme_intro": f.readme_intro,
        "scripts": len(f.scripts),
        "dependencies": len(f.dependencies) + len(f.dev_dependencies),
        "env_vars": [v.key for v in f.env_vars],
        "top_dirs": [d for d, _ in f.top_dirs],
        "git_hooks": [h for h, _ in f.hooks],
        "ci_workflows": [w.name for w in f.workflows],
        "docker": f.docker is not None,
        "warnings": f.warnings,
        "docs_in_cache": existing,
        "doc_types": list(DOC_TYPES),
    }


@tool
def create_doc(app_path: str, doc_type: str = "full", overwrite: bool = False) -> dict:
    """Cria o documento inicial do app com os fatos extraídos dos arquivos.

    doc_type: brand, development ou full. Com overwrite=false, um documento já
    existente é mantido (para não perder edições).
    """
    app = core.app_dir(app_path)
    res = core.create_doc(app, doc_type, overwrite=overwrite)
    out = {"path": str(res.path), "created": res.created, "todos": res.todos,
           "kind": res.facts.stack.kind}
    if res.colors:
        out["brand_colors"] = res.colors.palette_overrides()
    if not res.created:
        out["note"] = "Documento já existia e foi mantido. Use overwrite=true para recriar."
    return out


@tool
def list_sections(app_path: str, doc_type: str = "full") -> dict:
    """Seções do documento, com a contagem de trechos (TODO) e dicas de onde
    procurar a informação nas seções pendentes."""
    _, dp = _ctx(app_path, doc_type)
    raw = sections.load_raw(dp)
    secs = sections.list_sections(raw)
    return {"sections": [_summary(s) for s in secs],
            "todos_total": sum(s.todos for s in secs)}


@tool
def read_section(app_path: str, section_id: str, doc_type: str = "full") -> dict:
    """Conteúdo atual de uma seção (título e blocos do corpo)."""
    _, dp = _ctx(app_path, doc_type)
    raw = sections.load_raw(dp)
    s = sections.find(raw, section_id)
    view = sections.section_view(raw, s)
    if hint := sections.hint_for(s.title):
        view["hint"] = hint
    return view


@tool
def write_section(app_path: str, section_id: str, blocks: list[dict],
                  doc_type: str = "full", title: str | None = None) -> dict:
    """Substitui o corpo de uma seção pelos `blocks` (e o título, se `title`).

    O corpo de um h1 vai só até a primeira subseção h2; as subseções não são
    alteradas. Os blocos são validados antes de gravar; em caso de erro nada é
    gravado e a mensagem diz o que corrigir.
    """
    _, dp = _ctx(app_path, doc_type)
    raw = sections.load_raw(dp)
    s = sections.write_section(raw, section_id, blocks, title)
    sections.save_raw(dp, raw)
    return {"saved": _summary(s),
            "todos_left": sum(x.todos for x in sections.list_sections(raw))}


@tool
def add_section(app_path: str, title: str, blocks: list[dict], level: int = 2,
                after_section_id: str | None = None, doc_type: str = "full") -> dict:
    """Cria uma seção nova. level=2 depois de um h1 entra no fim das subseções
    dele; level=1 entra depois do grupo inteiro. Sem after_section_id, vai para
    o fim. A numeração é refeita automaticamente."""
    _, dp = _ctx(app_path, doc_type)
    raw = sections.load_raw(dp)
    s = sections.add_section(raw, after_section_id, level, title, blocks)
    sections.save_raw(dp, raw)
    return {"added": _summary(s),
            "sections": [x.id + " " + x.title for x in sections.list_sections(raw)]}


@tool
def remove_section(app_path: str, section_id: str, doc_type: str = "full") -> dict:
    """Remove uma seção que não se aplica ao app. Remover um h1 remove também
    as subseções dele. A numeração é refeita automaticamente."""
    _, dp = _ctx(app_path, doc_type)
    raw = sections.load_raw(dp)
    removed = sections.remove_section(raw, section_id)
    sections.save_raw(dp, raw)
    return {"removed": removed.title,
            "sections": [x.id + " " + x.title for x in sections.list_sections(raw)]}


@tool
def build_pdf(app_path: str, doc_type: str = "full", output_path: str | None = None,
              mark: str | None = None) -> dict:
    """Gera o PDF. Sem output_path, salva em ~/Desktop/<app>-<tipo>.pdf.
    `mark` (ex.: "Uso interno") adiciona marca d'água e aviso de restrição."""
    app, _ = _ctx(app_path, doc_type)
    out = (core.normalize_output(output_path, app.name, doc_type) if output_path
           else core.default_output(app.name, doc_type))
    res = core.build(app.name, doc_type, out, mark)
    raw = sections.load_raw(core.doc_path(app.name, doc_type))
    return {"pdf": str(res.output), "blocks": res.blocks,
            "todos_left": sum(s.todos for s in sections.list_sections(raw))}


@tool
def block_types() -> dict:
    """Tipos de bloco aceitos e o formato de cada um."""
    return {"types": sorted(BLOCK_TYPES), "format": INSTRUCTIONS.split(
        "Formato dos blocos")[1].strip()}


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
