"""Interface de linha de comando do doc_app.

Dois modos:

  Painel interativo (padrão, sem argumentos):
      doc-app
    Pergunta o caminho do app, o tipo de documentação e onde salvar.
    Oferece criar um esqueleto quando o app ainda não tem doc no cache.

  Direto (scriptável):
      doc-app build <app> --type full -o saida.pdf
      doc-app clean [<app>] [--yes]
      doc-app list

Tipos de documentação: brand (marca e regras), development (código) e
full (os dois no mesmo PDF).

O `workspace/` é um CACHE local (no .gitignore): guarda um YAML por app e por
tipo em `workspace/<app>/<tipo>.yaml`. O comando `clean` limpa esse cache.
O destino padrão do PDF é ~/Desktop/<app>-<tipo>.pdf.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .brand import to_hex
from .core import (DEFAULT_MARK, DEFAULT_TYPE, build, cache_dir, create_doc,
                   default_output, doc_path, normalize_output, workspace_root)
from .extract import ProjectFacts
from .theme import DOC_TYPE_LABELS, DOC_TYPES

# estilos ANSI leves (desligados se a saída não for um terminal)
if sys.stdout.isatty():
    _DIM, _Z = "\033[2m", "\033[0m"
else:
    _DIM, _Z = "", ""


# --- geração ---------------------------------------------------------------

def generate(app_name: str, doc_type: str, output: Path,
             mark: str | None = None) -> int:
    """Gera o PDF. `mark` (ex.: "Uso interno") aplica a marca de
    classificação só nesta geração, sem alterar o YAML do cache."""
    try:
        res = build(app_name, doc_type, output, mark)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    cls = res.theme.classification
    label = f"{res.doc_type}, {cls.lower()}" if cls else res.doc_type
    print(f"PDF gerado ({label}): {res.output}  ({res.blocks} blocos)")
    return 0


def ensure_skeleton(app_path: Path, doc_type: str, *, assume_yes: bool) -> bool:
    """Cria o esqueleto do tipo pedido se não existir. True se há doc pronto."""
    app_name = app_path.name
    if doc_path(app_name, doc_type).exists():
        return True

    from .extract import extract_facts
    facts = extract_facts(app_path)
    print(f"\n📭 Ainda não há documentação '{doc_type}' para {app_name!r} no cache.")
    print(f"🔎 Detectei: {facts.stack.summary()}")
    found = _facts_summary(facts)
    if found:
        print(f"📋 Encontrei: {found}")

    if not assume_yes and sys.stdin.isatty():
        resp = _ask("✨ Criar a documentação inicial com esses dados? [S/n]: ",
                    default="s").lower()
        if resp not in ("s", "sim", "y", "yes", ""):
            print("❌ Cancelado.")
            return False

    res = create_doc(app_path, doc_type)
    if res.facts.stack.kind in ("frontend", "fullstack"):
        if res.colors:
            c = res.colors
            print(f"🎨 Cores da marca detectadas: principal {to_hex(c.brand)}, "
                  f"escura {to_hex(c.dark)}, destaque {to_hex(c.accent)}")
        else:
            print("🎨 Não encontrei cores de marca no app; usando a paleta do doc_app.")
    print(f"📝 Documentação criada: {res.path}")
    print(f"   {_DIM}{res.todos} trecho(s) marcados com (TODO) para completar.{_Z}")
    return True


def _facts_summary(f: ProjectFacts) -> str:
    parts = []
    if f.readme_intro or f.description:
        parts.append("README")
    if f.scripts:
        parts.append(f"{len(f.scripts)} scripts")
    if f.env_vars:
        parts.append(f"{len(f.env_vars)} variáveis de ambiente")
    deps = len(f.dependencies) + len(f.dev_dependencies)
    if deps:
        parts.append(f"{deps} dependências")
    if f.hooks:
        parts.append(f"{len(f.hooks)} git hook(s)")
    if f.workflows:
        parts.append(f"{len(f.workflows)} workflow(s) de CI")
    if f.docker:
        parts.append("Dockerfile")
    return ", ".join(parts)


# --- comandos diretos ------------------------------------------------------

def cmd_build(args) -> int:
    app_path = Path(args.app).expanduser()
    if not app_path.is_dir():
        print(f"App não encontrado (não é um diretório): {app_path}",
              file=sys.stderr)
        return 1
    doc_type = args.doc_type
    if not ensure_skeleton(app_path, doc_type, assume_yes=args.yes):
        return 1
    app_name = app_path.name
    if args.output:
        out = normalize_output(args.output, app_name, doc_type)
    else:
        out = default_output(app_name, doc_type)
    mark = args.mark or (DEFAULT_MARK if args.internal else None)
    return generate(app_name, doc_type, out, mark=mark)


def cmd_clean(args) -> int:
    root = workspace_root()
    if args.app:
        target = cache_dir(args.app)
        if not target.exists():
            print(f"Nada a limpar: {target} não existe.")
            return 0
        if not _confirm_clean([target], args.yes):
            return 0
        shutil.rmtree(target)
        print(f"Cache removido: {target}")
        return 0

    if not root.exists() or not any(root.iterdir()):
        print("Cache já está vazio.")
        return 0
    alvos = [p for p in root.iterdir() if p.is_dir()]
    if not _confirm_clean(alvos, args.yes):
        return 0
    for p in alvos:
        shutil.rmtree(p)
    print(f"Cache limpo ({len(alvos)} app(s) removido(s)).")
    return 0


def cmd_list(_args) -> int:
    root = workspace_root()
    if not root.exists() or not any(root.iterdir()):
        print(f"Cache vazio ({root}).")
        return 0
    print(f"Apps no cache ({root}):")
    for p in sorted(root.iterdir()):
        if p.is_dir():
            tipos = sorted(f.stem for f in p.glob("*.yaml") if f.stem in DOC_TYPES)
            print(f"  • {p.name}: {', '.join(tipos) if tipos else '(vazio)'}")
    return 0


def _confirm_clean(targets: list[Path], assume_yes: bool) -> bool:
    print("Será(ão) removido(s):")
    for t in targets:
        print(f"  - {t}")
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print("Sem terminal interativo; use --yes para confirmar.", file=sys.stderr)
        return False
    return _ask("Confirmar remoção? [s/N]: ", default="n").lower() in ("s", "sim", "y", "yes")


# --- painel interativo -----------------------------------------------------

BANNER = """
  ╔══════════════════════════════════════════╗
  ║   📄  doc_app · gerador de documentação  ║
  ╚══════════════════════════════════════════╝
"""


class _ExitPanel(Exception):
    """Sinaliza que o usuário pediu para sair (Ctrl-C)."""


def _ask(prompt: str, default: str = "") -> str:
    """Lê uma entrada. Ctrl-C sai do app; Ctrl-D (EOF) vale como vazio/cancelar."""
    try:
        resp = input(prompt).strip()
    except KeyboardInterrupt:
        raise _ExitPanel from None
    except EOFError:
        print()
        return default
    return resp or default


def _choose(prompt: str, options: list[str], default_index: int = 0) -> int:
    for i, opt in enumerate(options, 1):
        print(f"   {i}.  {opt}")
    while True:
        raw = _ask(f"\n{prompt} [{default_index + 1}]: ", str(default_index + 1))
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("   ⚠️  Opção inválida, tente de novo.")


def _ask_app_path() -> Path | None:
    """Pede o caminho do app, revalidando até ser um diretório (0 cancela)."""
    while True:
        raw = _ask("\n📂 Caminho do app a documentar (0 cancela): ")
        if raw == "0":
            return None
        if not raw:
            print("   ⚠️  Informe um caminho, ou digite 0 para cancelar.")
            continue
        path = Path(raw).expanduser()
        if path.is_dir():
            return path
        print(f"   ⚠️  Não encontrei a pasta: {path}")


def cmd_panel(_args) -> int:
    print(BANNER)
    print(f"   {_DIM}dica: pressione Ctrl-C a qualquer momento para sair.{_Z}")
    try:
        return _run_panel()
    except _ExitPanel:
        print("\n\n👋 Saindo do doc_app. Até logo!")
        return 0


def _run_panel() -> int:
    acao = _choose("👉 O que deseja fazer?",
                   ["📝  Gerar documentação de um app",
                    "🔎  Ver assistentes conectados",
                    "🔌  Conectar a assistentes de IA (MCP)",
                    "🧹  Limpar cache",
                    "🚪  Sair"])
    if acao == 4:
        print("\n👋 Até logo!")
        return 0
    if acao == 1:
        print()
        return cmd_connections(argparse.Namespace(all=False))
    if acao == 2:
        print()
        return cmd_connect(argparse.Namespace(yes=False))
    if acao == 3:
        print()
        return cmd_clean(argparse.Namespace(app=None, yes=False))

    # gerar
    app_path = _ask_app_path()
    if app_path is None:
        print("\n❌ Cancelado.")
        return 0

    types = list(DOC_TYPES)
    type_idx = _choose("📚 Qual o tipo de documentação?",
                       [DOC_TYPE_LABELS[t] for t in types])
    doc_type = types[type_idx]

    if not ensure_skeleton(app_path, doc_type, assume_yes=False):
        return 1

    mark = _ask_mark()

    app_name = app_path.name
    default = default_output(app_name, doc_type)
    print("\n💾 Onde salvar o PDF?")
    print(f"   {_DIM}Enter usa o padrão:{_Z} {default}")
    dest = _ask("   > ")
    out = normalize_output(dest, app_name, doc_type) if dest else default

    print("\n⏳ Gerando...")
    rc = generate(app_name, doc_type, out, mark=mark)
    if rc == 0:
        print("🎉 Concluído!")
    return rc


def _ask_mark() -> str | None:
    """Pergunta se o PDF leva marca de uso interno e qual o texto."""
    idx = _choose("🔒 Marcar o documento como restrito?",
                  ["Não, documento público",
                   f"Sim, \"{DEFAULT_MARK}\"",
                   "Sim, com outro texto (ex.: Confidencial)"])
    if idx == 0:
        return None
    if idx == 1:
        return DEFAULT_MARK
    while True:
        text = _ask("   Texto da marca: ")
        if text:
            return text[:40]
        print("   ⚠️  Digite um texto, ou Ctrl-C para sair.")


# --- parser ----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doc-app",
        description="Gera documentação em PDF a partir de uma DSL de blocos.",
    )
    sub = parser.add_subparsers(dest="command")

    b = sub.add_parser("build", help="Gera o PDF de um app.")
    b.add_argument("app", help="Caminho do app a documentar.")
    b.add_argument("--type", "-t", dest="doc_type", choices=list(DOC_TYPES),
                   default=DEFAULT_TYPE,
                   help="Tipo de documentação: brand, development ou full "
                        "(padrão: brand).")
    b.add_argument("--output", "-o", help="Caminho de saída do PDF.")
    b.add_argument("--yes", "-y", action="store_true",
                   help="Não pergunta (cria esqueleto e usa padrões).")
    b.add_argument("--internal", action="store_true",
                   help=f"Marca o PDF como \"{DEFAULT_MARK}\" (marca d'água, "
                        "selo na capa e aviso no rodapé).")
    b.add_argument("--mark", metavar="TEXTO",
                   help="Marca com um texto próprio (ex.: \"Confidencial\").")
    b.set_defaults(func=cmd_build)

    c = sub.add_parser("clean", help="Limpa o cache (workspace).")
    c.add_argument("app", nargs="?", help="Limpa só este app; sem argumento, tudo.")
    c.add_argument("--yes", "-y", action="store_true", help="Não pede confirmação.")
    c.set_defaults(func=cmd_clean)

    l = sub.add_parser("list", help="Lista os apps no cache.")
    l.set_defaults(func=cmd_list)

    k = sub.add_parser("connect",
                       help="Conecta o doc_app (via MCP) aos assistentes de IA instalados.")
    k.add_argument("--yes", "-y", action="store_true",
                   help="Conecta em todos os assistentes encontrados, sem perguntar.")
    k.set_defaults(func=cmd_connect)

    s = sub.add_parser("connections",
                       help="Mostra em quais assistentes de IA o doc_app está conectado.")
    s.add_argument("--all", "-a", action="store_true",
                   help="Inclui os assistentes que não estão instalados.")
    s.set_defaults(func=cmd_connections)

    return parser


def cmd_connections(args) -> int:
    from .clients import show_status
    print("🔎 Assistentes de IA e o doc_app\n")
    return show_status(show_all=args.all)


def cmd_connect(args) -> int:
    from .clients import setup
    print("🔌 Conectar o doc_app a assistentes de IA\n")
    return setup(assume_yes=args.yes)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if not getattr(args, "command", None):
            return cmd_panel(args)
        return args.func(args)
    except (_ExitPanel, KeyboardInterrupt):
        print("\n👋 Saindo do doc_app.")
        return 130  # convenção para interrupção por SIGINT


if __name__ == "__main__":
    raise SystemExit(main())
