"""Monta o esqueleto da documentação a partir dos fatos extraídos.

O que é fato (scripts, dependências, variáveis, árvore de pastas, hooks, CI,
Docker) vem preenchido. O que exige interpretação (propósito, fluxos de uso,
regras de arquitetura) fica marcado com (TODO), para ser escrito por uma
pessoa ou, no futuro, pelo agente.

Tipos:
  brand        visão geral, como começar, uso, regras, qualidade, Docker, lacunas
  development  visão geral, como começar, código, ferramentas, dependências,
               módulos, APIs, qualidade, Docker
  full         os dois, sem repetir seções em comum
"""

from __future__ import annotations

from .extract import ProjectFacts

TODO = "(TODO)"


def skeleton_blocks(facts: ProjectFacts, doc_type: str) -> list[dict]:
    brand = doc_type in ("brand", "full")
    dev = doc_type in ("development", "full")

    blocks = _overview(facts) + _getting_started(facts)
    if brand:
        blocks += _usage(facts) + _architecture_rules()
    if dev:
        blocks += (_code_organization(facts) + _tools(facts)
                   + _dependencies(facts) + _modules() + _apis(facts))
    blocks += _quality(facts) + _docker(facts)
    if brand:
        blocks += _gaps(facts)
    elif facts.warnings:
        blocks += [{"h1": "Inconsistências encontradas"}, {"bullet": facts.warnings}]
    return _number_headings(blocks)


# --- utilitários -----------------------------------------------------------

def _number_headings(blocks: list[dict]) -> list[dict]:
    """Prefixa h1 com 'N.' e h2 com 'N.M.' na ordem em que aparecem."""
    h1 = h2 = 0
    out: list[dict] = []
    for block in blocks:
        (typ, content), = block.items()
        if typ == "h1":
            h1, h2 = h1 + 1, 0
            out.append({"h1": f"{h1}. {content}"})
        elif typ == "h2":
            h2 += 1
            out.append({"h2": f"{h1}.{h2}. {content}"})
        else:
            out.append(block)
    return out


def _table(header: list[str], rows: list[list[str]], widths: list[int]) -> dict:
    return {"table": {"header": header, "widths": widths, "rows": rows}}


def _run_prefix(facts: ProjectFacts) -> str:
    pm = facts.stack.package_manager
    if pm in ("pnpm", "yarn", "bun"):
        return f"{pm} "
    if pm == "npm":
        return "npm run "
    return ""


# --- seções em comum -------------------------------------------------------

def _overview(facts: ProjectFacts) -> list[dict]:
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
        rows.append(["—", f"{TODO} preencher manualmente"])

    return [
        {"h1": "Visão geral"},
        {"p": intro or f"{TODO} Descreva em um parágrafo o que é {facts.name}: "
                       "o problema que resolve, para quem, e o que o torna diferente."},
        {"p": f"{TODO} Complete com o contexto que o README não cobre: público, "
              "escopo atual e o que está fora do escopo."},
        {"callout": {
            "title": "Como este documento foi gerado",
            "text": "Os fatos (stack, scripts, variáveis, pastas, hooks, CI e Docker) "
                    "foram extraídos dos arquivos do repositório. Revise-os e "
                    "substitua os trechos marcados com (TODO).",
        }},
        {"h2": "Stack"},
        _table(["Peça", "Escolha"], rows, [45, 125]),
    ]


def _getting_started(facts: ProjectFacts) -> list[dict]:
    blocks: list[dict] = [{"h1": "Como começar"}, {"h2": "Pré-requisitos"}]
    prereqs = facts.readme_prereqs + [p for p in facts.prereqs
                                      if p not in facts.readme_prereqs]
    blocks.append({"bullet": prereqs} if prereqs else
                  {"bullet": [f"{TODO} Versões de runtime e ferramentas necessárias."]})

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
        blocks.append({"p": f"O template fica em {facts.env_file}. "
                            f"{len(facts.env_vars)} variável(is) declarada(s):"})
        items = []
        for var in facts.env_vars:
            desc = var.description or f"{TODO} Descrever para que serve."
            if var.example:
                desc += f" Exemplo: {var.example}"
            items.append({"key": var.key, "value": desc})
        blocks.append({"kv": items})

    if facts.scripts:
        prefix = _run_prefix(facts)
        blocks.append({"h2": "Scripts"})
        blocks.append(_table(["Script", "Comando"],
                             [[prefix + name, cmd] for name, cmd in facts.scripts],
                             [50, 120]))
    return blocks


def _default_setup(facts: ProjectFacts) -> str | None:
    pm = facts.stack.package_manager
    names = {n for n, _ in facts.scripts}
    lines = []
    if facts.env_file:
        lines.append(f"cp {facts.env_file} .env")
    if pm in ("pnpm", "yarn", "npm", "bun"):
        lines.append(f"{pm} install")
        for candidate in ("dev", "start"):
            if candidate in names:
                lines.append(f"{_run_prefix(facts)}{candidate}".replace("npm run start",
                                                                       "npm start"))
                break
    elif pm == "pip/uv":
        lines.append("uv sync")
    elif pm == "cargo":
        lines += ["cargo build", "cargo run"]
    return "\n".join(lines) or None


# --- brand -----------------------------------------------------------------

def _usage(facts: ProjectFacts) -> list[dict]:
    if facts.stack.kind == "backend":
        return [
            {"h1": "Como se usa"},
            {"h2": f"{TODO} Fluxo principal"},
            {"p": f"{TODO} Descreva o caminho típico de quem consome o serviço: "
                  "autenticação, chamadas principais e respostas esperadas."},
            {"h2": f"{TODO} Endpoints ou funcionalidades"},
            {"bullet": [f"{TODO} Endpoint ou funcionalidade e para que serve."]},
        ]
    return [
        {"h1": "Como se usa a aplicação"},
        {"h2": f"{TODO} Fluxo principal"},
        {"p": f"{TODO} Descreva o caminho feliz do ponto de vista do usuário: "
              "por onde entra, o que faz e o que obtém."},
        {"h2": f"{TODO} Telas ou funcionalidades"},
        {"bullet": [f"{TODO} Funcionalidade e para que serve."]},
    ]


def _architecture_rules() -> list[dict]:
    return [
        {"h1": "Regras e decisões de arquitetura"},
        {"p": f"{TODO} As invariantes e decisões que não são óbvias no código e "
              "que o time precisa preservar."},
        {"callout": {
            "title": "Regra",
            "text": f"{TODO} Documente aqui uma regra inegociável do projeto e "
                    "como ela é verificada.",
        }},
    ]


def _gaps(facts: ProjectFacts) -> list[dict]:
    items = list(facts.warnings)
    items.append(f"{TODO} O que ainda falta, é provisório ou tem dívida técnica.")
    return [{"h1": "Lacunas conhecidas"}, {"bullet": items}]


# --- development -----------------------------------------------------------

def _code_organization(facts: ProjectFacts) -> list[dict]:
    blocks: list[dict] = [{"h1": "Organização do código"}]
    if facts.tree:
        root = "src/" if facts.code_root == "src" else "a raiz do repositório"
        blocks.append({"p": f"Estrutura de {root}, gerada a partir das pastas "
                            "(dependências e artefatos de build omitidos):"})
        blocks.append({"code": facts.tree})
    blocks.append({"p": f"{TODO} Explique as convenções: onde mora cada tipo de "
                        "código e o que não deve ser misturado."})
    if facts.top_dirs:
        rows = []
        for name, entries in facts.top_dirs:
            preview = ", ".join(entries[:6]) + (" …" if len(entries) > 6 else "")
            rows.append([f"{name}/", (f"{TODO} Responsabilidade. Contém: "
                                     f"{preview or '(vazia)'}")])
        blocks.append({"h2": "Pastas principais"})
        blocks.append(_table(["Pasta", "Responsabilidade"], rows, [40, 130]))
    return blocks


def _tools(facts: ProjectFacts) -> list[dict]:
    if not facts.tools:
        return []
    return [
        {"h1": "Ferramentas e configuração"},
        {"p": "Arquivos de configuração encontrados na raiz:"},
        _table(["Ferramenta", "Arquivo"],
               [[tool, file] for tool, file in facts.tools], [60, 110]),
    ]


def _dependencies(facts: ProjectFacts) -> list[dict]:
    if not (facts.dependencies or facts.dev_dependencies):
        return []
    blocks: list[dict] = [{"h1": "Dependências"}]
    for title, deps in (("Produção", facts.dependencies),
                        ("Desenvolvimento", facts.dev_dependencies)):
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


def _modules() -> list[dict]:
    return [
        {"h1": "Módulos e componentes"},
        {"p": f"{TODO} Referência dos principais símbolos (funções, tipos, "
              "componentes): responsabilidade, entradas e saídas."},
        {"h2": f"{TODO} Nome do módulo"},
        {"p": f"{TODO} O que faz, quem usa e cuidados ao alterar."},
    ]


def _apis(facts: ProjectFacts) -> list[dict]:
    blocks: list[dict] = [{"h1": "APIs e integrações"}]
    tools = {t for t, _ in facts.tools}
    if "Orval" in tools:
        blocks.append({"p": "O cliente HTTP é gerado pelo Orval a partir de um "
                            "schema OpenAPI (ver orval.config)."})
    urls = [v for v in facts.env_vars if "URL" in v.key.upper()]
    if urls:
        blocks.append({"bullet": [f"{v.key}: {v.description or TODO}"
                                  for v in urls]})
    blocks.append({"p": f"{TODO} Endpoints consumidos ou expostos, contratos e "
                        "serviços externos."})
    return blocks


# --- qualidade e Docker (todos os tipos) -----------------------------------

def _quality(facts: ProjectFacts) -> list[dict]:
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
        blocks.append(_table(["Arquivos", "Checagem"],
                             [[p, c] for p, c in facts.staged_checks], [65, 105]))
    if facts.check_scripts:
        prefix = _run_prefix(facts)
        blocks.append({"h2": "Checagens manuais"})
        blocks.append({"bullet": [f"{prefix}{name}" for name, _ in facts.check_scripts]})
    if len(blocks) == 1:
        blocks.append({"bullet": [f"{TODO} Como rodar os testes.",
                                  f"{TODO} Lint, formatação e checagens de CI."]})
    else:
        blocks.append({"p": f"{TODO} Explique o que cada checagem protege."})
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
        items.append(f"Comando de início: {d.cmd}")
    if d.build_args:
        items.append(f"Argumentos de build: {', '.join(d.build_args)}")

    port = d.ports[0].split("/")[0] if d.ports else None
    run = f"docker run -p {port}:{port} {facts.name}" if port else f"docker run {facts.name}"
    blocks: list[dict] = [{"h1": "Docker"}]
    if items:
        blocks.append({"bullet": items})
    blocks.append({"code": f"docker build -t {facts.name} .\n{run}"})
    return blocks
