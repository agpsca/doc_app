"""Extrator determinístico de fatos de um projeto (sem IA).

Lê arquivos conhecidos do app e devolve um `ProjectFacts` com tudo o que dá
para afirmar sem interpretar o código: introdução do README, scripts,
dependências, variáveis de ambiente de exemplo, árvore de pastas, hooks de git,
CI, Dockerfile e ferramentas configuradas.

Segurança: só lê arquivos de exemplo de ambiente (.env.example e afins).
Nunca lê `.env`, `.env.local` ou similares, que podem conter segredos.

A prosa interpretativa (o "porquê" das decisões) fica para o agente.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .detect import StackInfo, detect_stack
from .textio import read_text

MAX_READ = 512 * 1024  # não lê arquivos maiores que isso

IGNORED_DIRS = {
    "node_modules", ".git", ".next", ".nuxt", "dist", "build", "out", "coverage",
    ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".turbo", ".cache", "target", ".idea", ".vscode", "workspace",
}

# Somente arquivos de EXEMPLO. .env / .env.local nunca são lidos.
ENV_EXAMPLE_FILES = (".env.example", ".env.sample", ".env.template", ".env.dist")

SETUP_HEADING = re.compile(
    r"come[cç]|instala|setup|getting started|quick ?start|rodando|rodar|executar|"
    r"running|how to run|desenvolvimento local|local development|uso local",
    re.IGNORECASE,
)
PREREQ_HEADING = re.compile(r"pr[ée][\s-]?requisitos?|requisitos|requirements|"
                            r"prerequisites|depend[êe]ncias do sistema", re.I)
CMD_START = re.compile(r"^(yarn|npm|pnpm|npx|bun|make|docker|docker-compose|uv|pip|"
                       r"python3?|poetry|go|cargo|composer|php|bundle|rails|"
                       r"\./|cp |git |mvn|gradle)", re.I)

# Bibliotecas conhecidas -> (categoria, nome exibido)
KNOWN_LIBS: dict[str, tuple[str, str]] = {
    # estilo
    "tailwindcss": ("Estilo", "Tailwind CSS"),
    "styled-components": ("Estilo", "styled-components"),
    "@emotion/react": ("Estilo", "Emotion"),
    "sass": ("Estilo", "Sass"),
    # componentes / ícones
    "radix-ui": ("Componentes", "Radix UI"),
    "shadcn": ("Componentes", "shadcn/ui"),
    "@mui/material": ("Componentes", "Material UI"),
    "@chakra-ui/react": ("Componentes", "Chakra UI"),
    "antd": ("Componentes", "Ant Design"),
    "@mantine/core": ("Componentes", "Mantine"),
    "bootstrap": ("Componentes", "Bootstrap"),
    "react-bootstrap": ("Componentes", "React Bootstrap"),
    "reactstrap": ("Componentes", "reactstrap"),
    "primereact": ("Componentes", "PrimeReact"),
    "vuetify": ("Componentes", "Vuetify"),
    "lucide-react": ("Ícones", "lucide-react"),
    # estado / dados
    "zustand": ("Estado global", "zustand"),
    "@reduxjs/toolkit": ("Estado global", "Redux Toolkit"),
    "jotai": ("Estado global", "jotai"),
    "mobx": ("Estado global", "MobX"),
    "@tanstack/react-query": ("Estado de servidor", "TanStack Query"),
    "swr": ("Estado de servidor", "SWR"),
    "@apollo/client": ("Estado de servidor", "Apollo Client"),
    # formulários / validação
    "react-hook-form": ("Formulários", "react-hook-form"),
    "formik": ("Formulários", "Formik"),
    "zod": ("Validação", "zod"),
    "yup": ("Validação", "yup"),
    # http
    "orval": ("Cliente HTTP", "Orval (gerado a partir do OpenAPI)"),
    "axios": ("Cliente HTTP", "axios"),
    # qualidade
    "@biomejs/biome": ("Lint e formato", "Biome"),
    "eslint": ("Lint e formato", "ESLint"),
    "prettier": ("Lint e formato", "Prettier"),
    "husky": ("Git hooks", "husky"),
    "lint-staged": ("Git hooks", "lint-staged"),
    "vitest": ("Testes", "Vitest"),
    "jest": ("Testes", "Jest"),
    "@playwright/test": ("Testes", "Playwright"),
    "cypress": ("Testes", "Cypress"),
    # python
    "fastapi": ("Framework web", "FastAPI"),
    "django": ("Framework web", "Django"),
    "flask": ("Framework web", "Flask"),
    "pydantic": ("Validação", "Pydantic"),
    "sqlalchemy": ("Banco de dados", "SQLAlchemy"),
    "pytest": ("Testes", "pytest"),
    "ruff": ("Lint e formato", "Ruff"),
    "mypy": ("Tipagem", "mypy"),
    "fpdf2": ("PDF", "fpdf2"),
    "pyyaml": ("Configuração", "PyYAML"),
}

# Ordem das categorias na tabela de stack.
_CATEGORY_ORDER = {cat: i for i, cat in enumerate([
    "Framework web", "Estilo", "Componentes", "Ícones", "Formulários", "Validação",
    "Estado global", "Estado de servidor", "Cliente HTTP", "Banco de dados", "PDF",
    "Configuração", "Tipagem", "Lint e formato", "Testes", "Git hooks",
])}

# Arquivo de configuração -> ferramenta
TOOL_CONFIGS: list[tuple[str, str]] = [
    ("biome.json", "Biome"),
    ("biome.jsonc", "Biome"),
    ("eslint.config.*", "ESLint"),
    (".eslintrc*", "ESLint"),
    (".prettierrc*", "Prettier"),
    ("prettier.config.*", "Prettier"),
    ("tsconfig.json", "TypeScript"),
    ("orval.config.*", "Orval"),
    ("components.json", "shadcn/ui"),
    ("vitest.config.*", "Vitest"),
    ("jest.config.*", "Jest"),
    ("playwright.config.*", "Playwright"),
    ("tailwind.config.*", "Tailwind CSS"),
    ("next.config.*", "Next.js"),
    ("vite.config.*", "Vite"),
    (".pre-commit-config.yaml", "pre-commit"),
    ("lefthook.yml", "lefthook"),
    ("ruff.toml", "Ruff"),
    ("Makefile", "Make"),
]

TEST_SCRIPT_HINT = re.compile(r"test|check|lint|typecheck|verify|e2e|format", re.IGNORECASE)


@dataclass
class EnvVar:
    key: str
    description: str
    example: str


@dataclass
class DockerInfo:
    stages: list[str] = field(default_factory=list)   # "node:22-slim (builder)"
    ports: list[str] = field(default_factory=list)
    user: str | None = None
    cmd: str | None = None
    build_args: list[str] = field(default_factory=list)


@dataclass
class Workflow:
    file: str
    name: str
    triggers: str
    steps: list[tuple[str, str]] = field(default_factory=list)  # (nome, comando)


@dataclass
class ProjectFacts:
    name: str
    stack: StackInfo
    description: str | None = None
    readme_intro: str | None = None
    readme_prereqs: list[str] = field(default_factory=list)
    setup_text: str | None = None
    setup_code: str | None = None
    setup_steps: list[str] = field(default_factory=list)
    prereqs: list[str] = field(default_factory=list)
    libs: list[tuple[str, str]] = field(default_factory=list)  # (categoria, libs)
    scripts: list[tuple[str, str]] = field(default_factory=list)
    dependencies: list[tuple[str, str]] = field(default_factory=list)
    dev_dependencies: list[tuple[str, str]] = field(default_factory=list)
    env_file: str | None = None
    env_vars: list[EnvVar] = field(default_factory=list)
    code_root: str | None = None          # "src" ou "."
    tree: str | None = None
    top_dirs: list[tuple[str, list[str]]] = field(default_factory=list)
    tools: list[tuple[str, str]] = field(default_factory=list)  # (ferramenta, arquivo)
    hooks: list[tuple[str, str]] = field(default_factory=list)  # (hook, comandos)
    staged_checks: list[tuple[str, str]] = field(default_factory=list)
    workflows: list[Workflow] = field(default_factory=list)
    docker: DockerInfo | None = None
    # Contradições encontradas entre arquivos do repositório (vão para
    # "Lacunas conhecidas"; o doc_app não escolhe um lado).
    warnings: list[str] = field(default_factory=list)

    @property
    def check_scripts(self) -> list[tuple[str, str]]:
        return [(n, c) for n, c in self.scripts if TEST_SCRIPT_HINT.search(n)]


# --- API -------------------------------------------------------------------

def extract_facts(app_path: Path) -> ProjectFacts:
    facts = ProjectFacts(name=app_path.name, stack=detect_stack(app_path))
    _read_readme(app_path, facts)
    pkg = _read_json(app_path / "package.json")
    if pkg:
        _from_package_json(pkg, facts)
    pyproject = _read_toml(app_path / "pyproject.toml")
    if pyproject:
        _from_pyproject(pyproject, facts)
    _read_version_files(app_path, facts)
    _read_env_example(app_path, facts)
    _build_tree(app_path, facts)
    _detect_tools(app_path, facts)
    _read_husky(app_path, facts)
    _read_workflows(app_path, facts)
    _read_dockerfile(app_path, facts)
    _dedupe(facts.prereqs)
    _check_consistency(app_path, facts)
    return facts


def _check_consistency(app: Path, facts: ProjectFacts) -> None:
    """Aponta divergências óbvias entre README e configuração."""
    pm = facts.stack.package_manager
    if pm in ("pnpm", "yarn", "npm", "bun") and facts.setup_code:
        used = {m.group(1) for m in
                re.finditer(r"^\s*(pnpm|yarn|npm|bun)\b", facts.setup_code, re.M)}
        other = sorted(used - {pm})
        if other:
            src = "packageManager do package.json" if (app / "package.json").is_file() \
                else "lockfile"
            facts.warnings.append(
                f"O README usa {', '.join(other)} nos comandos de instalação, mas o "
                f"projeto está configurado para {pm} ({src}). Confirme qual é o "
                "correto e alinhe o README.")
    for lock, owner in (("yarn.lock", "yarn"), ("package-lock.json", "npm"),
                        ("pnpm-lock.yaml", "pnpm")):
        if pm and pm != owner and (app / lock).is_file():
            facts.warnings.append(
                f"Existe {lock} ({owner}) num projeto configurado para {pm}. "
                "Lockfiles de gerenciadores diferentes costumam divergir.")


# --- leitura segura --------------------------------------------------------

def _read_text(path: Path) -> str | None:
    return read_text(path, MAX_READ)


def _read_json(path: Path) -> dict | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _read_toml(path: Path) -> dict | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None


def _dedupe(items: list) -> None:
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    items[:] = out


def _plain_markdown(text: str) -> str:
    """Remove marcações simples de Markdown para caber no PDF."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)          # imagens
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)       # links
    text = re.sub(r"`([^`]+)`", r"\1", text)                   # código inline
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)            # negrito
    text = re.sub(r"(?<!\w)[*_](.+?)[*_](?!\w)", r"\1", text)  # itálico
    return re.sub(r"\s+", " ", text).strip()


def _short_cmd(cmd: str, limit: int = 90) -> str:
    cmd = re.sub(r"\s--no-warnings=\S+", "", cmd)
    cmd = re.sub(r"\s+", " ", cmd).strip()
    return cmd if len(cmd) <= limit else cmd[: limit - 1] + "…"


def _clean_version(v: str) -> str:
    return v.lstrip("^~=v ").strip() if isinstance(v, str) else str(v)


# --- README ----------------------------------------------------------------

def _read_readme(app: Path, facts: ProjectFacts) -> None:
    readme = next((p for p in (app / "README.md", app / "readme.md",
                               app / "README.rst", app / "README")
                   if p.is_file()), None)
    if readme is None:
        return
    text = _read_text(readme)
    if not text:
        return

    lines = text.splitlines()
    # Seções: (titulo, linhas)
    sections: list[tuple[str, list[str]]] = [("", [])]
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and re.match(r"^#{1,6}\s", line):
            sections.append((line.lstrip("#").strip(), []))
        else:
            sections[-1][1].append(line)

    # Introdução: primeiro parágrafo de texto corrido antes da 2ª seção.
    # Sem parágrafo, usa o título principal do README.
    intro_sources = sections[0][1] + (sections[1][1] if len(sections) > 1 else [])
    facts.readme_intro = _first_paragraph(intro_sources)
    if not facts.readme_intro and len(sections) > 1 and sections[1][0]:
        facts.readme_intro = _plain_markdown(sections[1][0]) or None

    for title, body in sections:
        if not title:
            continue
        if PREREQ_HEADING.search(title) and not facts.readme_prereqs:
            facts.readme_prereqs = _list_items(body)
        elif SETUP_HEADING.search(title) and facts.setup_text is None \
                and facts.setup_code is None:
            facts.setup_text = _first_paragraph(body)
            facts.setup_code = _first_code_block(body)
            facts.setup_steps = _list_items(body)
            if facts.setup_code is None:
                cmds = _commands_in(body)
                facts.setup_code = "\n".join(cmds) if cmds else None


def _list_items(lines: list[str]) -> list[str]:
    items = []
    for line in lines:
        m = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)", line)
        if m:
            text = _plain_markdown(m.group(1))
            if text:
                items.append(text)
    return items


def _commands_in(lines: list[str]) -> list[str]:
    """Comandos citados em código inline (`yarn install`) fora de blocos."""
    cmds = []
    for line in lines:
        for span in re.findall(r"`([^`]+)`", line):
            span = span.strip()
            if CMD_START.match(span) and span not in cmds:
                cmds.append(span)
    return cmds


def _first_paragraph(lines: list[str]) -> str | None:
    para: list[str] = []
    in_fence = False
    for line in lines:
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            if para:
                break
            continue
        if in_fence:
            continue
        if not s:
            if para:
                break
            continue
        if s[0] in ">|<!-*+#" or re.match(r"^\d+\.\s", s) or s.startswith("[!"):
            if para:
                break
            continue
        para.append(s)
    text = _plain_markdown(" ".join(para)) if para else ""
    return text or None


def _first_code_block(lines: list[str]) -> str | None:
    block: list[str] = []
    inside = False
    for line in lines:
        if line.strip().startswith("```"):
            if inside:
                break
            inside = True
            continue
        if inside:
            block.append(line.rstrip())
    code = "\n".join(block).strip("\n")
    return code or None


# --- package.json / pyproject ----------------------------------------------

def _from_package_json(pkg: dict, facts: ProjectFacts) -> None:
    if isinstance(pkg.get("description"), str):
        facts.description = pkg["description"].strip() or None

    scripts = pkg.get("scripts") or {}
    if isinstance(scripts, dict):
        facts.scripts = [(k, _short_cmd(str(v))) for k, v in scripts.items()]

    deps = pkg.get("dependencies") or {}
    dev = pkg.get("devDependencies") or {}
    facts.dependencies = [(k, _clean_version(v)) for k, v in deps.items()]
    facts.dev_dependencies = [(k, _clean_version(v)) for k, v in dev.items()]
    _collect_libs({**deps, **dev}, facts)

    engines = pkg.get("engines") or {}
    if isinstance(engines, dict):
        for k, v in engines.items():
            facts.prereqs.append(f"{k.capitalize()} {v}")
    pm = pkg.get("packageManager")
    if isinstance(pm, str) and "@" in pm:
        name, ver = pm.split("@", 1)
        facts.prereqs.append(f"{name} {ver.split('+')[0]} (fixado em packageManager)")

    staged = pkg.get("lint-staged") or {}
    if isinstance(staged, dict):
        for pattern, cmds in staged.items():
            cmds = cmds if isinstance(cmds, list) else [cmds]
            facts.staged_checks.append(
                (pattern, "; ".join(_short_cmd(str(c), 70) for c in cmds)))


def _from_pyproject(data: dict, facts: ProjectFacts) -> None:
    project = data.get("project") or {}
    if not facts.description and isinstance(project.get("description"), str):
        desc = project["description"].strip()
        if desc and desc.lower() != "add your description here":
            facts.description = desc

    if project.get("requires-python"):
        facts.prereqs.append(f"Python {project['requires-python']}")

    deps = []
    for spec in project.get("dependencies") or []:
        m = re.match(r"^\s*([A-Za-z0-9_.\-\[\]]+)\s*(.*)$", str(spec))
        if m:
            deps.append((m.group(1), m.group(2).strip() or "—"))
    facts.dependencies += deps
    _collect_libs({name.split("[")[0].lower(): v for name, v in deps}, facts)

    for name, target in (project.get("scripts") or {}).items():
        facts.scripts.append((name, str(target)))


def _collect_libs(deps: dict, facts: ProjectFacts) -> None:
    by_cat: dict[str, list[str]] = {}
    for dep in deps:
        key = dep.lower()
        if key.startswith("@radix-ui/"):
            key = "radix-ui"
        if key in KNOWN_LIBS:
            cat, label = KNOWN_LIBS[key]
            if label not in by_cat.setdefault(cat, []):
                by_cat[cat].append(label)
    facts.libs = sorted(((cat, " + ".join(labels)) for cat, labels in by_cat.items()
                         if not (facts.stack.framework
                                 and " + ".join(labels) == facts.stack.framework)),
                        key=lambda item: _CATEGORY_ORDER.get(item[0], 99))

    # versão do framework detectado
    for dep, label in (("next", "Next.js"), ("react", "React"), ("vue", "Vue"),
                       ("svelte", "Svelte"), ("@angular/core", "Angular")):
        if dep in deps and facts.stack.framework == label:
            facts.stack.framework = f"{label} {_clean_version(deps[dep])}"
            break


def _read_version_files(app: Path, facts: ProjectFacts) -> None:
    for fname, label in ((".nvmrc", "Node"), (".node-version", "Node"),
                         (".python-version", "Python")):
        text = _read_text(app / fname)
        already = any(p.startswith(label + " ") for p in facts.prereqs)
        if text and text.strip() and not already:
            facts.prereqs.append(f"{label} {text.strip().splitlines()[0]}")


# --- ambiente --------------------------------------------------------------

def _read_env_example(app: Path, facts: ProjectFacts) -> None:
    for fname in ENV_EXAMPLE_FILES:
        text = _read_text(app / fname)
        if text is None:
            continue
        facts.env_file = fname
        comments: list[str] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                comments = []
                continue
            if line.startswith("#"):
                comments.append(line.lstrip("#").strip())
                continue
            line = line.removeprefix("export ").strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            facts.env_vars.append(EnvVar(
                key=key.strip(),
                description=_plain_markdown(" ".join(c for c in comments if c)),
                example=value,
            ))
            comments = []
        return


# --- árvore ----------------------------------------------------------------

def _visible_children(path: Path) -> list[Path]:
    try:
        items = [p for p in path.iterdir()
                 if p.name not in IGNORED_DIRS
                 and not (p.name.startswith(".") and p.is_dir())]
    except OSError:
        return []
    return sorted(items, key=lambda p: (not p.is_dir(), p.name.lower()))


def _build_tree(app: Path, facts: ProjectFacts, max_children: int = 14,
                max_lines: int = 45) -> None:
    root = app / "src" if (app / "src").is_dir() else app
    facts.code_root = "src" if root != app else "."
    label = "src/" if root != app else f"{app.name}/"
    lines = [label]

    children = _visible_children(root)
    for i, child in enumerate(children[:max_children]):
        last = i == min(len(children), max_children) - 1
        branch = "└── " if last else "├── "
        lines.append(branch + child.name + ("/" if child.is_dir() else ""))
        if child.is_dir():
            grand = _visible_children(child)
            entries = [g.name + ("/" if g.is_dir() else "") for g in grand]
            facts.top_dirs.append((child.name, entries))
            pad = "    " if last else "│   "
            for j, name in enumerate(entries[:max_children]):
                sub_last = j == min(len(entries), max_children) - 1
                lines.append(pad + ("└── " if sub_last else "├── ") + name)
            if len(entries) > max_children:
                lines.append(pad + f"    … (+{len(entries) - max_children})")
    if len(children) > max_children:
        lines.append(f"… (+{len(children) - max_children})")

    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + ["…"]
    facts.tree = "\n".join(lines) if len(lines) > 1 else None


# --- ferramentas, hooks, CI ------------------------------------------------

def _detect_tools(app: Path, facts: ProjectFacts) -> None:
    seen: set[str] = set()
    for pattern, tool in TOOL_CONFIGS:
        match = next(iter(sorted(app.glob(pattern))), None)
        if match and match.is_file() and tool not in seen:
            seen.add(tool)
            facts.tools.append((tool, match.name))


HOOK_CMD = re.compile(
    r"\b((?:pnpm|npm|yarn|npx|bun|uv|poetry|make)\s+(?:exec\s+|run\s+)?[\w:.\-]+)")


def _read_husky(app: Path, facts: ProjectFacts) -> None:
    husky = app / ".husky"
    if not husky.is_dir():
        return
    for hook in sorted(husky.iterdir()):
        if not hook.is_file() or hook.name.startswith("_"):
            continue
        text = _read_text(hook) or ""
        cmds: list[str] = []
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith(("#", "echo", "printf")):
                continue
            for m in HOOK_CMD.finditer(s):
                if m.group(1) not in cmds:
                    cmds.append(m.group(1))
        facts.hooks.append((hook.name, ", ".join(cmds) if cmds else "script personalizado"))


def _read_workflows(app: Path, facts: ProjectFacts) -> None:
    wf_dir = app / ".github" / "workflows"
    if not wf_dir.is_dir():
        return
    for wf in sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))):
        text = _read_text(wf)
        if not text:
            continue
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        # PyYAML (YAML 1.1) lê a chave `on:` como o booleano True.
        on = data.get("on", data.get(True))
        workflow = Workflow(file=wf.name, name=str(data.get("name") or wf.stem),
                            triggers=_describe_triggers(on))
        for job in (data.get("jobs") or {}).values():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                uses = str(step.get("uses", ""))
                if uses.startswith("actions/setup-node"):
                    ver = (step.get("with") or {}).get("node-version")
                    if ver:
                        facts.prereqs.append(f"Node {ver} (versão usada no CI)")
                run = step.get("run")
                if not run:
                    continue
                run = str(run).strip()
                cmd = run if "\n" not in run else "(script de várias linhas)"
                workflow.steps.append((str(step.get("name") or "—"), _short_cmd(cmd, 70)))
        facts.workflows.append(workflow)


def _describe_triggers(on) -> str:
    if isinstance(on, str):
        return on
    if isinstance(on, list):
        return ", ".join(map(str, on))
    if isinstance(on, dict):
        parts = []
        for event, cfg in on.items():
            branches = (cfg or {}).get("branches") if isinstance(cfg, dict) else None
            parts.append(f"{event} ({', '.join(branches)})" if branches else str(event))
        return ", ".join(parts)
    return "—"


# --- Docker ----------------------------------------------------------------

def _read_dockerfile(app: Path, facts: ProjectFacts) -> None:
    text = _read_text(app / "Dockerfile")
    if not text:
        return
    info = DockerInfo()
    for raw in text.splitlines():
        line = raw.strip()
        upper = line.upper()
        if upper.startswith("FROM "):
            m = re.match(r"FROM\s+(\S+)(?:\s+AS\s+(\S+))?", line, re.IGNORECASE)
            if m:
                info.stages.append(f"{m.group(1)} ({m.group(2)})" if m.group(2)
                                   else m.group(1))
        elif upper.startswith("EXPOSE "):
            info.ports += line.split()[1:]
        elif upper.startswith("USER "):
            info.user = line.split(None, 1)[1]
        elif upper.startswith(("CMD ", "ENTRYPOINT ")):
            info.cmd = line.split(None, 1)[1]
        elif upper.startswith("ARG "):
            info.build_args.append(line.split(None, 1)[1].split("=")[0])
    facts.docker = info
