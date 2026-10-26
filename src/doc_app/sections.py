"""Leitura e edição do YAML da documentação, seção por seção.

Uma *seção* é um título h1 ou h2 e os blocos que vêm depois dele, até o
próximo h1/h2. Cada seção tem um id igual ao seu número ("3", "3.1").

As edições validam os blocos antes de gravar e renumeram os títulos, então
quem edita (uma pessoa ou um agente via MCP) não precisa cuidar da numeração.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .dsl import validate_block

TODO = "(TODO)"
_NUM = re.compile(r"^\s*\d+(?:\.\d+)*\.\s+")

# Dicas de onde procurar informação para cada seção, pelo título.
_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"vis[aã]o geral", re.I),
     "README, package.json/pyproject (name, description), página inicial ou "
     "ponto de entrada do app. Diga o que o app é, para quem e qual problema resolve."),
    (re.compile(r"como se usa|fluxo|telas|funcionalidades|endpoints", re.I),
     "Rotas e páginas (app/, pages/, routes/, router), menus e navegação; em "
     "backend, os routers/controllers. Descreva o caminho do usuário ou do consumidor."),
    (re.compile(r"regras|decis[õo]es|arquitetura", re.I),
     "Configurações (next.config, vite.config, tsconfig), camadas de src/lib, "
     "providers, stores, middlewares, scripts de checagem. Registre só o que o "
     "código confirma, com o arquivo que garante a regra."),
    (re.compile(r"organiza[cç][aã]o|pastas", re.I),
     "A árvore de pastas já está no documento; abra 2 ou 3 arquivos de cada "
     "pasta para descrever a responsabilidade dela."),
    (re.compile(r"m[óo]dulos|componentes", re.I),
     "Pastas features/, modules/, components/, services/. Uma subseção (h2) por "
     "módulo importante: o que faz, quem usa, cuidados ao alterar."),
    (re.compile(r"apis?|integra[cç]", re.I),
     "Clientes HTTP, arquivos de API, variáveis *_URL, OpenAPI, SDKs de terceiros."),
    (re.compile(r"qualidade|testes", re.I),
     "Hooks de git, CI e scripts de checagem já estão listados; explique o que "
     "cada checagem protege, olhando os scripts correspondentes."),
    (re.compile(r"lacunas", re.I),
     "Comentários TODO/FIXME no código, código provisório ou desativado, "
     "inconsistências já anotadas nesta seção."),
]


@dataclass
class Section:
    id: str
    level: int            # 1 ou 2
    title: str            # sem o número
    start: int            # índice do título em blocks
    end: int              # índice depois do último bloco da seção
    todos: int


class SectionError(ValueError):
    """Erro de edição com mensagem pensada para quem vai corrigir a chamada."""


# --- arquivo ---------------------------------------------------------------

def load_raw(path: Path) -> dict:
    if not path.exists():
        raise SectionError(f"Documento não encontrado: {path}. Crie com create_doc.")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw.get("blocks"), list):
        raise SectionError(f"{path}: documento sem lista 'blocks'.")
    return raw


def save_raw(path: Path, raw: dict) -> None:
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, width=100),
                   encoding="utf-8")
    tmp.replace(path)   # troca atômica: nunca deixa o YAML pela metade


# --- leitura ---------------------------------------------------------------

def _heading(block: Any) -> tuple[int, str] | None:
    if isinstance(block, dict) and len(block) == 1:
        (typ, content), = block.items()
        if typ in ("h1", "h2") and isinstance(content, str):
            return int(typ[1]), content
    return None


def _count_todos(blocks: list) -> int:
    return sum(1 for b in blocks if TODO in str(b))


def list_sections(raw: dict) -> list[Section]:
    blocks = raw["blocks"]
    heads = [(i, h) for i, b in enumerate(blocks) if (h := _heading(b))]
    out = []
    for n, (i, (level, text)) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(blocks)
        m = _NUM.match(text)
        sid = m.group(0).strip().rstrip(".") if m else str(n + 1)
        out.append(Section(id=sid, level=level, title=_NUM.sub("", text), start=i,
                           end=end, todos=_count_todos(blocks[i:end])))
    return out


def find(raw: dict, section_id: str) -> Section:
    sid = str(section_id).strip().rstrip(".")
    for s in list_sections(raw):
        if s.id == sid:
            return s
    ids = ", ".join(s.id for s in list_sections(raw))
    raise SectionError(f"Seção {section_id!r} não existe. Ids disponíveis: {ids}.")


def hint_for(title: str) -> str | None:
    for pattern, hint in _HINTS:
        if pattern.search(title):
            return hint
    return None


def section_view(raw: dict, s: Section) -> dict:
    return {"id": s.id, "level": s.level, "title": s.title, "todos": s.todos,
            "blocks": raw["blocks"][s.start + 1:s.end]}


# --- escrita ---------------------------------------------------------------

def _validate_body(blocks: Any) -> list[dict]:
    if not isinstance(blocks, list):
        raise SectionError("'blocks' deve ser uma lista de blocos, ex.: "
                           '[{"p": "texto"}, {"bullet": ["a", "b"]}].')
    errors = []
    for i, b in enumerate(blocks):
        if isinstance(b, dict) and len(b) == 1 and next(iter(b)) in ("h1", "h2"):
            errors.append(f"bloco {i}: não use h1/h2 dentro de uma seção; para criar "
                          "uma subseção use add_section. h3 é permitido.")
            continue
        errors += validate_block(b, f"bloco {i}")
    if errors:
        raise SectionError("Blocos inválidos, nada foi gravado:\n- " + "\n- ".join(errors))
    return blocks


def _clean_title(title: Any) -> str:
    if not isinstance(title, str) or not title.strip():
        raise SectionError("'title' deve ser um texto não vazio.")
    return _NUM.sub("", title.strip())


def renumber(blocks: list) -> None:
    """Reescreve a numeração de todos os h1/h2 na ordem em que aparecem."""
    h1 = h2 = 0
    for i, b in enumerate(blocks):
        h = _heading(b)
        if not h:
            continue
        level, text = h
        text = _NUM.sub("", text)
        if level == 1:
            h1, h2 = h1 + 1, 0
            blocks[i] = {"h1": f"{h1}. {text}"}
        else:
            h2 += 1
            blocks[i] = {"h2": f"{h1}.{h2}. {text}"}


def write_section(raw: dict, section_id: str, blocks: Any,
                  title: str | None = None) -> Section:
    """Substitui o corpo da seção (e o título, se dado). Subseções h2 de um h1
    não são tocadas: o corpo de um h1 vai só até a primeira subseção."""
    s = find(raw, section_id)
    body = _validate_body(blocks)
    head = {f"h{s.level}": _clean_title(title) if title else s.title}
    raw["blocks"][s.start:s.end] = [head, *body]
    renumber(raw["blocks"])
    return find_by_position(raw, s.start)


def add_section(raw: dict, after_id: str | None, level: int, title: str,
                blocks: Any) -> Section:
    """Insere uma seção nova.

    - h2 depois de um h1: entra no fim das subseções desse h1.
    - h2 depois de um h2: entra logo depois dele.
    - h1: entra depois do grupo inteiro (o h1 e suas subseções) da referência.
    - sem `after_id`: entra no fim do documento.
    """
    if level not in (1, 2):
        raise SectionError("'level' deve ser 1 (h1) ou 2 (h2).")
    body = _validate_body(blocks)
    secs = list_sections(raw)
    if after_id is None:
        pos = len(raw["blocks"])
    else:
        ref = find(raw, after_id)
        k = next(i for i, s in enumerate(secs) if s.start == ref.start)
        if level == 2 and ref.level == 2:
            pos = ref.end
        else:
            # fim do grupo: o h1 de referência (ou o h1 pai do h2) e suas subseções
            g = k
            while g > 0 and secs[g].level == 2:
                g -= 1
            pos = secs[g].end
            for s in secs[g + 1:]:
                if s.level == 1:
                    break
                pos = s.end
    if level == 2 and not any(s.level == 1 and s.start < pos for s in secs):
        raise SectionError("Uma seção h2 precisa ficar depois de algum h1.")
    raw["blocks"][pos:pos] = [{f"h{level}": _clean_title(title)}, *body]
    renumber(raw["blocks"])
    return find_by_position(raw, pos)


def remove_section(raw: dict, section_id: str) -> Section:
    """Remove a seção. Remover um h1 remove também as subseções dele."""
    s = find(raw, section_id)
    end = s.end
    if s.level == 1:
        for other in list_sections(raw):
            if other.start >= s.end:
                if other.level == 1:
                    break
                end = other.end
    del raw["blocks"][s.start:end]
    renumber(raw["blocks"])
    return s


def find_by_position(raw: dict, start: int) -> Section:
    for s in list_sections(raw):
        if s.start == start:
            return s
    raise SectionError("Seção não encontrada depois da edição.")
