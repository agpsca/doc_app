#!/usr/bin/env sh
# Cleanup do doc_app — desfaz a instalação e volta ao estado "primeira vez".
#
# O que faz:
#   1. 🔗 remove o symlink `~/.local/bin/doc_app` (se apontar para este repo)
#   2. 🧹 esvazia o cache local (workspace/)
#   3. 🗑️  remove artefatos __pycache__
#   4. (opcional) 📦 remove o .venv com --venv
#
# NÃO apaga o código do app. Uso:
#   ./scripts/cleanup.sh
#   ./scripts/cleanup.sh --venv     # também remove o ambiente .venv
#   ./scripts/cleanup.sh --yes      # não pede confirmação

set -eu

if [ -t 1 ]; then
    B="$(printf '\033[1m')"; DIM="$(printf '\033[2m')"
    G="$(printf '\033[32m')"; Y="$(printf '\033[33m')"
    C="$(printf '\033[36m')"; R="$(printf '\033[31m')"; Z="$(printf '\033[0m')"
else
    B=""; DIM=""; G=""; Y=""; C=""; R=""; Z=""
fi
say()  { printf '%s\n' "$*"; }
ok()   { printf '%s✅ %s%s\n' "$G" "$*" "$Z"; }
warn() { printf '%s⚠️  %s%s\n' "$Y" "$*" "$Z"; }
err()  { printf '%s❌ %s%s\n' "$R" "$*" "$Z" >&2; }
step() { printf '\n%s▸ %s%s\n' "$B" "$*" "$Z"; }

REMOVE_VENV=0
ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        --venv) REMOVE_VENV=1 ;;
        --yes|-y) ASSUME_YES=1 ;;
        *) err "Opção desconhecida: $arg"; exit 1 ;;
    esac
done

printf '\n%s' "$C"
cat <<'BANNER'
  ╔══════════════════════════════════════════╗
  ║                                          ║
  ║     ▄▀█ doc_app                          ║
  ║     █▄█ cleanup                          ║
  ║                                          ║
  ╚══════════════════════════════════════════╝
BANNER
printf '%s' "$Z"
printf '  %s🧹 desfazendo a instalação%s\n' "$DIM" "$Z"

# raiz do repo (sobe até achar o pyproject.toml)
SCRIPT_DIR="$(cd -P "$(dirname "$0")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
while [ "$REPO_ROOT" != "/" ] && [ ! -f "$REPO_ROOT/pyproject.toml" ]; do
    REPO_ROOT="$(dirname "$REPO_ROOT")"
done
if [ ! -f "$REPO_ROOT/pyproject.toml" ]; then
    err "Não achei a raiz do repositório (pyproject.toml)."
    exit 1
fi
TARGET_BIN="$REPO_ROOT/bin/doc_app"

say ""
say "   Será removido:"
say "     🔗 symlink ~/.local/bin/doc_app (se for deste repo)"
say "     🔌 conexões 'doc-app' nos assistentes de IA (só as deste repo; o resto fica)"
say "     🧹 cache    $REPO_ROOT/workspace/*"
say "     🗑️  artefatos __pycache__"
[ "$REMOVE_VENV" -eq 1 ] && say "     📦 ambiente $REPO_ROOT/.venv"
say "   ${DIM}(o código do app NÃO é apagado)${Z}"

if [ "$ASSUME_YES" -ne 1 ]; then
    printf '\n   Confirmar? [s/N]: '
    read -r ANS || ANS=""
    case "$ANS" in
        s|S|sim|y|Y|yes) ;;
        *) warn "Cancelado."; exit 0 ;;
    esac
fi

# 1. symlink
step "🔗 Removendo o comando global"
LINK="$HOME/.local/bin/doc_app"
if [ -L "$LINK" ]; then
    CURRENT="$(readlink "$LINK" 2>/dev/null || echo '?')"
    if [ "$CURRENT" = "$TARGET_BIN" ]; then
        rm -f "$LINK"
        ok "Symlink removido: $LINK"
    else
        warn "Symlink aponta para outro lugar ($CURRENT); não mexi."
    fi
else
    ok "Nenhum symlink a remover."
fi

# 1b. conexões MCP nos assistentes de IA
step "🔌 Removendo as conexões com assistentes de IA"
if RES="$(uv run --project "$REPO_ROOT" python -m doc_app.clients unregister all 2>&1)"; then
    if [ -n "$RES" ]; then
        printf '%s\n' "$RES" | while IFS= read -r line; do ok "$line"; done
    else
        ok "Nenhuma conexão a remover."
    fi
else
    warn "Alguma conexão não foi removida:"
    printf '%s\n' "$RES" | sed 's/^/     /'
fi

# 2. cache
step "🧹 Esvaziando o cache"
if [ -d "$REPO_ROOT/workspace" ]; then
    rm -rf "$REPO_ROOT/workspace"/* 2>/dev/null || true
    ok "Cache esvaziado."
else
    ok "Cache já estava vazio."
fi

# 3. pycache
step "🗑️  Removendo artefatos"
find "$REPO_ROOT/src" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
ok "Artefatos removidos."

# 4. venv (opcional)
if [ "$REMOVE_VENV" -eq 1 ]; then
    step "📦 Removendo o ambiente"
    rm -rf "$REPO_ROOT/.venv"
    ok ".venv removido (rode ./scripts/install.sh para recriar)."
fi

printf '\n%s✨ Limpo!%s O repositório está como numa cópia recém-clonada.\n' "$G" "$Z"
