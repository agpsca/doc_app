#!/usr/bin/env python
"""Checagem da análise do repositório: README, rotas, módulos e pendências.

Monta um app de mentira numa pasta temporária e confere o que a extração
afirma sobre ele, que seções do README cada seção do documento aproveita e
que os blocos gerados passam no validador da DSL. É o que quebra se a análise
voltar a deixar como (TODO) algo que está escrito nos arquivos.

Uso:
    uv run python scripts/check_extract.py
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from doc_app.dsl import validate_block
from doc_app.extract import extract_facts
from doc_app.md import md_blocks
from doc_app.skeleton import TODO, readme_targets, skeleton_blocks

README = """\
# loja-api

Serviço de pedidos da loja.

## Requisitos

- Python 3.12

## Como rodar

```bash
pip install -r requirements.txt
```

## Como se usa

O consumidor autentica em /auth/login e depois chama /pedidos.

## Decisões de arquitetura

Toda rota passa por require_permissions.

### Transações

O commit é feito na camada de serviço.

## Qualidade

| Momento | O que roda |
|---|---|
| CI | pytest |

Os testes cobrem o caminho de pagamento.

## Lacunas conhecidas

- Falta paginação em /pedidos.
"""

ROUTES_PY = """\
from fastapi import APIRouter

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


@router.get(
    path="",
    status_code=200,
)
async def listar():
    return []


@router.post("/{pedido_id}/itens")
async def adicionar():
    # TODO: validar estoque antes de aceitar
    return {}
"""

BLUEPRINT_INIT = """\
from flask import Blueprint

relatorios_bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")
"""

BLUEPRINT_ROUTES = """\
from . import relatorios_bp


@relatorios_bp.route("/mensal", methods=["GET", "POST"])
def mensal():
    return ""
"""


def build_app(root: Path) -> Path:
    app = root / "loja-api"
    (app / "app" / "features" / "pedidos").mkdir(parents=True)
    (app / "app" / "features" / "relatorios").mkdir(parents=True)
    (app / "tests").mkdir()
    (app / "README.md").write_text(README, encoding="utf-8")
    (app / "requirements.txt").write_text(
        "fastapi==0.119.1\nsqlmodel==0.0.27\npytest==8.0.0\n", encoding="utf-8")
    (app / "example.env").write_text(
        "# Banco de dados usado pelo serviço\nDATABASE_URL=mysql://localhost/loja\n",
        encoding="utf-8")
    (app / "Dockerfile").write_text(
        'FROM python:3.12-slim\nEXPOSE 8000\nUSER appuser\n'
        'CMD ["uvicorn", "app.main:app", "--port", "8000"]\n', encoding="utf-8")
    (app / "app" / "features" / "pedidos" / "routes.py").write_text(
        ROUTES_PY, encoding="utf-8")
    (app / "app" / "features" / "relatorios" / "__init__.py").write_text(
        BLUEPRINT_INIT, encoding="utf-8")
    (app / "app" / "features" / "relatorios" / "routes.py").write_text(
        BLUEPRINT_ROUTES, encoding="utf-8")
    (app / "tests" / "test_pedidos.py").write_text("def test_ok():\n    pass\n",
                                                   encoding="utf-8")
    # extensão em maiúsculas e CRLF: como um arquivo criado no Windows chega
    (app / "tests" / "Test_Relatorios.PY").write_text(
        "def test_mensal():\r\n    pass  # FIXME: cobrir o POST\r\n", encoding="utf-8")
    return app


def check_markdown() -> None:
    blocks = md_blocks("""\
Parágrafo com `código` e **negrito**
que continua na linha seguinte.

- item um
- item dois
  que embrulha

| Coluna | Outra |
|---|---|
| a | b |

```bash
echo oi
```

### Subtítulo
""".splitlines())
    types = [next(iter(b)) for b in blocks]
    assert types == ["p", "bullet", "table", "code", "h3"], types
    assert blocks[0]["p"] == "Parágrafo com código e negrito que continua na linha seguinte."
    assert blocks[1]["bullet"] == ["item um", "item dois que embrulha"], blocks[1]
    table = blocks[2]["table"]
    assert table["header"] == ["Coluna", "Outra"] and table["rows"] == [["a", "b"]]
    assert sum(table["widths"]) <= 170
    assert blocks[3]["code"] == "echo oi"
    # o filtro de tipos deixa passar só o que a seção pediu
    assert [next(iter(b)) for b in md_blocks(["| a | b |", "|---|---|", "| 1 | 2 |"],
                                             keep=("p",))] == []
    # nada de tabela sem linhas, e sem cabeçalho vazio
    assert md_blocks(["| a | b |", "|---|---|"]) == []


def check_facts(app: Path) -> None:
    f = extract_facts(app)
    assert f.stack.framework == "FastAPI 0.119.1", f.stack.framework
    assert f.stack.kind == "backend", f.stack.kind
    assert f.stack.package_manager == "pip", f.stack.package_manager
    assert f.readme_intro == "Serviço de pedidos da loja.", f.readme_intro
    assert f.readme_prereqs == ["Python 3.12"], f.readme_prereqs
    assert "pip install -r requirements.txt" in (f.setup_code or ""), f.setup_code
    assert f.env_file == "example.env" and [v.key for v in f.env_vars] == ["DATABASE_URL"]
    assert f.env_vars[0].description == "Banco de dados usado pelo serviço"
    assert "Python 3.12 (imagem base do Dockerfile)" in f.prereqs, f.prereqs
    assert ("Testes", "pytest") in f.libs, f.libs
    assert f.test_files == [("tests", 2)], f.test_files
    found = "\n".join(f.code_todos)
    assert len(f.code_todos) == 2, f.code_todos
    assert "routes.py:16 — TODO: validar estoque antes de aceitar" in found, found
    # arquivo com CRLF e extensão em maiúsculas (vindo do Windows) também conta,
    # e o caminho é sempre reportado com barra normal
    assert "tests/Test_Relatorios.PY:2 — FIXME: cobrir o POST" in found, found
    assert "\\" not in found, found
    assert "(TODO)" not in found       # não conta como trecho a completar

    # o router do FastAPI e o blueprint do Flask, cada um com suas operações.
    # O blueprint é declarado em __init__.py e decorado em routes.py.
    groups = {g.label: g for g in f.routes}
    assert set(groups) == {"Pedidos", "relatorios"}, list(groups)
    assert groups["Pedidos"].base == "/pedidos"
    assert groups["Pedidos"].ops == ["GET /", "POST /{pedido_id}/itens"], \
        groups["Pedidos"].ops
    assert groups["relatorios"].base == "/relatorios"
    assert sorted(groups["relatorios"].ops) == ["GET /mensal", "POST /mensal"]
    assert [m.name for m in f.modules] == ["pedidos", "relatorios"]
    return f


def check_readme_mapping(f) -> None:
    md = readme_targets(f)
    assert set(md) == {"usage", "rules", "quality", "gaps"}, list(md)
    assert md["usage"][0]["p"].startswith("O consumidor autentica"), md["usage"]
    # a subseção h3 do README acompanha a seção que a contém
    assert [next(iter(b)) for b in md["rules"]] == ["p", "h3", "p"], md["rules"]
    # o quadro de qualidade já entra como fato extraído: só a prosa é aproveitada
    assert [next(iter(b)) for b in md["quality"]] == ["p"], md["quality"]
    assert md["gaps"] == [{"bullet": ["Falta paginação em /pedidos."]}], md["gaps"]
    # seções já aproveitadas em outro lugar não são reaproveitadas
    assert "Python 3.12" not in str(md)


def check_skeleton(f) -> None:
    common = ("/pedidos", "uvicorn app.main:app", "Python 3.12")
    extra = {
        "brand": ("O consumidor autentica", "require_permissions", "Falta paginação"),
        "development": ("pedidos", "routes.py", "sqlmodel"),
    }
    extra["full"] = extra["brand"] + extra["development"]
    for doc_type in ("brand", "development", "full"):
        blocks = skeleton_blocks(f, doc_type)
        errors = [e for i, b in enumerate(blocks)
                  for e in validate_block(b, f"{doc_type}: bloco {i}")]
        assert not errors, errors
        text = str(blocks)
        # o que o README e o código respondem não fica marcado para completar
        for found in common + extra[doc_type]:
            assert found in text, (doc_type, found)
        # sobra (TODO) só no que nenhum arquivo responde, e nunca num título
        todos = [b for b in blocks if TODO in str(b)]
        assert len(todos) <= 3, (doc_type, todos)
        assert all("h1" not in b and "h2" not in b for b in todos), todos

    numbers = [v for b in skeleton_blocks(f, "full") for k, v in b.items() if k == "h1"]
    assert numbers[0].startswith("1. ") and numbers[1].startswith("2. "), numbers

    # toda seção pendente diz ao agente onde procurar: é o que permite
    # preencher o documento sem o usuário explicar o repositório
    from doc_app import sections
    for doc_type in ("brand", "development", "full"):
        raw = {"blocks": skeleton_blocks(f, doc_type)}
        pending = [s for s in sections.list_sections(raw) if s.todos]
        without = [s.title for s in pending if not sections.hint_for(s.title)]
        assert not without, (doc_type, without)


def check_frameworks() -> None:
    """Rotas reconhecidas em cada stack, não só nos dois do dono do repositório.

    Cada caso é um arquivo mínimo com a declaração que o framework usa; o que
    se afirma é o grupo, a base e as operações.
    """
    cases: dict[str, tuple[dict[str, str], str, str, list[str]]] = {
        "FastAPI": ({"app/order/routes.py":
                     'from fastapi import APIRouter\n'
                     'router = APIRouter(prefix="/orders", tags=["Orders"])\n'
                     '@router.get(path="")\nasync def listar(): ...\n'},
                    "Orders", "/orders", ["GET /"]),
        "Flask": ({"api/orders/__init__.py":
                   'from flask import Blueprint\n'
                   'bp = Blueprint("orders", __name__, url_prefix="/orders")\n',
                   "api/orders/routes.py":
                   'from . import bp\n@bp.route("/", methods=["GET", "POST"])\n'
                   'def index(): ...\n'},
                  "orders", "/orders", ["GET /", "POST /"]),
        "Express": ({"api/users.js":
                     "const router = require('express').Router();\n"
                     "router.get('/users', l);\nrouter.post('/users', c);\n"},
                    "api", "/", ["GET /users", "POST /users"]),
        "NestJS": ({"src/orders/orders.controller.ts":
                    "@Controller('orders')\nclass C {\n @Get()\n a() {}\n"
                    " @Post()\n b() {}\n}\n"},
                   "orders", "/orders", ["GET /", "POST /"]),
        "Spring": ({"src/main/java/x/OrderController.java":
                    '@RequestMapping("/api/orders")\nclass C {\n'
                    ' @GetMapping("/{id}")\n void a() {}\n @PostMapping\n'
                    ' void b() {}\n}\n'},
                   "x", "/api/orders", ["GET /{id}", "POST /"]),
        "Laravel": ({"routes/web.php":
                     "<?php\nRoute::get('/produtos', 'C@i');\n"
                     "Route::post('/produtos', 'C@s');\n"},
                    "routes", "/", ["GET /produtos", "POST /produtos"]),
        "Go": ({"cmd/api/main.go":
                'func main() {\n r := chi.NewRouter()\n r.Get("/health", h)\n'
                ' r.Post("/orders", c)\n}\n'},
               "api", "/", ["GET /health", "POST /orders"]),
    }
    for framework, (files, label, base, ops) in cases.items():
        with tempfile.TemporaryDirectory() as raw:
            app = Path(raw) / "servico"
            for rel, code in files.items():
                path = app / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(code, encoding="utf-8")
            routes = extract_facts(app).routes
            assert len(routes) == 1, (framework, routes)
            group = routes[0]
            assert (group.label, group.base, group.kind) == (label, base, "api"), \
                (framework, group)
            assert sorted(group.ops) == sorted(ops), (framework, group.ops)

    # listas de rotas de tela (Vue Router, Angular) entram como páginas
    with tempfile.TemporaryDirectory() as raw:
        app = Path(raw) / "painel"
        (app / "src" / "router").mkdir(parents=True)
        (app / "src" / "router" / "index.ts").write_text(
            "const routes = [{ path: '/' }, { path: '/clientes' },"
            "{ path: '/clientes/:id' }, { path: '/config' }];", encoding="utf-8")
        routes = extract_facts(app).routes
        assert len(routes) == 1 and routes[0].kind == "page", routes
        assert routes[0].ops == ["/", "/clientes", "/clientes/:id", "/config"], \
            routes[0].ops


def check_tone(f) -> None:
    """O texto que chega ao PDF não pode parecer formulário.

    Três tiques que entregam geração automática: plural escrito "variável(is)",
    instrução ao autor ("Descreva...") impressa no documento e a marca (TODO)
    crua no meio da frase.
    """
    from doc_app.renderer import Renderer

    assert Renderer.pending(f"{TODO} Tom de voz.") == (True, "Tom de voz.")
    assert Renderer.pending(f"Fato. {TODO} Resto.") == (False, "Fato. a definir: Resto.")
    assert Renderer.pending("texto normal") == (False, "texto normal")

    hedge = re.compile(r"\w\(s\)|\(is\)|\(ões\)")
    orders = re.compile(r"\b(Descreva|Explique|Complete|Documente|Preencha|Liste)\b")
    for doc_type in ("brand", "development", "full"):
        text = str(skeleton_blocks(f, doc_type))
        found = hedge.search(text) or orders.search(text)
        assert not found, (doc_type, found.group(0))


def main() -> int:
    check_markdown()
    check_frameworks()
    with tempfile.TemporaryDirectory() as raw:
        app = build_app(Path(raw))
        facts = check_facts(app)
        check_readme_mapping(facts)
        check_skeleton(facts)
        check_tone(facts)
    print("ok: markdown, fatos do repositório, rotas de 8 stacks, módulos, "
          "seções do README e tom do texto")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
