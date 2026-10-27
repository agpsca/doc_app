#!/usr/bin/env python
"""Checagem do menu interativo.

Cobre o que a opção "Voltar" promete: cada submenu (tipo de documentação,
marca de restrição, caminho do app) volta ao menu principal sem gerar PDF, e
o painel só termina quando o usuário escolhe Sair. Cobre também a memória do
último app documentado (Enter repete, pasta apagada é esquecida) e o YAML do
cache (criado quando falta, reaproveitado quando já existe).

Uso:
    uv run python scripts/check_menu.py
"""

from __future__ import annotations

import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from doc_app import cli, core
from doc_app.core import FORMATS
from doc_app.theme import DOC_TYPES

# o prompt vai para o input (que está mockado): conta pelo item impresso
MENU = "Gerar documentação de um app"
GERAR, SAIR = "1", "5"
VOLTAR_TIPO = str(len(DOC_TYPES) + 1)   # último item do submenu de tipos
VOLTAR_FORMATO = str(len(FORMATS) + 1)  # 3 formatos + Voltar
VOLTAR_MARCA = "4"                      # 3 opções de marca + Voltar


def boom(*_a, **_k):
    raise AssertionError("não deveria gerar PDF depois de Voltar")


class Tty(io.StringIO):
    """stdin que se diz interativo: o painel pergunta sempre, com ou sem
    terminal de verdade, então as respostas da checagem batem."""

    def isatty(self) -> bool:
        return True


def run_panel(answers: list[str]) -> str:
    """Roda o painel com respostas pré-definidas; devolve a saída impressa."""
    it = iter(answers)
    out = io.StringIO()
    with patch("builtins.input", lambda *_: next(it)), \
            patch.object(cli.sys, "stdin", Tty()), \
            patch.object(cli, "generate", boom), \
            redirect_stdout(out):
        rc = cli.cmd_panel(None)
    assert rc == 0, rc
    sobrando = list(it)
    assert not sobrando, f"respostas não consumidas: {sobrando}"
    return out.getvalue()


def check_back_from_type(app: Path) -> None:
    text = run_panel([GERAR, str(app), VOLTAR_TIPO, SAIR])
    assert text.count(MENU) == 2, text          # voltou para o menu
    assert "Até logo" in text


def check_back_from_format(app: Path) -> None:
    text = run_panel([GERAR, str(app), "1", VOLTAR_FORMATO, SAIR])
    assert text.count(MENU) == 2, text
    assert "Marcar o documento" not in text   # parou antes da marca


def check_back_from_mark(app: Path) -> None:
    with patch.object(cli, "ensure_skeleton", return_value=True):
        text = run_panel([GERAR, str(app), "1", "1", VOLTAR_MARCA, SAIR])
    assert text.count(MENU) == 2, text
    assert "Onde salvar" not in text          # parou antes de pedir o destino


def check_back_from_path(app: Path) -> None:
    text = run_panel([GERAR, "0", GERAR, str(app), VOLTAR_TIPO, SAIR])
    assert text.count(MENU) == 3, text


def check_eof_exits() -> None:
    """Ctrl-D numa pergunta sem padrão sai em vez de repetir para sempre.
    Roda antes das outras: sem último app lembrado, a pergunta do caminho é a
    primeira sem padrão."""
    def eof(*_a):
        raise EOFError

    out = io.StringIO()
    with patch("builtins.input", eof), redirect_stdout(out):
        assert cli.cmd_panel(None) == 0
    assert "Saindo do doc_app" in out.getvalue()


def check_last_app(app: Path) -> None:
    """Enter no caminho repete o último app; pasta apagada é esquecida."""
    run_panel([GERAR, str(app), VOLTAR_TIPO, SAIR])
    assert core.last_app() == app.resolve()

    text = run_panel([GERAR, "", VOLTAR_TIPO, SAIR])     # Enter = último app
    assert str(app.resolve()) in text
    assert "Não encontrei" not in text

    core.save_last_app(app / "apagada")
    assert core.last_app() is None


def check_keeps_existing_yaml(app: Path) -> None:
    """O fluxo de gerar cria o YAML quando falta e, na segunda vez, reaproveita
    o que está no cache em vez de recriar (não perde o texto já escrito)."""
    criar = [GERAR, str(app), "1", "1", "s", VOLTAR_MARCA, SAIR]
    text = run_panel(criar)
    dp = core.doc_path(app.name, "brand")
    assert dp.exists(), text
    assert "Documentação criada" in text

    antes = dp.read_text(encoding="utf-8")
    text = run_panel([GERAR, str(app), "1", "1", VOLTAR_MARCA, SAIR])
    assert "Documentação criada" not in text, text
    assert dp.read_text(encoding="utf-8") == antes


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        app, outro = tmp / "app", tmp / "outro"
        app.mkdir()
        outro.mkdir()
        # cache em pasta temporária: a checagem não mexe no workspace/ real
        with patch.object(core, "workspace_root", lambda: tmp / "workspace"):
            check_eof_exits()
            check_back_from_type(app)
            check_back_from_format(app)
            check_back_from_mark(app)
            check_back_from_path(app)
            check_last_app(app)
            check_keeps_existing_yaml(outro)
    print("ok: menu volta e encerra, último app lembrado, YAML do cache "
          "criado e reaproveitado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
