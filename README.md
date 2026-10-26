# doc_app

Gera documentação em PDF de um app a partir do próprio repositório.

Você aponta o doc_app para a pasta de um projeto. Ele lê os arquivos (README,
`package.json` ou `pyproject.toml`, `.env.example`, pastas, hooks de git, CI,
Dockerfile e estilos) e monta um PDF com capa, sumário clicável e seções
numeradas.

O que dá para confirmar nos arquivos vem preenchido: stack, scripts,
dependências, variáveis de ambiente, árvore de pastas, checagens de qualidade e
Docker. O que depende de interpretação (para que serve o app, como se usa, quais
regras de arquitetura o time segue) fica marcado com `(TODO)`. Esses trechos
podem ser escritos à mão ou por um assistente de IA conectado ao doc_app.

## Sumário

- [Como funciona](#como-funciona)
- [Requisitos](#requisitos)
- [Primeiro uso, passo a passo](#primeiro-uso-passo-a-passo)
- [Painel interativo](#painel-interativo)
- [Linha de comando](#linha-de-comando)
- [Tipos de documentação](#tipos-de-documentação)
- [Marca de uso restrito](#marca-de-uso-restrito)
- [Editar a documentação](#editar-a-documentação)
- [Completar com um assistente de IA (MCP)](#completar-com-um-assistente-de-ia-mcp)
- [O que é extraído do repositório](#o-que-é-extraído-do-repositório)
- [Cores do documento](#cores-do-documento)
- [Problemas comuns](#problemas-comuns)
- [Desinstalar](#desinstalar)
- [Estrutura do código](#estrutura-do-código)
- [Limitações](#limitações)

## Como funciona

```
 repositório do app
        │  doc_app lê os arquivos
        ▼
 workspace/<app>/<tipo>.yaml      ← documento editável: fatos + trechos (TODO)
        │  você ou um assistente de IA completa os (TODO)
        ▼
 ~/Desktop/<app>-<tipo>.pdf       ← PDF gerado a partir do YAML
```

O PDF nunca é a fonte. Toda mudança é feita no YAML, e o PDF é gerado de novo
a partir dele. Por isso não é preciso um editor de PDF.

## Requisitos

| Requisito | Para que serve | Como conferir |
|---|---|---|
| Linux (testado no Ubuntu 26.04) | O caminho das fontes é fixo em `src/doc_app/theme.py`; outros sistemas precisam ajustar esse caminho | — |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Instala o Python 3.14 e as dependências do projeto | `uv --version` |
| Fontes DejaVu | Desenham o texto do PDF, com acentos | `ls /usr/share/fonts/truetype/dejavu` |

Se faltarem as fontes, no Ubuntu ou Debian:

```bash
sudo apt install fonts-dejavu-core
```

## Primeiro uso, passo a passo

### 1. Instalar

```bash
git clone <repo> ~/projects/doc_app
cd ~/projects/doc_app
./scripts/install.sh
```

O instalador faz cinco coisas, nesta ordem:

1. **Prepara o ambiente** com `uv sync`, que baixa o Python e as dependências.
2. **Cria o comando `doc_app`** em `~/.local/bin`, um link para `bin/doc_app`.
   O link aponta para o repositório, então o comando sempre usa o código atual.
3. **Confere o `PATH`.** Se `~/.local/bin` não estiver nele, o instalador mostra
   a linha para colar no `~/.zshrc` ou `~/.bashrc`. Ele não edita esses
   arquivos sozinho.
4. **Testa o comando.**
5. **Oferece conectar o doc_app aos assistentes de IA** encontrados na máquina
   (veja [Completar com um assistente de IA](#completar-com-um-assistente-de-ia-mcp)).
   Responder `0` pula essa etapa; dá para conectar depois com `doc_app connect`.

| Opção | Efeito |
|---|---|
| `--yes` | Aceita todas as perguntas, inclusive conectar todos os assistentes encontrados |
| `--no-mcp` | Pula a etapa dos assistentes |

### 2. Gerar o primeiro PDF

Abra o painel e responda às perguntas. Exemplo real, documentando um app de
exemplo com o tipo completo e marca de uso interno:

```
$ doc_app

  ╔══════════════════════════════════════════╗
  ║   📄  doc_app · gerador de documentação  ║
  ╚══════════════════════════════════════════╝

   dica: pressione Ctrl-C a qualquer momento para sair.
   1.  📝  Gerar documentação de um app
   2.  🔎  Ver assistentes conectados
   3.  🔌  Conectar a assistentes de IA (MCP)
   4.  🧹  Limpar cache
   5.  🚪  Sair

👉 O que deseja fazer? [1]: 1

📂 Caminho do app a documentar (0 cancela): ~/projects/meu-app
   1.  🏷️  Marca e regras        (uso, arquitetura, convenções)
   2.  🛠️  Código                 (estrutura, módulos, APIs, testes)
   3.  📚  Completa               (marca + código no mesmo PDF)

📚 Qual o tipo de documentação? [1]: 3

📭 Ainda não há documentação 'full' para 'meu-app' no cache.
🔎 Detectei: React 18.3.1 · JavaScript/TypeScript · pnpm · frontend
📋 Encontrei: README, 3 scripts, 1 variáveis de ambiente, 4 dependências
✨ Criar a documentação inicial com esses dados? [S/n]:
🎨 Cores da marca detectadas: principal #2563EB, escura #112D6A, destaque #3B73ED
📝 Documentação criada: ~/projects/doc_app/workspace/meu-app/full.yaml
   16 trecho(s) marcados com (TODO) para completar.
   1.  Não, documento público
   2.  Sim, "Uso interno"
   3.  Sim, com outro texto (ex.: Confidencial)

🔒 Marcar o documento como restrito? [1]: 2

💾 Onde salvar o PDF?
   Enter usa o padrão: ~/Desktop/meu-app-full.pdf
   >

⏳ Gerando...
PDF gerado (full, uso interno): ~/Desktop/meu-app-full.pdf  (48 blocos)
🎉 Concluído!
```

O que aconteceu:

- **Detectei** mostra a stack e o tipo do app (frontend, backend, fullstack ou
  biblioteca/CLI). O tipo decide se o doc_app procura cores de marca e como a
  seção de uso é escrita.
- **Encontrei** resume o que foi lido dos arquivos.
- **Documentação criada** é o YAML editável. A linha seguinte diz quantos trechos
  ainda estão marcados com `(TODO)`.
- Nas perguntas com número entre colchetes, Enter aceita o valor mostrado.

### 3. Conferir o PDF

O PDF tem capa, sumário com números de página (cada linha é um link para a
seção), marcadores no painel lateral do leitor de PDF, cabeçalho e rodapé com
"Página X de Y". Os trechos `(TODO)` aparecem no texto como lembrete do que
falta.

### 4. Completar os trechos `(TODO)`

Há dois caminhos, que podem ser misturados:

- **À mão:** edite o YAML e gere o PDF de novo
  ([Editar a documentação](#editar-a-documentação)).
- **Com um assistente de IA:** peça no chat do assistente conectado
  ([Pedir a documentação](#pedir-a-documentação)).

### 5. Gerar de novo

```bash
doc_app build ~/projects/meu-app --type full --internal
```

Como o YAML já existe no cache, o doc_app não recria nada: ele só gera o PDF a
partir do YAML atual, com as suas edições.

## Painel interativo

```bash
doc_app
```

| Opção | O que faz |
|---|---|
| 📝 Gerar documentação de um app | Pede caminho, tipo, marca e destino, e gera o PDF. Se o YAML do app e tipo ainda não existir, oferece criá-lo |
| 🔎 Ver assistentes conectados | Mostra em quais assistentes de IA o doc_app está conectado. Só lê |
| 🔌 Conectar a assistentes de IA | Conecta o doc_app aos assistentes escolhidos |
| 🧹 Limpar cache | Apaga os YAML de todos os apps (pede confirmação) |
| 🚪 Sair | Fecha o painel |

Teclas:

- **Enter** aceita o valor padrão mostrado entre colchetes.
- **0** cancela, na pergunta do caminho do app e na escolha de assistentes.
- **Ctrl-C** sai do doc_app em qualquer ponto.
- Uma resposta inválida faz o painel perguntar de novo.

O destino do PDF aceita um arquivo (`~/docs/manual.pdf`), uma pasta
(`~/docs/`, e o PDF entra nela como `<app>-<tipo>.pdf`) ou um nome sem extensão
(`.pdf` é acrescentado).

## Linha de comando

Os mesmos recursos do painel, sem perguntas. Útil em scripts.

### `doc_app build` — gerar o PDF

```bash
doc_app build <caminho-do-app> [--type TIPO] [-o DESTINO] [--internal | --mark TEXTO] [--yes]
```

| Opção | Efeito | Padrão |
|---|---|---|
| `--type`, `-t` | `brand`, `development` ou `full` | `brand` |
| `--output`, `-o` | Arquivo ou pasta de destino | `~/Desktop/<app>-<tipo>.pdf` |
| `--internal` | Marca o PDF como "Uso interno" | sem marca |
| `--mark TEXTO` | Marca com um texto próprio | sem marca |
| `--yes`, `-y` | Cria o YAML sem perguntar, se ainda não existir | pergunta |

Exemplos:

```bash
doc_app build ~/projects/meu-app                        # brand, no Desktop
doc_app build ~/projects/meu-app -t full -o ~/docs/     # completa, em ~/docs/meu-app-full.pdf
doc_app build ~/projects/api -t development --mark "Confidencial"
```

### `doc_app list` — ver o cache

```
$ doc_app list
Apps no cache (~/projects/doc_app/workspace):
  • 1one-frontend: brand
  • meu-app: full
```

Cada linha é um app e os tipos de documentação que já existem para ele.

### `doc_app clean` — limpar o cache

```bash
doc_app clean              # todos os apps
doc_app clean meu-app      # só um app (use o nome da pasta, não o caminho)
doc_app clean --yes        # sem confirmação
```

Atenção: isso apaga os YAML, inclusive o texto escrito à mão ou por um
assistente.

### `doc_app connect` e `doc_app connections` — assistentes de IA

```bash
doc_app connect            # escolhe em quais assistentes conectar
doc_app connect --yes      # conecta em todos os encontrados
doc_app connections        # mostra os conectados
doc_app connections --all  # inclui os assistentes não instalados
```

```
$ doc_app connections
🔎 Assistentes de IA e o doc_app

   Kiro                 ✅ conectado
                        ~/.kiro/settings/mcp.json
   GitHub Copilot CLI   ·  não conectado
                        ~/.copilot/mcp-config.json
   VS Code (Copilot)    ·  não conectado
                        ~/.config/Code/User/mcp.json

   1 de 3 assistente(s) com o doc_app conectado.
   Para conectar: doc_app connect
```

| Estado | Significado |
|---|---|
| ✅ conectado | A entrada `doc-app` existe e aponta para este repositório |
| · não conectado | Não há entrada `doc-app` |
| ⚠️ aponta para outro repositório | Há uma entrada `doc-app` de outra cópia do doc_app |
| ❌ erro | O arquivo de configuração não pôde ser lido; a mensagem diz o motivo |

## Tipos de documentação

| Tipo | Nome no arquivo | Para quem | Seções |
|---|---|---|---|
| Marca e regras | `brand` | Time todo, produto, quem está chegando | Visão geral, Como começar, Como se usa, Regras e decisões de arquitetura, Qualidade e testes, Docker, Lacunas conhecidas |
| Código | `development` | Quem vai mexer no código | Visão geral, Como começar, Organização do código, Ferramentas, Dependências, Módulos e componentes, APIs e integrações, Qualidade e testes, Docker, Inconsistências |
| Completa | `full` | Os dois públicos, num PDF só | As seções dos dois tipos, sem repetir as que são comuns |

Seções sem dados no repositório não aparecem. Por exemplo, "Docker" só existe
se houver um `Dockerfile`, e "Ferramentas" só se houver arquivos de
configuração reconhecidos.

Cada tipo tem seu próprio YAML no cache (`brand.yaml`, `development.yaml`,
`full.yaml`), então editar um não muda os outros.

O tipo `development` usa tipografia mais compacta e uma variação da capa (um
filete no topo). `brand` e `full` usam a capa padrão.

## Marca de uso restrito

Para documentos que não devem sair da empresa:

```bash
doc_app build ~/projects/meu-app --internal          # "Uso interno"
doc_app build ~/projects/meu-app --mark "Confidencial"
```

No painel, é a pergunta "🔒 Marcar o documento como restrito?".

O PDF marcado ganha:

- marca d'água diagonal e semitransparente em todas as páginas depois da capa;
- selo com o texto da marca no canto da capa;
- aviso no rodapé ("USO INTERNO · não distribuir");
- o texto da marca nos metadados do PDF (palavras-chave).

A marca é escolhida a cada geração e não fica gravada no YAML, então o mesmo
conteúdo pode sair público ou restrito. Para um app sair sempre marcado, coloque
no YAML dele:

```yaml
theme:
  classification: Uso interno
```

A marca é visual. Ela não impede que alguém copie ou repasse o arquivo.

## Editar a documentação

### Onde fica o arquivo

```
~/projects/doc_app/workspace/<app>/<tipo>.yaml
```

Abra em qualquer editor de texto:

```bash
code ~/projects/doc_app/workspace/meu-app/full.yaml
```

Depois de salvar, gere o PDF de novo com `doc_app build` (o tipo precisa ser o
mesmo do arquivo editado).

### Anatomia do arquivo

```yaml
type: full                 # tipo do documento: brand, development ou full
app_kind: frontend         # frontend, backend, fullstack ou other (detectado)
brand_source: '...'        # de onde vieram as cores (só informativo)
theme:                     # aparência; tudo opcional
  cover:
    title: meu-app         # título da capa
    subtitle: Documentação completa
    tagline: Uso, regras de arquitetura e referência de código
    footnote: Gerado pelo doc_app a partir do código-fonte do repositório.
  header_left: meu-app · Documentação
  header_right: Uso, regras e código
  footer_left: meu-app
  classification: Uso interno   # opcional: marca sempre este app
  palette:                      # cores (veja "Cores do documento")
    brand: '#2563EB'
blocks:                    # o conteúdo, em ordem
  - h1: 1. Visão geral
  - p: Painel de pedidos da loja.
  # ...
```

### Tipos de bloco

Cada bloco é um item da lista `blocks` com uma única chave, o tipo do bloco.

| Tipo | Uso | Exemplo |
|---|---|---|
| `h1` | Seção (entra no sumário) | `- h1: 3. Como se usa a aplicação` |
| `h2` | Subseção (entra no sumário) | `- h2: 3.1. Login` |
| `h3` | Subtítulo dentro de uma subseção (entra no sumário) | `- h3: Recuperar senha` |
| `p` | Parágrafo | `- p: O login valida o e-mail antes de enviar.` |
| `bullet` | Lista com marcadores | `- bullet: [Item, Outro item]` |
| `num` | Lista numerada | `- num: [Instale, Rode]` |
| `code` | Bloco de código | ver abaixo |
| `callout` | Caixa de destaque com título | `- callout: {title: Regra, text: ...}` |
| `kv` | Pares nome e descrição | ver abaixo |
| `table` | Tabela | ver abaixo |
| `spacer` | Espaço vertical, em mm | `- spacer: 6` |

```yaml
- code: |
    pnpm install
    pnpm dev
- kv:
    - key: API_URL
      value: URL da API de pedidos.
- table:
    header: [Script, Comando]
    rows:
      - [pnpm dev, vite]
      - [pnpm build, vite build]
    widths: [50, 120]      # opcional; em mm, a soma deve caber em 170
```

Cuidados ao editar à mão:

- **Numeração:** os títulos `h1` e `h2` levam o número no texto ("3.1. Login").
  Ao criar ou apagar seções à mão, ajuste os números. As ferramentas do MCP
  refazem a numeração sozinhas.
- **Aspas:** textos com `:` seguido de espaço, ou começando com `#`, `-` ou
  `[`, precisam ficar entre aspas: `- p: 'Atenção: ...'`.
- **Emojis** são removidos no PDF, porque a fonte não tem esses caracteres.
- **Tabelas grandes** atravessam páginas e repetem o cabeçalho. Listas de
  dependências com mais de 20 pacotes saem em duas colunas.

### O cache

O `workspace/` fica fora do git e é tratado como cache: `doc_app clean` e
`scripts/cleanup.sh` apagam tudo o que está nele. Se um documento tiver muito
trabalho manual, guarde uma cópia do YAML em outro lugar.

Para recriar um documento do zero, a partir dos arquivos do app:

```bash
doc_app clean meu-app
doc_app build ~/projects/meu-app --type full
```

## Completar com um assistente de IA (MCP)

### A ideia

O doc_app não tem modelo de IA próprio e não precisa de chave de API. Ele
oferece um servidor [MCP](https://modelcontextprotocol.io) (`doc-app-mcp`), um
protocolo aberto que assistentes como Kiro, VS Code, Cursor e Claude usam para
chamar ferramentas externas.

Com o doc_app conectado:

1. o **assistente** lê o código do app com as ferramentas dele e escreve o texto
   das seções;
2. o **doc_app** confere o formato do texto, grava no YAML e gera o PDF.

### Conectar

```bash
doc_app connect
```

```
   O servidor MCP do doc_app funciona com qualquer assistente compatível.
   Só a entrada 'doc-app' é adicionada; o arquivo anterior vira .bak.

   1. Kiro                 · não conectado
   2. GitHub Copilot CLI   · não conectado
   3. VS Code (Copilot)    · não conectado

   Conectar quais? (ex.: 1,3 · t = todos · 0 = nenhum):
```

Só aparecem os assistentes encontrados na máquina. Assistentes suportados e
onde cada um guarda a configuração:

| Assistente | Configuração | Como o doc_app grava |
|---|---|---|
| Kiro | `~/.kiro/settings/mcp.json` | edita o JSON |
| Cursor | `~/.cursor/mcp.json` | edita o JSON |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | edita o JSON |
| Gemini CLI | `~/.gemini/settings.json` | edita só o bloco `mcpServers` |
| Claude Desktop | `~/.config/Claude/claude_desktop_config.json` | edita o JSON |
| GitHub Copilot CLI | `~/.copilot/mcp-config.json` | edita o JSON |
| VS Code (Copilot) | `~/.config/Code/User/mcp.json` | edita o JSON, ou usa `code --add-mcp` se o arquivo tiver comentários |
| Claude Code | configuração do próprio CLI | `claude mcp add --scope user` |
| Codex | `~/.codex/config.toml` | `codex mcp add` |

O que o doc_app garante ao mexer nesses arquivos:

- cria ou remove só a entrada `doc-app`; os outros servidores e configurações
  ficam iguais;
- salva uma cópia do arquivo anterior como `<arquivo>.bak`;
- não edita arquivos que não sejam JSON puro (com comentários, por exemplo) e
  avisa;
- não remove uma entrada `doc-app` que aponte para outra cópia do doc_app.

Para um cliente MCP que não está na lista, este comando mostra a configuração
para copiar:

```bash
uv run --project ~/projects/doc_app python -m doc_app.clients snippet
```

```json
{
  "mcpServers": {
    "doc-app": {
      "command": "uv",
      "args": ["run", "--project", "/home/<você>/projects/doc_app", "doc-app-mcp"]
    }
  }
}
```

### Pedir a documentação

Depois de conectar, recarregue o assistente (ou abra uma nova sessão) e peça no
chat. Quanto mais específico, melhor:

> Use as ferramentas do doc_app para documentar ~/projects/meu-app, tipo full.
> Preencha todas as seções com (TODO) usando write_section, criando uma
> subseção por módulo em "Módulos e componentes". Gere o PDF no fim, com marca
> de uso interno.

O caminho que o assistente segue:

1. `inspect_app` e `create_doc`: o doc_app lê o app e cria o YAML (ou reaproveita
   o que já existe, sem perder edições).
2. `list_sections`: lista as seções com `(TODO)` e dá uma dica de onde procurar
   a informação para cada uma.
3. Para cada seção, o assistente lê os arquivos do app e chama `write_section`.
   Pode criar subseções (`add_section`) e remover as que não se aplicam
   (`remove_section`).
4. `build_pdf`: gera o PDF e informa o caminho.

O servidor envia ao assistente regras de conteúdo: escrever em português, só
afirmar o que o código confirma, citar o arquivo de onde tirou cada regra,
manter `(TODO)` quando não conseguir confirmar algo e nunca copiar segredos.

**O painel e o `doc_app build` não chamam o assistente.** Eles só usam o que é
extraído dos arquivos. O enriquecimento acontece apenas quando você pede no chat
do assistente.

### Conferir o resultado

- Rode `doc_app list` e abra o YAML: as seções devem ter texto novo, e a
  quantidade de `(TODO)` deve ter caído.
- Revise o texto. O assistente pode interpretar o código errado, e o YAML é o
  lugar para corrigir.
- Para gerar de novo depois de revisar: `doc_app build <app> --type <tipo>`.

### Ferramentas expostas

| Ferramenta | O que faz |
|---|---|
| `inspect_app` | Fatos do app (stack, tipo, scripts, variáveis, pastas) e documentos já no cache |
| `create_doc` | Cria o YAML inicial; com `overwrite`, recria do zero |
| `list_sections` | Seções, contagem de `(TODO)` e dicas de onde procurar |
| `read_section` | Título e blocos de uma seção |
| `write_section` | Substitui o corpo de uma seção (e o título, se pedido) |
| `add_section` | Cria uma seção ou subseção; refaz a numeração |
| `remove_section` | Remove uma seção (um `h1` leva junto as subseções); refaz a numeração |
| `build_pdf` | Gera o PDF, com marca opcional |
| `block_types` | Formato dos blocos aceitos |

Antes de gravar, o doc_app valida os blocos. Se algo estiver fora do formato,
nada é gravado e o assistente recebe o motivo, para corrigir e tentar de novo:

```
Blocos inválidos, nada foi gravado:
- bloco 0 (p): o conteúdo deve ser um texto não vazio.
- bloco 1: tipo 'tabela' não existe. Use um de: bullet, callout, code, h1, h2, h3, kv, num, p, spacer, table.
- bloco 3 (table): a linha 0 deve ter 1 células, como o header.
```

### Privacidade

Pelo MCP, o código do app é lido pelo assistente e vai para o modelo que ele
usa, como em qualquer uso do assistente no repositório. O doc_app em si não
envia nada para fora. Se o repositório for da empresa, confira se o assistente
que você usa é permitido para esse código.

## O que é extraído do repositório

| Fonte | O que vira no documento |
|---|---|
| `README.md` | Introdução da visão geral, pré-requisitos e passos de instalação (blocos de código ou comandos citados no texto) |
| `package.json` | Framework e versão, bibliotecas por categoria, scripts, dependências, gerenciador de pacotes (`packageManager` ou lockfile), regras do lint-staged |
| `pyproject.toml` | Versão do Python, dependências, scripts, framework web |
| `requirements.txt` | Só a detecção do framework web (as dependências dele não entram na tabela) |
| `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle` | Linguagem e se é um serviço web |
| `.env.example`, `.env.sample`, `.env.template`, `.env.dist` | Variáveis de ambiente, com a descrição tirada dos comentários e o valor de exemplo |
| Pastas | Árvore de `src/` (ou da raiz) e tabela das pastas principais |
| `.husky/` | O que cada hook de git roda |
| `.github/workflows/` | Quando cada workflow dispara e quais comandos roda |
| `Dockerfile` | Estágios, porta, usuário, comando de início, argumentos de build |
| Arquivos de configuração | Ferramentas em uso (Biome, ESLint, TypeScript, Vite, Next, Orval etc.) |
| CSS, Sass, Less, `tailwind.config`, manifest | Cores da marca (só em frontend) |

Detalhes:

- **Segurança:** `.env`, `.env.local` e outros arquivos de ambiente reais nunca
  são lidos. Só os arquivos de exemplo da tabela.
- **Codificação:** arquivos em UTF-8, UTF-8 com BOM, UTF-16 (comum em README
  criado no Windows) e Latin-1 são lidos corretamente.
- **Pastas ignoradas:** `node_modules`, `.git`, `dist`, `build`, `.next`,
  `.venv` e outras de artefatos.
- **Inconsistências:** quando dois arquivos se contradizem (por exemplo, o
  README manda usar yarn e o `package.json` está configurado para pnpm), o
  doc_app não escolhe um lado. Ele registra a divergência em "Lacunas
  conhecidas" para alguém confirmar.

## Cores do documento

O doc_app tem uma paleta própria, discreta, em grafite e cinza-azulado. Ela é
usada:

- em todo app de **backend** (sempre, mesmo que o YAML peça outra);
- em apps de **frontend** onde não foi possível detectar cores de marca;
- em bibliotecas e CLIs.

Em **frontend** e **fullstack**, o doc_app procura as cores no próprio app:
variáveis CSS (`--primary`, `--color-brand-*`, `--accent`), variáveis de Sass e
Less (`$primary`, `@primary`), `tailwind.config` e manifest. Cores definidas só
para o tema escuro são ignoradas. Das cores encontradas, ele escolhe três:

| Cor | Onde aparece | Critério |
|---|---|---|
| Principal | Títulos, links, sumário | Primeira cor de marca com contraste de pelo menos 4,5:1 sobre branco; se nenhuma tiver, a mais forte é escurecida até chegar lá |
| Escura | Fundo da capa, cabeçalho das tabelas | A cor de marca mais escura; se não houver, derivada da principal |
| Destaque | Réguas, barra dos destaques, título da capa | A cor mais viva que contraste com a escura |

Os fundos claros, as linhas e os textos da capa são derivados dessas três. O
resultado fica no YAML, em `theme: palette:`, com a origem de cada cor em
`brand_source`. Para ajustar, edite as cores ali:

```yaml
theme:
  palette:
    brand: '#00664E'      # também aceita [0, 102, 78]
    dark: '#152E2B'
    accent: '#05DC7F'
```

Cores que podem ser definidas: `brand`, `dark`, `accent`, `link`, `ink` (texto),
`muted` (texto secundário), `rule` (linhas), `code_bg`, `code_fg`,
`callout_bg`, `zebra` (linhas alternadas das tabelas), `cover_text`,
`cover_muted` e `white`.

## Problemas comuns

**`doc_app: command not found`**
`~/.local/bin` não está no `PATH`. Adicione ao `~/.zshrc` (ou `~/.bashrc`) e
abra um novo terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

**Erro de fonte ao gerar o PDF**
As fontes DejaVu não estão em `/usr/share/fonts/truetype/dejavu`. Instale com
`sudo apt install fonts-dejavu-core`.

**O assistente não preencheu os `(TODO)`**
Confira com `doc_app connections` se ele está conectado, recarregue o
assistente e peça explicitamente para usar `write_section` em cada seção. O
painel e o `doc_app build` não chamam o assistente.

**As ferramentas do doc_app não aparecem no assistente**
Depois de conectar, o assistente precisa recarregar os servidores MCP. No Kiro,
abra uma nova sessão; no VS Code, use o comando "MCP: List Servers" e inicie o
`doc-app`. A primeira conexão pode levar alguns segundos, enquanto o `uv`
prepara o ambiente.

**Editei o YAML e o PDF não mudou**
Confira se o tipo no `doc_app build` é o mesmo do arquivo editado. Editar
`full.yaml` e gerar com `--type brand` usa o `brand.yaml`.

**Quero recriar o documento a partir dos arquivos do app**
O doc_app reaproveita o YAML que já existe, para não perder edições. Para
recriar: `doc_app clean <app>` e gere de novo.

**O PDF saiu com as cores do doc_app, não da marca do app**
O app foi detectado como backend, ou não há cores de marca reconhecíveis nos
estilos. Defina as cores no YAML (veja [Cores do documento](#cores-do-documento)).
Em backend, as cores do doc_app são sempre usadas.

**O registro num assistente deu erro**
A mensagem diz o arquivo e o motivo. O caso mais comum é um arquivo de
configuração com comentários: o doc_app não o edita, para não estragá-lo.
Adicione a entrada à mão com o bloco do `snippet` (veja
[Conectar](#conectar)).

## Desinstalar

```bash
./scripts/cleanup.sh            # remove comando, conexões MCP, cache e artefatos
./scripts/cleanup.sh --venv     # também remove o ambiente .venv
./scripts/cleanup.sh --yes      # sem confirmação
```

O que é removido:

- o comando `doc_app` em `~/.local/bin`, se apontar para este repositório;
- a entrada `doc-app` em todos os assistentes, se apontar para este repositório
  (os outros servidores ficam);
- o conteúdo do `workspace/`, inclusive edições feitas nos YAML;
- os artefatos `__pycache__`;
- com `--venv`, o ambiente Python.

O código do doc_app não é apagado. Para voltar a usar: `./scripts/install.sh`.

## Estrutura do código

```
bin/doc_app            atalho de execução (usado pelo link em ~/.local/bin)
scripts/install.sh     instalação
scripts/cleanup.sh     desinstalação
src/doc_app/
  cli.py               painel e comandos de linha
  core.py              criar documento e gerar PDF (usado pela CLI e pelo MCP)
  extract.py           fatos do repositório (README, scripts, env, pastas, CI, Docker)
  detect.py            stack e tipo do app (frontend, backend...)
  brand.py             cores da marca de frontends
  skeleton.py          documento inicial a partir dos fatos
  sections.py          leitura e edição do YAML por seção
  dsl.py               tipos de bloco e validação
  loader.py            leitura e escrita do YAML
  theme.py             paleta, fontes, tipografia e tipos de documentação
  renderer.py          desenho do PDF (fpdf2): capa, sumário, blocos, marca
  builder.py           monta capa, sumário e corpo
  textio.py            leitura de arquivos com detecção de codificação
  mcp_server.py        servidor MCP (ferramentas para assistentes)
  clients.py           conexão com os assistentes de IA
  agent/               reservado para um modo com modelo próprio (não implementado)
workspace/             cache local dos documentos (fora do git)
```

## Limitações

- Funciona só no Linux sem ajustes, por causa do caminho das fontes.
- A extração lê arquivos de configuração e estrutura; ela não interpreta o
  código. Propósito, fluxos e regras dependem de uma pessoa ou de um assistente.
- O texto escrito por um assistente pode conter erros de interpretação. Revise
  o YAML antes de distribuir o PDF.
- O cache é apagado por `clean` e `cleanup.sh`; documentos com muito trabalho
  manual precisam de cópia em outro lugar.
- A marca de uso restrito é só visual.
