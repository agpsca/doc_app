#!/usr/bin/env sh
# Instalador do doc_app.
#
# O que faz:
#   1. 📦 prepara o ambiente com `uv sync`
#   2. 🔗 cria um symlink `~/.local/bin/doc_app` -> `bin/doc_app` deste repo
#   3. 🧭 verifica se `~/.local/bin` está no PATH (apenas avisa; não edita seu rc)
#   4. ✅ testa que o comando responde
#   5. 🔌 (opcional, pergunta antes) conecta o servidor MCP aos assistentes de IA
#      encontrados na máquina (Kiro, Cursor, VS Code, Claude, Gemini, Codex...)
#
# Uso:
#   ./scripts/install.sh
#   ./scripts/install.sh --yes      # aceita as perguntas (conecta todos os encontrados)
#   ./scripts/install.sh --no-mcp   # não oferece a conexão com assistentes
#
# Para desinstalar: ./scripts/cleanup.sh

set -eu

ASSUME_YES=0
SKIP_MCP=0
for arg in "$@"; do
    case "$arg" in
        --yes|-y) ASSUME_YES=1 ;;
        --no-mcp) SKIP_MCP=1 ;;
        *) printf 'Opção desconhecida: %s\n' "$arg" >&2; exit 1 ;;
    esac
done

# --- cores (desligadas se não for um terminal) ----------------------------
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

# --- banner ---------------------------------------------------------------
printf '%s\n' ""
printf '%s' "$C"
cat <<'BANNER'
  ╔══════════════════════════════════════════╗
  ║                                          ║
  ║     ▄▀█ doc_app                          ║
  ║     █▄█ gerador de documentação          ║
  ║                                          ║
  ╚══════════════════════════════════════════╝
BANNER
printf '%s' "$Z"
printf '  %s📄 instalador%s\n' "$DIM" "$Z"

# --- raiz do repo ---------------------------------------------------------
# Resolve a raiz subindo a partir da pasta do script até achar o pyproject.toml.
# Assim funciona tanto se o script estiver em scripts/ quanto na raiz.
SCRIPT_DIR="$(cd -P "$(dirname "$0")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
while [ "$REPO_ROOT" != "/" ] && [ ! -f "$REPO_ROOT/pyproject.toml" ]; do
    REPO_ROOT="$(dirname "$REPO_ROOT")"
done
TARGET_BIN="$REPO_ROOT/bin/doc_app"

if [ ! -f "$REPO_ROOT/pyproject.toml" ] || [ ! -f "$TARGET_BIN" ]; then
    err "Não achei a raiz do repositório (pyproject.toml + bin/doc_app)."
    say "   Rode o instalador de dentro do repositório clonado."
    exit 1
fi

# --- 1. uv ----------------------------------------------------------------
step "📦 Verificando o uv e preparando o ambiente"
if ! command -v uv >/dev/null 2>&1; then
    err "'uv' não está instalado."
    say "   Instale em: ${C}https://docs.astral.sh/uv/getting-started/installation/${Z}"
    exit 1
fi
ok "uv encontrado: $(uv --version 2>/dev/null || echo 'ok')"

say "${DIM}   rodando: uv sync --project \"$REPO_ROOT\"${Z}"
if uv sync --project "$REPO_ROOT" >/dev/null 2>&1; then
    ok "Dependências instaladas (ambiente pronto)."
else
    err "Falha no 'uv sync'. Rode manualmente para ver o erro:"
    say "   uv sync --project \"$REPO_ROOT\""
    exit 1
fi

chmod +x "$TARGET_BIN" 2>/dev/null || true

# --- 2. symlink -----------------------------------------------------------
step "🔗 Instalando o comando 'doc_app'"
BIN_HOME="$HOME/.local/bin"
LINK="$BIN_HOME/doc_app"
mkdir -p "$BIN_HOME"

if [ -e "$LINK" ] || [ -L "$LINK" ]; then
    CURRENT="$(readlink "$LINK" 2>/dev/null || echo '?')"
    if [ "$CURRENT" = "$TARGET_BIN" ]; then
        ok "Symlink já aponta para este repo."
    else
        warn "Já existe $LINK (-> $CURRENT)."
        printf '   Sobrescrever? [s/N]: '
        read -r ANS || ANS=""
        case "$ANS" in
            s|S|sim|y|Y|yes)
                ln -sf "$TARGET_BIN" "$LINK"
                ok "Symlink atualizado."
                ;;
            *)
                warn "Mantido o symlink existente. Instalação não concluída."
                exit 0
                ;;
        esac
    fi
else
    ln -s "$TARGET_BIN" "$LINK"
    ok "Symlink criado: $LINK -> $TARGET_BIN"
fi

# --- 3. PATH --------------------------------------------------------------
step "🧭 Conferindo o PATH"
case ":$PATH:" in
    *":$BIN_HOME:"*)
        ok "'$BIN_HOME' já está no PATH."
        ;;
    *)
        warn "'$BIN_HOME' NÃO está no seu PATH."
        say "   Adicione a linha abaixo ao seu ${B}~/.zshrc${Z} (ou ~/.bashrc) e reabra o terminal:"
        printf '\n      %sexport PATH="$HOME/.local/bin:$PATH"%s\n\n' "$C" "$Z"
        say "   ${DIM}(não editei seu arquivo de shell automaticamente)${Z}"
        ;;
esac

# --- 4. teste -------------------------------------------------------------
step "✅ Testando"
if "$TARGET_BIN" list >/dev/null 2>&1; then
    ok "O comando responde."
else
    warn "O comando foi instalado, mas o teste falhou — verifique o ambiente."
fi

# --- 5. assistentes de IA (opcional) ---------------------------------------
if [ "$SKIP_MCP" -eq 0 ]; then
    step "🔌 Conectar a assistentes de IA (MCP)"
    if [ "$ASSUME_YES" -eq 1 ]; then
        uv run --project "$REPO_ROOT" python -m doc_app.clients setup --yes || \
            warn "Algum assistente não foi conectado; veja as mensagens acima."
    else
        uv run --project "$REPO_ROOT" python -m doc_app.clients setup || \
            warn "Algum assistente não foi conectado; veja as mensagens acima."
    fi
fi

# --- fim ------------------------------------------------------------------
printf '\n%s🎉 Pronto!%s Agora você pode usar:\n\n' "$G" "$Z"
say "   ${B}doc_app${Z}                 ${DIM}# painel interativo${Z}"
say "   ${B}doc_app build <app> --type full${Z}"
say "   ${B}doc_app clean${Z}           ${DIM}# limpa o cache${Z}"
say "   ${B}doc_app list${Z}            ${DIM}# lista apps no cache${Z}"
say "   ${B}doc_app connect${Z}         ${DIM}# conecta a assistentes de IA (MCP)${Z}"
printf '\n%sDica:%s se o comando não for encontrado, confira o passo do PATH acima.\n' "$Y" "$Z"
