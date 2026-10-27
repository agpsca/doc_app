"""Monta o esqueleto da documentação a partir dos fatos extraídos.

Entra pronto tudo o que os arquivos confirmam: stack, scripts, dependências,
variáveis, árvore de pastas, hooks, CI, Docker, rotas, módulos e o texto do
próprio README, seção por seção. Fica marcado com (TODO) só o que nenhum
arquivo do repositório responde, para ser escrito por uma pessoa ou por um
agente via MCP.

Tipos:
  brand        visão geral, como começar, uso, regras, qualidade, Docker, lacunas
  development  visão geral, como começar, código, ferramentas, dependências,
               módulos, APIs, qualidade, Docker
  full         os dois, sem repetir seções em comum
"""

from __future__ import annotations

import re

from .extract import ProjectFacts
from .identity import Asset, Identity
from .md import md_blocks, plain_markdown

TODO = "(TODO)"

# Seções do README que uma seção do documento aproveita, na ordem de prioridade.
# O terceiro item limita os tipos de bloco aproveitados, quando o quadro
# equivalente já entra no documento como fato extraído.
_README_TARGETS: list[tuple[str, re.Pattern, tuple[str, ...] | None]] = [
    (
        "rules",
        re.compile(
            r"decis|arquitetur|regras|conven|padr[õo]es|invariant|"
            r"n[ãa]o s[ãa]o [óo]bvi|princ[íi]pios",
            re.I,
        ),
        None,
    ),
    (
        "usage",
        re.compile(
            r"como (usar|se usa|funciona)|uso\b|funcionalidad|telas|"
            r"fluxos?\b|navega|features|endpoints|rotas",
            re.I,
        ),
        None,
    ),
    ("apis", re.compile(r"\bapis?\b|integra|contrato|openapi|webhook", re.I), None),
    ("modules", re.compile(r"m[óo]dulos|dom[íi]nios|componentes", re.I), None),
    (
        "org",
        re.compile(r"organiza|estrutura|pastas|layout do (projeto|c[óo]digo)", re.I),
        None,
    ),
    (
        "quality",
        re.compile(
            r"qualidade|testes?|lint|\bci\b|checagens|verifica|"
            r"scripts?",
            re.I,
        ),
        ("p", "bullet", "num", "h3"),
    ),
    (
        "gaps",
        re.compile(
            r"lacunas|limita|pend[êe]nc|roadmap|known issues|d[íi]vida|"
            r"pr[óo]ximos passos|falta",
            re.I,
        ),
        None,
    ),
]

# Seções do README que o documento já cobre com fatos extraídos, ou que não
# dizem nada sobre o app.
_SKIP_SECTION = re.compile(
    r"^(stack|licen|contribu|sum[áa]rio|[íi]ndice|changelog|"
    r"docker|instala|requisitos|pr[ée][\s-]?requisitos|"
    r"vari[áa]veis|come[cç]|autor|cr[ée]dito)",
    re.I,
)


def skeleton_blocks(facts: ProjectFacts, doc_type: str,
                    identity: Identity | None = None) -> list[dict]:
    md = readme_targets(facts)
    if doc_type == "slides":
        return _number_headings(_slides(facts, identity or Identity(), md))

    brand = doc_type in ("brand", "full")
    dev = doc_type in ("development", "full")

    blocks = _overview(facts, md) + _getting_started(facts)
    if brand:
        blocks += _usage(facts, md) + _architecture_rules(facts, md)
    if dev:
        blocks += (
            _code_organization(facts, md)
            + _tools(facts)
            + _dependencies(facts)
            + _modules(facts, md)
            + _apis(facts, md)
        )
    blocks += _quality(facts, md) + _docker(facts)
    if brand:
        blocks += _gaps(facts, md)
    elif facts.warnings:
        blocks += [{"h1": "Inconsistências encontradas"}, {"bullet": facts.warnings}]
    return _number_headings(blocks)


# --- slides: guia de identidade visual -------------------------------------


def _slides(facts: ProjectFacts, ident: Identity, md: dict) -> list[dict]:
    """Um slide por subseção. Entra o que os arquivos provam; o que depende de
    decisão de marca (tom de voz, usos indevidos) fica (TODO)."""
    blocks: list[dict] = [{"h1": "A marca"}]
    blocks += _slide_positioning(facts, ident, md)
    blocks += _slide_naming(facts, ident)

    visual: list[dict] = []
    signature, symbol = ident.signature(), ident.symbol()
    if signature:
        # variantes da mesma marca ficam na mesma pasta; outra pasta costuma
        # ser outra marca (parceiro, selo), e não entra na amostra
        folder = signature.path.rpartition("/")[0]

        def same_folder(surface: str) -> Asset | None:
            return next((a for a in ident.assets
                         if a.surface == surface and a.renderable
                         and a.path.rpartition("/")[0] == folder), None)

        on_light, on_dark = same_folder("light"), same_folder("dark")
        main = on_light or signature
        logo = {"path": main.path, "on": "both",
                "caption": f"{main.path} · {main.size} · {main.format.upper()}"}
        if on_dark:
            logo["path_dark"] = on_dark.path
            logo["caption"] += f" · fundo escuro: {on_dark.path}"
        visual += [{"h2": "Assinatura"}, {"logo": logo}]
        used = {logo["path"], logo.get("path_dark")}
        variants = [a for a in ident.assets if a.path not in used]
        if variants:
            visual.append({"table": {
                "header": ["Arquivo", "Papel", "Formato", "Tamanho"],
                "rows": [[a.path,
                          a.role + (f" (sobre {a.surface})" if a.surface else ""),
                          a.format.upper(), a.size] for a in variants]}})
    if symbol:
        visual += [
            {"h2": "Símbolo"},
            {"logo": {"path": symbol.path,
                      "caption": f"{symbol.path} · {symbol.size} · "
                                 f"{symbol.format.upper()}"
                                 + ("" if symbol.is_vector
                                    else " (bitmap: não escala sem perda)")}},
            {"h2": "Área de proteção"},
            {"clearspace": {"path": symbol.path, "ratio": 0.5}},
            {"p": "O desenho assume meia altura do símbolo, que é a convenção "
                  "mais comum. Nenhum arquivo do repositório declara esse valor."},
            {"p": f"{TODO} Respiro mínimo oficial da marca."},
        ]
    if ident.brand_colors:
        visual += [
            {"h2": "Cores da marca"},
            {"swatches": {"items": [{"name": _short_token(c.name), "hex": c.hex,
                                     "source": c.source.rsplit("/", 1)[-1]}
                                    for c in ident.brand_colors]}},
        ]
    if ident.semantic_colors:
        visual += [
            {"h2": "Cores da interface"},
            {"p": "Cores semânticas: um token por intenção, consumido pelos "
                  "componentes."},
            {"swatches": {"items": [{"name": _short_token(c.name), "hex": c.hex}
                                    for c in ident.semantic_colors[:12]]}},
        ]
    for font in ident.fonts[:3]:
        visual += [
            {"h2": f"Tipografia · {font.name}"},
            {"specimen": {"font": font.name, "role": font.role,
                          "weights": font.weights, "source": font.source,
                          "sample": "Aa Bb Cc 0123456789"}},
        ]
    if ident.tokens:
        groups = sorted({g for g, _, _ in ident.tokens})
        visual += [
            {"h2": "Forma e espaçamento"},
            {"p": f"Tokens declarados nos estilos ({', '.join(groups).lower()}):"},
            {"table": {"header": ["Grupo", "Token", "Valor"],
                       "rows": [[g, n, v] for g, n, v in ident.tokens]}},
        ]
    if visual:
        blocks += [{"h1": "Identidade visual"}] + visual + _slide_misuse(facts)
    blocks += _slide_governance(facts, ident)
    blocks += _slide_gaps(facts, ident, md)
    return blocks


def _short_token(name: str) -> str:
    """Nome curto da variável, para caber embaixo da amostra de cor."""
    short = name.lstrip("-$@")
    for prefix in ("color-", "colour-", "brand-color-"):
        if short.startswith(prefix):
            short = short[len(prefix):]
    return short


def _slide_positioning(facts: ProjectFacts, ident: Identity, md: dict) -> list[dict]:
    blocks: list[dict] = [{"h2": "Posicionamento"}]
    phrase = ident.description or facts.description or facts.readme_intro
    if phrase:
        source = next((src for label, value, src in ident.meta
                       if value == phrase), None)
        origin = (f" É assim que o produto se descreve no código ({source})."
                  if source else
                  " É a frase que o repositório usa para se apresentar.")
        blocks.append({"p": f"“{phrase.rstrip('.')}.”{origin}"})
    else:
        blocks.append({"p": f"{TODO} A frase que define o produto: o que é, "
                            "para quem e o que o torna diferente."})
    blocks += [
        {"p": f"{TODO} Público, promessa e o que a marca não é."},
        {"h2": "Tom de voz"},
        {"p": f"{TODO} O que dizer e o que evitar."},
    ]
    return blocks


def _slide_naming(facts: ProjectFacts, ident: Identity) -> list[dict]:
    rows = [["Nome no código", facts.name, "pasta do projeto"]]
    rows += [[label, value, source] for label, value, source in ident.meta]
    if facts.stack.framework:
        rows.append(["Framework", facts.stack.framework, "arquivo de dependências"])
    blocks: list[dict] = [
        {"h2": "Nome e escrita"},
        {"table": {"header": ["Item", "Valor", "Declarado em"], "rows": rows}},
        {"p": f"{TODO} Grafia oficial: caixa, hífen e pronúncia."},
    ]
    return blocks


def _slide_misuse(facts: ProjectFacts) -> list[dict]:
    """Usos indevidos: o código só prova as regras que ele verifica."""
    blocks: list[dict] = [{"h2": "Usos indevidos"}]
    guarded = [f"{pattern} → {check}" for pattern, check in facts.staged_checks]
    if guarded:
        blocks += [
            {"p": "As checagens do commit já protegem estes arquivos:"},
            {"bullet": guarded[:8]},
        ]
    blocks.append({"p": f"{TODO} Proibições: deformar, recolorir, aplicar sem contraste, "
                        "recriar o símbolo."})
    return blocks


def _slide_governance(facts: ProjectFacts, ident: Identity) -> list[dict]:
    rows: list[list[str]] = [["Cores da marca", source]
                             for source in sorted({c.source
                                                   for c in ident.brand_colors})]
    rows += [[f"Fonte {font.name}", font.source.split(": ")[0]]
             for font in ident.fonts[:3]]
    rows += [[asset.role.capitalize(), asset.path] for asset in ident.assets[:4]]
    if not rows:
        return []
    blocks: list[dict] = [
        {"h1": "Governança"},
        {"h2": "Onde a marca mora no código"},
        {"table": {"header": ["Item", "Arquivo"], "rows": rows}},
    ]
    prefix = _run_prefix(facts)
    checks = [f"{prefix}{name}" for name, _ in facts.check_scripts]
    if checks or facts.hooks:
        items = [f"git {hook}: {cmds}" for hook, cmds in facts.hooks] + checks
        blocks += [
            {"h2": "O que protege a marca"},
            {"bullet": items[:10]},
            {"p": f"{TODO} Quem aprova uma mudança de marca e como ela entra "
                  "no código."},
        ]
    return blocks


def _slide_gaps(facts: ProjectFacts, ident: Identity, md: dict) -> list[dict]:
    items = list(ident.missing) + list(facts.warnings)
    gaps = [b for b in (md.get("gaps") or []) if "bullet" in b or "p" in b][:2]
    blocks: list[dict] = [{"h1": "Lacunas"}, {"h2": "O que falta decidir"}]
    if items:
        blocks.append({"bullet": items[:10]})
    blocks += gaps
    if not items and not gaps:
        blocks.append({"bullet": [f"{TODO} O que ainda falta na identidade."]})
    return blocks


# --- README ----------------------------------------------------------------


def readme_targets(facts: ProjectFacts) -> dict[str, list[dict]]:
    """Blocos do README por seção do documento.

    Cada seção do README é aproveitada no máximo uma vez. As subseções mais
    profundas entram como h3 da mesma seção do documento, e as que já viraram
    introdução, pré-requisitos ou instalação ficam de fora (com as subseções).
    """
    out: dict[str, list[dict]] = {}
    secs = facts.readme_sections
    i, blocked = 0, 99
    while i < len(secs):
        sec = secs[i]
        if sec.level > blocked:  # subseção de uma seção descartada
            i += 1
            continue
        blocked = 99
        target = None
        if sec.title and not sec.used and not _SKIP_SECTION.search(sec.title):
            target = next(
                (
                    t
                    for t in _README_TARGETS
                    if t[0] not in out and t[1].search(sec.title)
                ),
                None,
            )
        if target is None:
            blocked = sec.level if sec.level >= 2 else 99
            i += 1
            continue
        name, _, keep = target
        blocks = md_blocks(sec.body, keep=keep)
        i += 1
        while i < len(secs) and secs[i].level > sec.level:
            sub, i = secs[i], i + 1
            body = md_blocks(sub.body, keep=keep)
            if body and (title := plain_markdown(sub.title)):
                blocks.append({"h3": title})
            blocks += body
        if blocks:
            out[name] = blocks
    return out


# --- utilitários -----------------------------------------------------------


def _number_headings(blocks: list[dict]) -> list[dict]:
    """Prefixa h1 com 'N.' e h2 com 'N.M.' na ordem em que aparecem."""
    h1 = h2 = 0
    out: list[dict] = []
    for block in blocks:
        ((typ, content),) = block.items()
        if typ == "h1":
            h1, h2 = h1 + 1, 0
            out.append({"h1": f"{h1}. {content}"})
        elif typ == "h2":
            h2 += 1
            out.append({"h2": f"{h1}.{h2}. {content}"})
        else:
            out.append(block)
    return out


def _count(number: int, singular: str, plural: str) -> str:
    """"1 variável declarada" / "3 variáveis declaradas": sem "(s)" no meio."""
    return f"{number} {singular if number == 1 else plural}"


def _table(header: list[str], rows: list[list[str]], widths: list[int]) -> dict:
    return {"table": {"header": header, "widths": widths, "rows": rows}}


def _run_prefix(facts: ProjectFacts) -> str:
    pm = facts.stack.package_manager
    if pm in ("pnpm", "yarn", "bun"):
        return f"{pm} "
    if pm == "npm":
        return "npm run "
    return ""


def _shell_cmd(raw: str) -> str:
    """CMD/ENTRYPOINT do Dockerfile em forma de linha de comando."""
    if raw.strip().startswith("["):
        parts = re.findall(r'"([^"]*)"', raw)
        return " ".join(parts) if parts else raw.strip()
    return raw.strip()


# --- seções em comum -------------------------------------------------------


def _overview(facts: ProjectFacts, md: dict) -> list[dict]:
    intro = facts.description or facts.readme_intro
    rows = []
    s = facts.stack
    if s.framework:
        rows.append(["Framework", s.framework])
    if s.language:
        rows.append(["Linguagem", s.language])
    rows += [[cat, libs] for cat, libs in facts.libs]
    if s.package_manager:
        rows.append(["Pacotes", s.package_manager])
    rows += [["Infraestrutura", extra] for extra in s.extras]
    if not rows:
        rows.append(["—", f"{TODO} stack não reconhecida nos arquivos"])

    blocks: list[dict] = [{"h1": "Visão geral"}]
    if intro:
        blocks.append({"p": intro})
    else:
        blocks += [
            {
                "p": f"{TODO} O que é o {facts.name}, que problema resolve e para quem."
            },
            {
                "p": f"{TODO} Público, escopo atual e o que está fora do escopo."
            },
        ]
    blocks += [
        {"h2": "Stack"},
        _table(["Peça", "Escolha"], rows, [45, 125]),
    ]
    return blocks


def _getting_started(facts: ProjectFacts) -> list[dict]:
    blocks: list[dict] = [{"h1": "Como começar"}, {"h2": "Pré-requisitos"}]
    prereqs = facts.readme_prereqs + [
        p for p in facts.prereqs if p not in facts.readme_prereqs
    ]
    blocks.append(
        {"bullet": prereqs}
        if prereqs
        else {"bullet": [f"{TODO} Versões de runtime e ferramentas necessárias."]}
    )

    blocks.append({"h2": "Instalação"})
    if facts.setup_steps:
        blocks.append({"num": facts.setup_steps})
    if facts.setup_text:
        blocks.append({"p": facts.setup_text})
    code = facts.setup_code or _default_setup(facts)
    if code:
        blocks.append({"code": code})
    elif not facts.setup_steps:
        blocks.append({"p": f"{TODO} Passos para rodar o projeto localmente."})

    if facts.env_vars:
        blocks.append({"h2": "Variáveis de ambiente"})
        blocks.append(
            {
                "p": f"O template fica em {facts.env_file}. "
                f"{_count(len(facts.env_vars), 'variável declarada', 'variáveis declaradas')}:"
            }
        )
        items = []
        for var in facts.env_vars:
            desc = var.description or f"{TODO} para que serve."
            if var.example:
                desc += f" Exemplo: {var.example}"
            items.append({"key": var.key, "value": desc})
        blocks.append({"kv": items})

    if facts.scripts:
        prefix = _run_prefix(facts)
        blocks.append({"h2": "Scripts"})
        blocks.append(
            _table(
                ["Script", "Comando"],
                [[prefix + name, cmd] for name, cmd in facts.scripts],
                [50, 120],
            )
        )
    return blocks


def _default_setup(facts: ProjectFacts) -> str | None:
    pm = facts.stack.package_manager
    names = {n for n, _ in facts.scripts}
    tools = {t for t, _ in facts.tools}
    lines = []
    if facts.env_file:
        lines.append(f"cp {facts.env_file} .env")
    if pm in ("pnpm", "yarn", "npm", "bun"):
        lines.append(f"{pm} install")
        for candidate in ("dev", "start"):
            if candidate in names:
                lines.append(
                    f"{_run_prefix(facts)}{candidate}".replace(
                        "npm run start", "npm start"
                    )
                )
                break
    elif pm == "pip/uv":
        lines.append("uv sync")
    elif pm == "pip":
        lines += [
            "python -m venv .venv",
            ". .venv/bin/activate",
            "pip install -r requirements.txt",
        ]
        # o comando que a imagem roda é o único início confirmado pelos arquivos
        if facts.docker and facts.docker.cmd:
            lines.append(_shell_cmd(facts.docker.cmd))
    elif pm == "cargo":
        lines += ["cargo build", "cargo run"]
    if not lines and "Docker Compose" in tools:
        lines.append("docker compose up -d")
    return "\n".join(lines) or None


# --- brand -----------------------------------------------------------------


def _usage(facts: ProjectFacts, md: dict) -> list[dict]:
    backend = facts.stack.kind == "backend"
    blocks: list[dict] = [
        {"h1": "Como se usa" if backend else "Como se usa a aplicação"}
    ]
    from_readme = md.get("usage", [])
    blocks += from_readme
    blocks += _routes_blocks(facts)
    if not from_readme:
        subject = "de quem consome o serviço" if backend else "do usuário"
        blocks.append(
            {
                "p": f"{TODO} Caminho principal {subject}: entrada, ação e resultado."
            }
        )
        if not facts.routes:
            blocks.append({"bullet": [f"{TODO} Funcionalidade e para que serve."]})
    return blocks


def _routes_blocks(facts: ProjectFacts) -> list[dict]:
    """Rotas encontradas no código: as que o app expõe e as telas que declara.

    Endpoints que o app apenas consome ficam fora desta seção: eles entram em
    "APIs e integrações", onde dizem respeito.
    """
    blocks: list[dict] = []
    api = [g for g in facts.routes if g.kind == "api"]
    pages = [g for g in facts.routes if g.kind == "page"]
    if api:
        total = sum(len(g.ops) for g in api)
        blocks.append(
            {
                "p": f"{_count(len(api), 'grupo de rotas', 'grupos de rotas')} no código, "
                f"com {_count(total, 'operação', 'operações')}:"
            }
        )
        blocks.append(
            _table(
                ["Grupo", "Base", "Operações"],
                [[g.label, g.base, ", ".join(g.ops)] for g in api],
                [32, 30, 108],
            )
        )
    if pages:
        total = sum(len(g.ops) for g in pages)
        blocks.append(
            {"p": f"{_count(total, 'rota de tela', 'rotas de tela')}, pelas pastas de páginas:"}
        )
        blocks.append(
            _table(
                ["Grupo", "Rotas"],
                [[g.label, ", ".join(g.ops)] for g in pages],
                [35, 135],
            )
        )
    return blocks


def _architecture_rules(facts: ProjectFacts, md: dict) -> list[dict]:
    blocks: list[dict] = [{"h1": "Regras e decisões de arquitetura"}]
    from_readme = md.get("rules", [])
    if from_readme:
        return blocks + from_readme
    blocks.append(
        {
            "p": f"{TODO} As invariantes e decisões que não são óbvias no "
            "código e que o time precisa preservar."
        }
    )
    if facts.staged_checks:
        blocks.append(
            {
                "p": "As checagens do commit indicam o que o projeto protege por "
                f"arquivo (ver Qualidade e testes). {TODO} A regra que cada "
                "uma garante."
            }
        )
    else:
        blocks.append(
            {
                "callout": {
                    "title": "Regra",
                    "text": f"{TODO} Uma regra inegociável do projeto e como ela é verificada.",
                }
            }
        )
    return blocks


def _gaps(facts: ProjectFacts, md: dict) -> list[dict]:
    blocks: list[dict] = [{"h1": "Lacunas conhecidas"}]
    blocks += md.get("gaps", [])
    if facts.warnings:
        blocks.append({"h2": "Divergências entre arquivos"})
        blocks.append({"bullet": facts.warnings})
    if facts.code_todos:
        blocks.append({"h2": "Pendências marcadas no código"})
        blocks.append({"bullet": facts.code_todos})
    if len(blocks) == 1:
        blocks.append(
            {
                "bullet": [
                    f"{TODO} O que ainda falta, é provisório ou tem dívida técnica."
                ]
            }
        )
    return blocks


# --- development -----------------------------------------------------------


def _code_organization(facts: ProjectFacts, md: dict) -> list[dict]:
    blocks: list[dict] = [{"h1": "Organização do código"}]
    if facts.tree:
        root = "src/" if facts.code_root == "src" else "a raiz do repositório"
        blocks.append(
            {
                "p": f"Estrutura de {root}, gerada a partir das pastas "
                "(dependências e artefatos de build omitidos):"
            }
        )
        blocks.append({"code": facts.tree})
    from_readme = md.get("org", [])
    if facts.tree:  # a árvore já está acima; o quadro do README repetiria
        from_readme = [b for b in from_readme if "code" not in b]
    blocks += from_readme
    if facts.top_dirs:
        rows = [
            [
                f"{name}/",
                ", ".join(entries[:8]) + (" …" if len(entries) > 8 else "")
                or "(vazia)",
            ]
            for name, entries in facts.top_dirs
        ]
        blocks.append({"h2": "Pastas principais"})
        blocks.append(_table(["Pasta", "Conteúdo"], rows, [40, 130]))
    if not from_readme:
        blocks.append(
            {
                "p": f"{TODO} Responsabilidade de cada pasta e o que não deve ser misturado."
            }
        )
    return blocks


def _tools(facts: ProjectFacts) -> list[dict]:
    if not facts.tools:
        return []
    return [
        {"h1": "Ferramentas e configuração"},
        {"p": "Arquivos de configuração encontrados na raiz:"},
        _table(
            ["Ferramenta", "Arquivo"],
            [[tool, file] for tool, file in facts.tools],
            [60, 110],
        ),
    ]


def _dependencies(facts: ProjectFacts) -> list[dict]:
    if not (facts.dependencies or facts.dev_dependencies):
        return []
    blocks: list[dict] = [{"h1": "Dependências"}]
    for title, deps in (
        ("Produção", facts.dependencies),
        ("Desenvolvimento", facts.dev_dependencies),
    ):
        if deps:
            blocks.append({"h2": f"{title} ({len(deps)})"})
            blocks.append(_deps_table(deps))
    return blocks


def _deps_table(deps: list[tuple[str, str]]) -> dict:
    """Até 20 pacotes: uma coluna. Mais que isso: dois pacotes por linha, em
    ordem de leitura (esquerda → direita), para a lista não ocupar páginas
    demais e continuar em ordem quando a tabela atravessa páginas."""
    if len(deps) <= 20:
        return _table(["Pacote", "Versão"], [[n, v] for n, v in deps], [100, 70])
    padded = deps + [("", "")] * (len(deps) % 2)
    rows = [[*padded[i], *padded[i + 1]] for i in range(0, len(padded), 2)]
    return _table(["Pacote", "Versão", "Pacote", "Versão"], rows, [57, 28, 57, 28])


def _modules(facts: ProjectFacts, md: dict) -> list[dict]:
    blocks: list[dict] = [{"h1": "Módulos e componentes"}]
    from_readme = md.get("modules", [])
    blocks += from_readme
    if facts.modules:
        parent = facts.modules[0].path.rsplit("/", 1)[0]
        blocks.append(
            {
                "p": f"{_count(len(facts.modules), 'módulo', 'módulos')} em {parent}/, com os "
                "arquivos de cada um:"
            }
        )
        blocks.append(
            _table(
                ["Módulo", "Arquivos"],
                [[m.name, ", ".join(m.files) or "(vazio)"] for m in facts.modules],
                [38, 132],
            )
        )
    if not from_readme:
        blocks.append(
            {
                "p": f"{TODO} Para cada módulo: o que faz, quem usa e "
                "cuidados ao alterar."
            }
        )
    return blocks


def _apis(facts: ProjectFacts, md: dict) -> list[dict]:
    blocks: list[dict] = [{"h1": "APIs e integrações"}]
    tools = {t for t, _ in facts.tools}
    if "Orval" in tools:
        blocks.append(
            {
                "p": "O cliente HTTP é gerado pelo Orval a partir de um "
                "schema OpenAPI (ver orval.config)."
            }
        )
    from_readme = md.get("apis", [])
    blocks += from_readme
    urls = [v for v in facts.env_vars if "URL" in v.key.upper()]
    if urls:
        blocks.append({"h2": "Endereços externos configurados"})
        blocks.append(
            {"bullet": [f"{v.key}: {v.description or v.example or '—'}" for v in urls]}
        )
    api = [g for g in facts.routes if g.kind == "api"]
    if api:
        blocks.append({"h2": "Rotas expostas"})
        blocks.append(
            _table(
                ["Grupo", "Base", "Arquivo"],
                [[g.label, g.base, g.source] for g in api],
                [34, 30, 106],
            )
        )
    consumed = [g for g in facts.routes if g.kind == "client"]
    if consumed:
        total = sum(len(g.ops) for g in consumed)
        blocks.append({"h2": "Endpoints consumidos"})
        blocks.append(
            {"p": f"{_count(total, 'chamada', 'chamadas')} nos clientes HTTP do app:"}
        )
        blocks.append(
            _table(
                ["Arquivo", "Endpoints"],
                [[g.source, ", ".join(g.ops)] for g in consumed],
                [55, 115],
            )
        )
    if not from_readme:
        blocks.append(
            {"p": f"{TODO} Contratos, autenticação e serviços externos consumidos."}
        )
    return blocks


# --- qualidade e Docker (todos os tipos) -----------------------------------


def _quality(facts: ProjectFacts, md: dict) -> list[dict]:
    blocks: list[dict] = [{"h1": "Qualidade e testes"}]
    rows = [[f"git {hook}", cmds] for hook, cmds in facts.hooks]
    for wf in facts.workflows:
        steps = ", ".join(cmd for _, cmd in wf.steps) or "—"
        rows.append([f"CI: {wf.name}", f"Dispara em {wf.triggers}. Roda: {steps}"])

    if rows:
        blocks.append({"p": "O que roda automaticamente e em que momento:"})
        blocks.append(_table(["Momento", "O que roda"], rows, [50, 120]))
    if facts.staged_checks:
        blocks.append({"h2": "Checagens nos arquivos do commit (lint-staged)"})
        blocks.append(
            _table(
                ["Arquivos", "Checagem"],
                [[p, c] for p, c in facts.staged_checks],
                [65, 105],
            )
        )
    if facts.check_scripts:
        prefix = _run_prefix(facts)
        blocks.append({"h2": "Checagens manuais"})
        blocks.append(
            {"bullet": [f"{prefix}{name}" for name, _ in facts.check_scripts]}
        )
    if facts.test_files:
        runner = next((lib for cat, lib in facts.libs if cat == "Testes"), None)
        total = sum(n for _, n in facts.test_files)
        where = ", ".join(f"{d}/ ({n})" for d, n in facts.test_files)
        blocks.append(
            {
                "p": f"{_count(total, 'arquivo de teste', 'arquivos de teste')}, em {where}"
                + (f", rodados com {runner}." if runner else ".")
            }
        )
    from_readme = md.get("quality", [])
    blocks += from_readme
    if not from_readme:
        blocks.append(
            {"p": f"{TODO} O que cada checagem protege."}
            if len(blocks) > 1
            else {
                "bullet": [
                    f"{TODO} Como rodar os testes.",
                    f"{TODO} Lint, formatação e checagens de CI.",
                ]
            }
        )
    return blocks


def _docker(facts: ProjectFacts) -> list[dict]:
    d = facts.docker
    if d is None:
        return []
    items = []
    if d.stages:
        items.append(f"Estágios: {' → '.join(d.stages)}")
    if d.ports:
        items.append(f"Porta exposta: {', '.join(d.ports)}")
    if d.user:
        items.append(f"Usuário de execução: {d.user}")
    if d.cmd:
        items.append(f"Comando de início: {_shell_cmd(d.cmd)}")
    if d.build_args:
        items.append(f"Argumentos de build: {', '.join(d.build_args)}")

    port = d.ports[0].split("/")[0] if d.ports else None
    run = (
        f"docker run -p {port}:{port} {facts.name}"
        if port
        else f"docker run {facts.name}"
    )
    blocks: list[dict] = [{"h1": "Docker"}]
    if items:
        blocks.append({"bullet": items})
    if any(t == "Docker Compose" for t, _ in facts.tools):
        run += "\n# ou, com o compose do repositório:\ndocker compose up -d"
    blocks.append({"code": f"docker build -t {facts.name} .\n{run}"})
    return blocks
