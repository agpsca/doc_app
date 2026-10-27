#!/usr/bin/env python
"""Checagem da lógica dependente de plataforma (Linux, WSL, Windows, macOS).

Cobre o que quebrava fora do Linux: a resolução das fontes do PDF, os caminhos
de configuração dos assistentes e o destino padrão do PDF.

Uso:
    uv run python scripts/check_platform.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from doc_app import clients, core
from doc_app.theme import _ARIAL, _DEJAVU, Fonts, _resolve_fonts


def touch(directory: Path, names) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_bytes(b"")


def check_fonts(tmp: Path) -> None:
    linux, win, empty = tmp / "dejavu", tmp / "Fonts", tmp / "vazio"
    touch(linux, _DEJAVU)
    touch(win, _ARIAL + _DEJAVU)   # Windows com DejaVu instalada por fora
    empty.mkdir()

    # nenhuma pasta serve -> dir vazio, para a mensagem de erro aparecer
    assert _resolve_fonts([str(empty)]) == ("", *_DEJAVU)

    # trio completo de DejaVu
    assert _resolve_fonts([str(empty), str(linux)]) == (str(linux), *_DEJAVU)

    # DejaVu ganha de Arial na mesma pasta
    assert _resolve_fonts([str(win)]) == (str(win), *_DEJAVU)

    # só Arial + Consolas (Windows limpo) também serve
    for name in _DEJAVU:
        (win / name).unlink()
    assert _resolve_fonts([str(win)]) == (str(win), *_ARIAL)

    # DOC_APP_FONT_DIR tem prioridade
    with patch.dict(os.environ, {"DOC_APP_FONT_DIR": str(linux)}):
        assert _resolve_fonts([str(win)]) == (str(linux), *_DEJAVU)

    # fonte presente devolve o caminho; ausente explica o que instalar
    assert Fonts(dir=str(linux)).path(_DEJAVU[0]) == str(linux / _DEJAVU[0])
    for fonts in (Fonts(dir=str(empty)), Fonts(dir="")):
        try:
            fonts.path(_DEJAVU[0])
        except FileNotFoundError as exc:
            assert "DOC_APP_FONT_DIR" in str(exc), exc
        else:
            raise AssertionError("fonte ausente deveria falhar com FileNotFoundError")


def check_client_paths() -> None:
    home = Path.home()
    # APPDATA em forma neutra: este check roda em qualquer plataforma
    with patch.object(clients.platform, "system", return_value="Windows"), \
            patch.dict(os.environ, {"APPDATA": "/appdata/Roaming"}):
        assert clients._app_support("Code", "User", "mcp.json") == Path(
            "/appdata/Roaming/Code/User/mcp.json")
    with patch.object(clients.platform, "system", return_value="Darwin"):
        assert clients._app_support("Claude") == home / "Library/Application Support/Claude"
    with patch.object(clients.platform, "system", return_value="Linux"), \
            patch.dict(os.environ, {"XDG_CONFIG_HOME": "/xdg"}):
        assert clients._app_support("Code") == Path("/xdg/Code")

    # executável resolvido pelo PATH (no Windows, com a extensão .cmd/.exe)
    with patch.object(clients.shutil, "which", return_value=r"C:\bin\code.cmd"):
        assert clients._exe("code") == r"C:\bin\code.cmd"
    with patch.object(clients.shutil, "which", return_value=None):
        assert clients._exe("code") == "code"


def check_output_paths(tmp: Path) -> None:
    onedrive = tmp / "OneDrive"
    (onedrive / "Desktop").mkdir(parents=True)
    with patch.dict(os.environ, {"OneDrive": str(onedrive)}):
        assert core.desktop_dir() == onedrive / "Desktop"
    with patch.dict(os.environ, {"OneDrive": str(tmp / "ausente")}), \
            patch.object(core.Path, "home", staticmethod(lambda: tmp)):
        assert core.desktop_dir() == tmp          # sem Desktop: cai na home

    # destino com separador do Windows é tratado como pasta
    assert core.normalize_output(r"C:\docs\\", "app", "full").name == "app-full.pdf"
    assert core.normalize_output("saida", "app", "full").name == "saida.pdf"


def check_windows_paths() -> None:
    """Caminho colado do Explorer, dentro do WSL: convertido pelo wslpath."""
    cases = {
        r"\\wsl.localhost\Distro\home\agpsca\app": "/home/agpsca/app",
        r"\\wsl$\Distro\home\agpsca\app": "/home/agpsca/app",
        r"C:\projetos\app": "/mnt/c/projetos/app",
        r'"C:\projetos\app"': "/mnt/c/projetos/app",      # "Copiar como caminho"
        "/home/agpsca/app": "/home/agpsca/app",           # já em formato Linux
        r"relativo\com\barra": r"relativo\com\barra",     # não é caminho Windows
    }

    def fake_wslpath(cmd, **kwargs):
        raw = cmd[-1]
        unc = re.match(r"^\\\\wsl(?:\$|\.localhost)\\[^\\]+", raw)
        if unc:
            out = raw[unc.end():].replace("\\", "/") or "/"
        elif re.match(r"^[A-Za-z]:[\\/]", raw):
            out = f"/mnt/{raw[0].lower()}/" + raw[3:].replace("\\", "/")
        else:
            return subprocess.CompletedProcess(cmd, 1, "", "wslpath: erro")
        return subprocess.CompletedProcess(cmd, 0, out + "\n", "")

    with patch.object(core.shutil, "which", return_value="/usr/bin/wslpath"), \
            patch.object(core.subprocess, "run", side_effect=fake_wslpath):
        for raw, expected in cases.items():
            assert str(core.parse_path(raw)) == expected, raw
        # destino do PDF no Windows, com barra final: vira pasta
        out = core.normalize_output(r"C:\Users\x\Desktop\\", "app", "full")
        assert str(out) == "/mnt/c/Users/x/Desktop/app-full.pdf", out

    # sem wslpath (Linux puro, Windows) o caminho passa inteiro
    with patch.object(core.shutil, "which", return_value=None):
        assert str(core.parse_path(r"C:\projetos\app")) == r"C:\projetos\app"


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        check_fonts(tmp)
        check_client_paths()
        check_output_paths(tmp)
        check_windows_paths()
    print("ok: fontes, caminhos de assistentes, destino do PDF e caminhos do Windows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
