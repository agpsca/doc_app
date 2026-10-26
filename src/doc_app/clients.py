"""Registro do servidor MCP do doc_app em clientes de IA.

O servidor (`doc-app-mcp`) é MCP padrão e funciona com qualquer cliente. Este
módulo só automatiza a configuração dos clientes conhecidos; para os outros,
`snippet()` devolve o bloco para copiar.

Regras de segurança:
- só a entrada "doc-app" é criada ou removida; o resto do arquivo fica igual;
- antes de alterar um arquivo, uma cópia vai para <arquivo>.bak;
- arquivo que não é JSON puro (ex.: com comentários) não é tocado;
- uma entrada "doc-app" que aponta para outro repositório não é removida.

Uso:
    uv run --project <raiz> python -m doc_app.clients setup [--yes]
    uv run --project <raiz> python -m doc_app.clients status [--all]
    uv run --project <raiz> python -m doc_app.clients list
    uv run --project <raiz> python -m doc_app.clients register <cliente|detected>
    uv run --project <raiz> python -m doc_app.clients unregister <cliente|all>
    uv run --project <raiz> python -m doc_app.clients snippet
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

SERVER_NAME = "doc-app"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def launch() -> tuple[str, list[str]]:
    return "uv", ["run", "--project", str(repo_root()), "doc-app-mcp"]


def _home() -> Path:
    return Path.home()


def _strip_jsonc(text: str) -> str:
    """Remove comentários // e /* */ e vírgulas finais (fora de strings)."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            out.append(ch)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        else:
            out.append(ch)
        i += 1
    import re
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def _app_support(*parts: str) -> Path:
    """Diretório de configuração de apps desktop (Linux: XDG; macOS: Library)."""
    if platform.system() == "Darwin":
        return _home().joinpath("Library", "Application Support", *parts)
    base = os.environ.get("XDG_CONFIG_HOME") or str(_home() / ".config")
    return Path(base).joinpath(*parts)


# --- clientes ---------------------------------------------------------------

@dataclass
class Client:
    id: str
    name: str

    def installed(self) -> bool: ...
    def status(self) -> str: ...        # ausente | atual | outro | erro: ...
    def register(self) -> str: ...
    def unregister(self) -> str: ...
    def where(self) -> str: ...


class JsonClient(Client):
    """Clientes que guardam os servidores num JSON (`mcpServers` ou `servers`)."""

    def __init__(self, id: str, name: str, path_fn, key: str = "mcpServers",
                 vscode_style: bool = False):
        super().__init__(id, name)
        self._path_fn = path_fn
        self.key = key
        self.vscode_style = vscode_style

    @property
    def path(self) -> Path:
        return self._path_fn()

    def where(self) -> str:
        return str(self.path)

    def installed(self) -> bool:
        return self.path.exists() or self.path.parent.is_dir()

    def entry(self) -> dict:
        command, args = launch()
        if self.vscode_style:
            return {"type": "stdio", "command": command, "args": args}
        return {"command": command, "args": args}

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{self.path} não é JSON puro (talvez tenha comentários): {exc}. "
                "Nada foi alterado; adicione a entrada à mão com `snippet`.") from exc
        if not isinstance(data, dict) or not isinstance(data.get(self.key, {}), dict):
            raise RuntimeError(f"{self.path} não tem o formato esperado. Nada foi alterado.")
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            shutil.copy2(self.path, self.path.with_name(self.path.name + ".bak"))
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        tmp.replace(self.path)

    def status(self) -> str:
        try:
            data = self._load()
        except RuntimeError as exc:
            try:   # arquivo com comentários (JSONC): só leitura
                data = json.loads(_strip_jsonc(self.path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                return f"erro: {exc}"
        current = (data.get(self.key) or {}).get(SERVER_NAME)
        if current is None:
            return "ausente"
        return "atual" if current.get("args") == launch()[1] else "outro"

    def register(self) -> str:
        data = self._load()
        servers = data.setdefault(self.key, {})
        if servers.get(SERVER_NAME) == self.entry():
            return "já registrado"
        servers[SERVER_NAME] = self.entry()
        self._save(data)
        return "registrado"

    def unregister(self) -> str:
        if self.status() == "ausente":
            return "não estava registrado"
        data = self._load()
        servers = data.get(self.key) or {}
        current = servers.get(SERVER_NAME)
        if current is None:
            return "não estava registrado"
        if current.get("args") != launch()[1]:
            return "aponta para outro repositório; mantido"
        del servers[SERVER_NAME]
        self._save(data)
        return "removido"


class ClaudeCodeClient(Client):
    """Claude Code: o próprio CLI grava a configuração (escopo de usuário)."""

    def where(self) -> str:
        return "claude mcp (escopo user)"

    def installed(self) -> bool:
        return shutil.which("claude") is not None

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["claude", "mcp", *args], capture_output=True,
                              text=True, timeout=60)

    def status(self) -> str:
        if not self.installed():
            return "ausente"
        res = self._run("get", SERVER_NAME)
        if res.returncode != 0:
            return "ausente"
        return "atual" if str(repo_root()) in res.stdout else "outro"

    def register(self) -> str:
        if self.status() == "atual":
            return "já registrado"
        self._run("remove", "--scope", "user", SERVER_NAME)
        command, args = launch()
        res = self._run("add", "--scope", "user", SERVER_NAME, "--", command, *args)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or res.stdout.strip())
        return "registrado"

    def unregister(self) -> str:
        st = self.status()
        if st == "ausente":
            return "não estava registrado"
        if st == "outro":
            return "aponta para outro repositório; mantido"
        res = self._run("remove", "--scope", "user", SERVER_NAME)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or res.stdout.strip())
        return "removido"


class CodexClient(Client):
    """Codex: configuração em TOML, gravada pelo próprio CLI (`codex mcp`)."""

    @property
    def path(self) -> Path:
        return Path(os.environ.get("CODEX_HOME") or _home() / ".codex") / "config.toml"

    def where(self) -> str:
        return str(self.path)

    def installed(self) -> bool:
        return shutil.which("codex") is not None

    def status(self) -> str:
        if not self.path.exists():
            return "ausente"
        try:
            data = tomllib.loads(self.path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            return f"erro: {exc}"
        current = (data.get("mcp_servers") or {}).get(SERVER_NAME)
        if current is None:
            return "ausente"
        return "atual" if current.get("args") == launch()[1] else "outro"

    def _run(self, *args: str) -> None:
        res = subprocess.run(["codex", "mcp", *args], capture_output=True, text=True,
                             timeout=60)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or res.stdout.strip())

    def register(self) -> str:
        st = self.status()
        if st == "atual":
            return "já registrado"
        if not self.installed():
            raise RuntimeError("comando 'codex' não encontrado no PATH.")
        if st == "outro":
            self._run("remove", SERVER_NAME)
        command, args = launch()
        self._run("add", SERVER_NAME, "--", command, *args)
        return "registrado"

    def unregister(self) -> str:
        st = self.status()
        if st == "ausente":
            return "não estava registrado"
        if st == "outro":
            return "aponta para outro repositório; mantido"
        if not self.installed():
            raise RuntimeError("comando 'codex' não encontrado; remova a seção "
                               f"[mcp_servers.{SERVER_NAME}] de {self.path} à mão.")
        self._run("remove", SERVER_NAME)
        return "removido"


def _vscode_user_mcp() -> Path:
    return _app_support("Code", "User", "mcp.json")


class VSCodeClient(JsonClient):
    """VS Code: o mcp.json de usuário costuma ter comentários (JSONC). Quando
    não dá para editar como JSON puro, usa o comando oficial `code --add-mcp`."""

    def __init__(self):
        super().__init__("vscode", "VS Code (Copilot)", _vscode_user_mcp,
                         key="servers", vscode_style=True)

    def installed(self) -> bool:
        return super().installed() or shutil.which("code") is not None

    def register(self) -> str:
        try:
            return super().register()
        except RuntimeError:
            if not shutil.which("code"):
                raise
        command, args = launch()
        spec = json.dumps({"name": SERVER_NAME, "type": "stdio",
                           "command": command, "args": args})
        res = subprocess.run(["code", "--add-mcp", spec], capture_output=True,
                             text=True, timeout=60)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or res.stdout.strip())
        return "registrado (via code --add-mcp)"

    def unregister(self) -> str:
        try:
            return super().unregister()
        except RuntimeError as exc:
            raise RuntimeError(
                f"{self.path} tem comentários; remova a entrada \"{SERVER_NAME}\" à mão "
                "(no VS Code: MCP: Open User Configuration).") from exc


CLIENTS: dict[str, Client] = {c.id: c for c in [
    JsonClient("kiro", "Kiro", lambda: _home() / ".kiro" / "settings" / "mcp.json"),
    JsonClient("cursor", "Cursor", lambda: _home() / ".cursor" / "mcp.json"),
    JsonClient("windsurf", "Windsurf",
               lambda: _home() / ".codeium" / "windsurf" / "mcp_config.json"),
    JsonClient("gemini", "Gemini CLI", lambda: _home() / ".gemini" / "settings.json"),
    JsonClient("claude-desktop", "Claude Desktop",
               lambda: _app_support("Claude", "claude_desktop_config.json")),
    JsonClient("copilot-cli", "GitHub Copilot CLI",
               lambda: Path(os.environ.get("COPILOT_HOME") or _home() / ".copilot")
               / "mcp-config.json"),
    VSCodeClient(),
    ClaudeCodeClient("claude-code", "Claude Code"),
    CodexClient("codex", "Codex"),
]}


def snippet() -> str:
    """Configuração genérica para clientes que não estão na lista."""
    command, args = launch()
    return json.dumps({"mcpServers": {SERVER_NAME: {"command": command, "args": args}}},
                      indent=2, ensure_ascii=False)


# --- painel de conexão --------------------------------------------------------

def show_status(show_all: bool = False) -> int:
    """Mostra em quais assistentes o doc_app está conectado. Só lê."""
    marks = {"atual": "✅ conectado", "outro": "⚠️  aponta para outro repositório",
             "ausente": "·  não conectado"}
    clients = [c for c in CLIENTS.values() if show_all or c.installed()]
    connected = 0
    for c in clients:
        st = c.status()
        if st == "atual":
            connected += 1
        label = marks.get(st, f"❌ {st}")
        inst = "" if c.installed() else "  (não instalado)"
        print(f"   {c.name:<20} {label}{inst}")
        print(f"   {'':<20} {c.where()}")
    if not clients:
        print("   Nenhum assistente conhecido encontrado nesta máquina.")
    print(f"\n   {connected} de {len(clients)} assistente(s) com o doc_app conectado.")
    if connected < len(clients):
        print("   Para conectar: doc_app connect")
    return 0

def setup(assume_yes: bool = False) -> int:
    """Painel interativo: mostra os clientes encontrados e registra nos escolhidos."""
    found = [c for c in CLIENTS.values() if c.installed()]
    print("   O servidor MCP do doc_app funciona com qualquer assistente compatível.")
    print("   Só a entrada 'doc-app' é adicionada; o arquivo anterior vira .bak.\n")
    if not found:
        print("   Nenhum assistente conhecido encontrado nesta máquina.")
        print("   Para configurar outro cliente, use este bloco:\n")
        print("\n".join("   " + line for line in snippet().splitlines()))
        return 0

    marks = {"atual": "✅ já conectado", "outro": "⚠️  aponta para outro repositório",
             "ausente": "· não conectado"}
    for i, c in enumerate(found, 1):
        st = c.status()
        label = marks.get(st, f"❌ {st}")
        print(f"   {i}. {c.name:<20} {label}")

    pending = [c for c in found if c.status() != "atual"]
    if not pending:
        print("\n✅ Todos os assistentes encontrados já estão conectados.")
        return 0

    if assume_yes:
        chosen = pending
    elif not sys.stdin.isatty():
        print("\n   Sem terminal interativo; pulei. Use: "
              "python -m doc_app.clients register detected")
        return 0
    else:
        chosen = _ask_choice(found)
        if chosen is None:
            print("   Pulado. Para conectar depois: doc_app connect")
            return 0

    failed = 0
    for c in chosen:
        try:
            print(f"✅ {c.name}: {c.register()}.")
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            failed += 1
            print(f"❌ {c.name}: {exc}", file=sys.stderr)
    if chosen and not failed:
        print("\n   Reinicie o assistente (ou recarregue os servidores MCP) e peça:")
        print('   "documente o app em <caminho> com o doc_app".')
    return 1 if failed else 0


def _ask_choice(found: list[Client]) -> list[Client] | None:
    while True:
        try:
            raw = input("\n   Conectar quais? (ex.: 1,3 · t = todos · 0 = nenhum): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if raw == "0":
            return None
        if raw.lower() in ("t", "todos"):
            return [c for c in found if c.status() != "atual"]
        try:
            idx = sorted({int(x) for x in raw.replace(" ", "").split(",") if x})
        except ValueError:
            idx = []
        if idx and all(1 <= i <= len(found) for i in idx):
            return [found[i - 1] for i in idx]
        print("   ⚠️  Opção inválida, tente de novo.")


# --- CLI ---------------------------------------------------------------------

def _resolve(target: str, only_installed: bool) -> list[Client]:
    if target in ("detected", "all"):
        return [c for c in CLIENTS.values() if not only_installed or c.installed()]
    ids = [t.strip() for t in target.split(",") if t.strip()]
    unknown = [i for i in ids if i not in CLIENTS]
    if unknown:
        raise SystemExit(f"cliente(s) desconhecido(s): {', '.join(unknown)}. "
                         f"Use: {', '.join(CLIENTS)}.")
    return [CLIENTS[i] for i in ids]


def main(argv: list[str]) -> int:
    commands = ("list", "register", "unregister", "snippet", "setup", "status")
    if not argv or argv[0] not in commands:
        print(__doc__.split("Uso:")[1], file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd == "status":
        return show_status(show_all="--all" in argv[1:])
    if cmd == "setup":
        return setup(assume_yes="--yes" in argv[1:])
    if cmd == "snippet":
        print(snippet())
        return 0
    if cmd == "list":
        for c in CLIENTS.values():
            inst = "instalado" if c.installed() else "não encontrado"
            print(f"{c.id}\t{c.name}\t{inst}\t{c.status()}\t{c.where()}")
        return 0
    if len(argv) != 2:
        print(f"uso: python -m doc_app.clients {cmd} <cliente|"
              f"{'detected' if cmd == 'register' else 'all'}>", file=sys.stderr)
        return 2
    failed = 0
    targets = _resolve(argv[1], only_installed=(cmd == "register"))
    for c in targets:
        if cmd == "unregister" and c.status() == "ausente":
            continue
        try:
            msg = c.register() if cmd == "register" else c.unregister()
            print(f"{c.name}: {msg}")
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            failed += 1
            print(f"{c.name}: erro: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
