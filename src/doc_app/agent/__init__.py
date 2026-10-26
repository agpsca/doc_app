"""Agente de geração de documentação (esqueleto).

Hoje o caminho principal é o servidor MCP (`doc_app.mcp_server`): um agente
externo, como o Kiro, lê o código e escreve as seções pelas ferramentas do
doc_app, sem chave de API no doc_app.

Este pacote fica para o modo em que o próprio doc_app chama um modelo
(Anthropic, OpenAI, Ollama...). Ele usaria as mesmas operações de seção de
`doc_app.sections`. A ideia:

1. O agente recebe o caminho de um projeto-alvo.
2. Analisa o código (configs, estrutura de pastas, pontos de entrada).
3. Produz uma lista de blocos da DSL — ou, de forma incremental, edita o
   `doc.yaml` que já existe no workspace, relendo-o em vez de reanalisar o
   projeto inteiro. Essa releitura barata é o ponto da pasta `workspace/`.

Dois caminhos possíveis de implementação (a decidir):
    - determinístico: regras que leem package.json/estrutura e montam blocos.
    - via LLM: um provedor escreve a prosa a partir do código.

`DocAgent` define o contrato; `generate` ainda não está implementado.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..dsl import Block


class DocAgent(ABC):
    """Contrato de um agente que gera blocos de documentação para um projeto."""

    @abstractmethod
    def generate(self, project_path: str | Path) -> list[Block]:
        """Analisa `project_path` e devolve a lista de blocos da DSL."""
        raise NotImplementedError


class PlaceholderAgent(DocAgent):
    """Implementação temporária: ainda não gera nada.

    Existe só para fixar a interface e permitir fiação futura sem quebrar
    importações.
    """

    def generate(self, project_path: str | Path) -> list[Block]:
        raise NotImplementedError(
            "O agente ainda não foi implementado. "
            "Defina a estratégia (determinística ou via LLM) antes de usar."
        )


__all__ = ["DocAgent", "PlaceholderAgent"]
