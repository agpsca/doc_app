# doc_app

Gera documentação de um app a partir do próprio repositório, em PDF, Word ou
PowerPoint.

Você aponta o doc_app para a pasta de um projeto. Ele lê os arquivos (README,
`package.json`, `pyproject.toml` ou `requirements.txt`, `.env.example`, pastas,
rotas declaradas no código, hooks de git, CI, Dockerfile e estilos) e monta um
PDF com capa, sumário clicável e seções numeradas — ou um `.docx`/`.pptx` com
os mesmos blocos, para editar no Office.

O que dá para confirmar nos arquivos vem preenchido: stack, scripts,
dependências, variáveis de ambiente, árvore de pastas, rotas, módulos, testes,
checagens de qualidade e Docker. O texto do README é aproveitado seção por
seção (uso, decisões de arquitetura, organização, qualidade, lacunas). Fica
marcado com `(TODO)` só o que nenhum arquivo responde — o propósito do app sem
README, a narrativa de uso, a responsabilidade de cada módulo. Esses trechos
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
        │  doc_app lê os arquivos: configuração, código e README
        ▼
 workspace/<app>/<tipo>.yaml      ← documento editável: fatos extraídos,
        │                            texto do README e trechos (TODO)
        │  você ou um assistente de IA completa os (TODO)
        ▼
 ~/Desktop/<app>-<tipo>.pdf       ← gerado a partir do YAML
 ~/Desktop/<app>-<tipo>.docx         (ou .docx / .pptx, os mesmos blocos)
```

O arquivo gerado nunca é a fonte. Toda mudança é feita no YAML, e o documento
é gerado de novo a partir dele. Editar o `.docx`/`.pptx` direto funciona, mas
a próxima geração não enxerga essa edição.

## Requisitos

| Requisito | Para que serve | Como conferir |
|---|---|---|
| Linux, WSL, macOS ou Windows | Os caminhos de fontes e de configuração são resolvidos na plataforma em uso | — |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Instala o Python 3.14 e as dependências do projeto | `uv --version` |
| Fontes do PDF | Desenham o texto, com acentos | veja a tabela abaixo |

As fontes são procuradas automaticamente, na primeira pasta que tiver o trio
completo (regular, negrito e monoespaçada):

| Plataforma | Fontes usadas | Onde |
|---|---|---|
| Linux, WSL | DejaVu | `/usr/share/fonts/truetype/dejavu`, `/usr/share/fonts/dejavu`, `~/.local/share/fonts` |
| WSL sem fontes Linux | as do Windows | `/mnt/c/Windows/Fonts` |
| Windows | Arial + Consolas (ou DejaVu, se instalada) | `%WINDIR%\Fonts` |
| macOS | DejaVu | `~/Library/Fonts`, `/Library/Fonts` |

Se faltarem as fontes DejaVu, no Ubuntu, Debian ou WSL:

```bash
sudo apt install fonts-dejavu-core
```

Para usar outras fontes, aponte `DOC_APP_FONT_DIR` para uma pasta com
`DejaVuSans.ttf`, `DejaVuSans-Bold.ttf` e `DejaVuSansMono.ttf`.

## Primeiro uso, passo a passo

### 1. Instalar

Em Linux, WSL ou macOS:

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

#### No Windows

Os scripts `install.sh` e `cleanup.sh` são de shell e não rodam no PowerShell.
No Windows, quem instala o comando é o próprio `uv`:

```powershell
git clone <repo> $HOME\projects\doc_app
cd $HOME\projects\doc_app
uv sync
uv tool install --editable .     # cria os comandos doc-app e doc-app-mcp
uv tool update-shell             # só se o comando não for encontrado; reabra o terminal
doc-app connect                  # conecta aos assistentes de IA
```

O `--editable` faz os comandos apontarem para este repositório, como o symlink
no Linux: `git pull` já atualiza o comando, e o cache fica em
`<repo>\workspace`.

Sem instalar nada, de dentro do repositório, também funciona:

```powershell
uv run doc-app build C:\projetos\meu-app --type full
```

No Windows, o comando chama-se `doc-app` (com hífen), e não `doc_app`. O resto
deste README vale igual nas duas plataformas. Para desinstalar:
`uv tool uninstall doc-app` e `uv run python -m doc_app.clients unregister all`.

No WSL, use as instruções de Linux. Os caminhos podem ser colados no formato do
Windows, como o Explorer copia: `\\wsl.localhost\Ubuntu-26.04\home\você\app`,
`C:\projetos\app`, com ou sem as aspas do "Copiar como caminho". O doc_app
converte com o `wslpath`, tanto para o app quanto para o destino do PDF.

O PDF vai para `~/Desktop` se essa pasta existir; no WSL ela normalmente não
existe, então o padrão passa a ser a home. Para salvar no Desktop do Windows:

```bash
doc_app build ~/projects/meu-app -t full -o /mnt/c/Users/<você>/Desktop/
doc_app build ~/projects/meu-app -t full -o 'C:\Users\<você>\Desktop\'
```

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
📋 Encontrei: README (8 seções), 3 scripts, 1 variáveis de ambiente, 4 dependências, 9 rota(s), 4 módulo(s)
✨ Criar a documentação inicial com esses dados? [S/n]:
🎨 Cores da marca detectadas: principal #2563EB, escura #112D6A, destaque #3B73ED
📝 Documentação criada: ~/projects/doc_app/workspace/meu-app/full.yaml
   3 trecho(s) marcados com (TODO) para completar.
   1.  Não, documento público
   2.  Sim, "Uso interno"
   3.  Sim, com outro texto (ex.: Confidencial)

🔒 Marcar o documento como restrito? [1]: 2

💾 Onde salvar o PDF?
   Enter usa o padrão: ~/Desktop/meu-app-full.pdf
   >

⏳ Gerando...
PDF gerado (full, uso interno): ~/Desktop/meu-app-full.pdf  (80 blocos)
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

O documento já chega com os fatos do repositório e com o texto do README
distribuído pelas seções correspondentes. Sobra o que nenhum arquivo responde
(veja [O que continua marcado com `(TODO)`](#o-que-continua-marcado-com-todo)).
Para ver quanto falta, a linha "trecho(s) marcados com (TODO)" aparece na
criação, e o assistente lista seção por seção com `list_sections`.

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
| 📝 Gerar documentação de um app | Pede caminho, tipo, formato, marca e destino, e gera o arquivo. Se o YAML do app e tipo ainda não existir, oferece criá-lo |
| 🔎 Ver assistentes conectados | Mostra em quais assistentes de IA o doc_app está conectado. Só lê |
| 🔌 Conectar a assistentes de IA | Conecta o doc_app aos assistentes escolhidos |
| 🧹 Limpar cache | Apaga os YAML de todos os apps (pede confirmação) |
| 🚪 Sair | Fecha o painel |

Cada ação volta para o menu quando termina; o painel só fecha em **Sair** (ou
Ctrl-C).

Teclas:

- **Enter** aceita o valor padrão mostrado entre colchetes. Na pergunta do
  caminho, repete o último app documentado.
- **⬅️ Voltar**, no fim dos submenus, e **0**, na pergunta do caminho do app,
  voltam para o menu.
- **0** também cancela a escolha de assistentes.
- **Ctrl-C** sai do doc_app em qualquer ponto.
- Uma resposta inválida faz o painel perguntar de novo.

O destino do PDF aceita um arquivo (`~/docs/manual.pdf`), uma pasta
(`~/docs/`, e o arquivo entra nela como `<app>-<tipo>.<formato>`) ou um nome
sem extensão (a extensão do formato é acrescentada).

### Formatos de saída

O desenho é o mesmo nos três: a paleta, as fontes e as medidas vêm do tema, e
Word e PowerPoint recebem a capa escura com faixa de destaque e selo, o
cabeçalho e o rodapé com régua e número de página, o filete do `h1`, a caixa
de código, o callout com barra, a tabela de cabeçalho escuro com faixa
zebrada, as amostras de cor e a marca d'água do documento restrito.

| Formato | Para que serve |
|---|---|
| `pdf` | Entrega. Mede o texto na geração, então as quebras são definitivas |
| `docx` | Editar no Word, Google Docs ou LibreOffice. Títulos nos estilos `Heading 1/2/3`, sumário em campo nativo (o Word atualiza ao abrir) e as fontes do tema embutidas no arquivo |
| `pptx` | Editar no PowerPoint ou Google Slides. Capa e divisórias escuras, um slide por `h2`, slide de sumário e `(cont.)` no que transborda |

O que não dá para igualar:

- **Fontes no PowerPoint.** O `.pptx` pede a família pelo nome, e o PowerPoint
  substitui se a máquina não a tiver. No Windows, gere com
  `DOC_APP_FONT_DIR=/mnt/c/Windows/Fonts` (ou instale as fontes DejaVu) para o
  PDF e o PowerPoint usarem a mesma. O `.docx` não tem esse problema: as
  fontes do tema vão **embutidas** no arquivo, como no PDF, então o Word
  desenha igual em qualquer máquina — cada fonte soma ~700 KB, e LibreOffice e
  Google Docs ignoram fonte embutida e voltam a substituir.
- **Quebras.** Word e PowerPoint refluem o texto; as quebras de página e de
  linha não caem exatamente onde o PDF mediu. No `.docx`, o cabeçalho da
  tabela repete na quebra e a linha não se divide, como no PDF, mas a
  paginação em si não é a mesma.
- **SVG.** Logo e área de proteção em SVG não entram (o Office não lê SVG): no
  lugar fica a legenda com o caminho do arquivo.

No WSL, o caminho do app e o destino também aceitam o formato do Windows
(`\\wsl.localhost\<distro>\home\...`, `C:\...`), convertidos com o `wslpath`.

## Linha de comando

Os mesmos recursos do painel, sem perguntas. Útil em scripts.

### `doc_app build` — gerar o PDF

```bash
doc_app build <caminho-do-app> [--type TIPO] [--format FORMATO] [-o DESTINO] [--internal | --mark TEXTO] [--yes]
```

| Opção | Efeito | Padrão |
|---|---|---|
| `--type`, `-t` | `brand`, `development`, `full` ou `slides` | `brand` |
| `--format`, `-f` | `pdf`, `docx` (Word) ou `pptx` (PowerPoint) | `pdf` |
| `--output`, `-o` | Arquivo ou pasta de destino | `~/Desktop/<app>-<tipo>.<formato>` |
| `--internal` | Marca o documento como "Uso interno" | sem marca |
| `--mark TEXTO` | Marca com um texto próprio | sem marca |
| `--yes`, `-y` | Cria o YAML sem perguntar, se ainda não existir | pergunta |

Exemplos:

```bash
doc_app build ~/projects/meu-app                        # brand, no Desktop
doc_app build ~/projects/meu-app -t full -o ~/docs/     # completa, em ~/docs/meu-app-full.pdf
doc_app build ~/projects/meu-app -t full -f docx        # a mesma, editável no Word
doc_app build ~/projects/meu-app -t slides -f pptx      # deck editável no PowerPoint
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
| Código | `development` | Quem vai mexer no código | Visão geral, Como começar, Organização do código, Ferramentas, Dependências, Módulos e componentes, APIs e integrações, Qualidade e testes, Docker, Inconsistências (quando dois arquivos se contradizem) |
| Completa | `full` | Os dois públicos, num PDF só | As seções dos dois tipos, sem repetir as que são comuns |
| Identidade visual | `slides` | Marca, produto, agência, quem aplica a marca | A marca (posicionamento, tom de voz, nome), Identidade visual (assinatura, símbolo, área de proteção, cores, tipografia, forma, usos indevidos), Governança, Lacunas |

Seções sem dados no repositório não aparecem. Por exemplo, "Docker" só existe
se houver um `Dockerfile`, e "Ferramentas" só se houver arquivos de
configuração reconhecidos.

Onde cada fato do código entra:

| Fato | Seção |
|---|---|
| Rotas e páginas | Como se usa (`brand`), APIs e integrações (`development`) |
| Módulos e os arquivos de cada um | Módulos e componentes (`development`) |
| Testes por pasta e o runner | Qualidade e testes |
| `TODO`/`FIXME` do código e divergências entre arquivos | Lacunas conhecidas |

Cada tipo tem seu próprio YAML no cache (`brand.yaml`, `development.yaml`,
`full.yaml`), então editar um não muda os outros.

O tipo `development` usa tipografia mais compacta e uma variação da capa (um
filete no topo). `brand` e `full` usam a capa padrão.

### Identidade visual (apresentação de slides)

```bash
doc_app build ~/projects/meu-app --type slides --internal
```

No painel, é a quarta opção da pergunta "📚 Qual o tipo de documentação?".

Sai um PDF em 16:9 (33,87 × 19,05 cm), feito para projetar: capa e divisórias
de seção sangrando na cor escura da marca, sumário clicável com o número de
cada slide, um slide por subseção e número de slide no canto. O que não cabe
num slide continua no seguinte, marcado "(cont.)".

O que o doc_app extrai do repositório para montar o guia:

| Slide | De onde vem |
|---|---|
| Posicionamento | a descrição declarada pelo app (metadata do `layout.tsx`, `<meta name="description">` do `index.html`, manifest, `package.json`) ou a introdução do README |
| Nome e escrita | nome do pacote, título e template de título, idioma declarado, framework — cada linha com o arquivo de origem |
| Assinatura | arquivo de logotipo mais largo, mostrado sobre fundo claro e sobre fundo escuro, com as variantes `on-light`/`on-dark` da mesma pasta |
| Símbolo | arquivo quadrado (ícone), com formato e dimensões medidas |
| Área de proteção | desenho gerado: o símbolo sobre grade de ¼H, respiro de ½H tracejado e a cota H |
| Cores da marca | variáveis de cor com "brand", "primary" ou "accent" no nome, com o hex e o arquivo de origem; havendo um namespace de marca (`--color-brand-*`), ele manda |
| Cores da interface | as cores semânticas (`--background`, `--muted`, `--destructive`...) |
| Tipografia | famílias declaradas em `next/font`, Google Fonts, `@font-face`, Tailwind ou variáveis de CSS/Sass, com os pesos |
| Forma e espaçamento | variáveis de raio, espaçamento e sombra |
| Usos indevidos | as checagens de commit que já protegem arquivos de marca |
| Governança | em que arquivo mora cada cor, fonte e asset; hooks e scripts de checagem |
| Lacunas | favicon, OG image, ícone iOS ou versão vetorial que faltam |

Nada disso é específico de um framework: o que não existir no repositório
simplesmente não vira slide. Num backend sem interface, por exemplo, sai só a
parte de nome, governança e lacunas.

Fica `(TODO)` o que nenhum arquivo responde: tom de voz, público, usos
indevidos, o respiro mínimo que o time adotou e quem aprova mudanças de marca.

Três limites honestos deste guia:

- **A fonte da marca não é usada no PDF.** Repositório com `next/font` não tem
  o arquivo da fonte; o nome e os pesos entram como especificação, e a amostra
  é desenhada com a fonte do documento.
- **Arquivo `.ico` aparece na lista, mas não é desenhado** (o PDF não lê esse
  formato). SVG e PNG entram, o SVG como vetor.
- **O YAML guarda o caminho do app** (`app_path`), porque as imagens são lidas
  na hora de gerar. Se a pasta do app mudar de lugar, ajuste essa linha; onde
  faltar o arquivo, o slide mostra o caminho que não foi encontrado.

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

Blocos de identidade visual, desenhados no tipo `slides` (no PDF A4 viram
imagem, amostras pequenas e texto):

| Tipo | Uso | Exemplo |
|---|---|---|
| `logo` | Arquivo da marca; `on: both` mostra sobre fundo claro e escuro | `- logo: {path: public/logo.svg, on: both}` |
| `clearspace` | Área de proteção, com grade e cota | `- clearspace: {path: public/icon.svg, ratio: 0.5}` |
| `swatches` | Amostras de cor com nome e código | `- swatches: {items: [{name: brand-green, hex: '#00664E'}]}` |
| `specimen` | Especificação de uma família tipográfica | `- specimen: {font: Space Grotesk, weights: '400, 500'}` |

Os caminhos de `logo` e `clearspace` são relativos à pasta do app, que o YAML
guarda em `app_path`.

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

Claude Desktop e VS Code guardam a configuração em outro lugar fora do Linux:
`%APPDATA%\Claude\` e `%APPDATA%\Code\User\` no Windows,
`~/Library/Application Support/` no macOS. O `doc_app connections` mostra o
caminho usado na sua máquina.

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
chat. O caminho do repositório é a única coisa que o assistente precisa de
você:

> Use as ferramentas do doc_app para documentar ~/projects/meu-app, tipo full.
> Preencha todas as seções com (TODO) usando write_section, criando uma
> subseção por módulo em "Módulos e componentes". Gere o PDF no fim, com marca
> de uso interno.

Para o guia de identidade visual:

> Use o doc_app para gerar o guia de identidade visual (tipo slides) de
> ~/projects/meu-app. Analise o repositório e preencha as seções com (TODO)
> por conta: leia os textos da interface para escrever o tom de voz, cite os
> arquivos de onde tirou cada afirmação e deixe (TODO) só no que o
> repositório não responder. Gere o PDF no fim.

Não é preciso dizer onde procurar: o `list_sections` devolve, para cada seção
pendente, uma dica do que abrir naquele repositório (os arquivos de texto de
interface para o tom de voz, os scripts de checagem para os usos indevidos, as
rotas para os contratos), e o `inspect_app` já entrega a marca detectada e os
arquivos com mais texto de interface.

O caminho que o assistente segue:

1. `inspect_app` e `create_doc`: o doc_app lê o app e cria o YAML (ou reaproveita
   o que já existe, sem perder edições). O `inspect_app` devolve também as
   seções do README, os grupos de rotas, os módulos, os testes, as pendências
   do código e, no tipo `slides`, a identidade visual detectada (assets, cores,
   fontes e os arquivos com mais texto de interface).
2. `list_sections`: lista as seções com `(TODO)` e dá uma dica de onde procurar
   a informação para cada uma.
3. Para cada seção, o assistente lê os arquivos do app e chama `write_section`.
   Pode criar subseções (`add_section`) e remover as que não se aplicam
   (`remove_section`).
4. `build_pdf`: gera o PDF e informa o caminho.

O servidor envia ao assistente regras de conteúdo: escrever em português, só
afirmar o que o código confirma, citar o arquivo de onde tirou cada regra,
manter `(TODO)` quando não conseguir confirmar algo, não apagar os fatos nem o
texto aproveitado do README, não substituir os blocos de marca (logo, amostras
de cor, área de proteção) por texto, e nunca copiar segredos.

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
| `build_pdf` | Gera o documento (`fmt`: `pdf`, `docx` ou `pptx`), com marca opcional |
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
| `README.md` | Introdução da visão geral, pré-requisitos, passos de instalação e **o texto das demais seções**: uso, decisões de arquitetura, organização, qualidade e lacunas (veja [Seções aproveitadas do README](#seções-aproveitadas-do-readme)) |
| `package.json` | Framework e versão, bibliotecas por categoria, scripts, dependências, gerenciador de pacotes (`packageManager` ou lockfile), regras do lint-staged |
| `pyproject.toml` | Versão do Python, dependências, scripts, framework web |
| `requirements.txt` | Framework web, dependências e bibliotecas por categoria (banco, autenticação, servidor, nuvem) |
| `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle` | Linguagem e se é um serviço web |
| `.env.example`, `.env.sample`, `.env.template`, `.env.dist`, `example.env`, `env.example` | Variáveis de ambiente, com a descrição tirada dos comentários e o valor de exemplo |
| Pastas | Árvore de `src/` (ou da raiz) e tabela das pastas principais, com o conteúdo de cada uma |
| Rotas no código | O que o app **expõe** (FastAPI, Flask, Express e afins, NestJS, Spring, Laravel, Go), as **telas** que declara (App Router do Next, `<Route path>` do react-router, listas de rotas do Vue Router e do Angular) e os endpoints que apenas **consome** (clientes HTTP como axios) — cada grupo com a base, as operações e o arquivo |
| `features/`, `modules/`, `domains/` | Tabela de módulos e os arquivos de cada um |
| `test_*.py`, `*.test.ts`, `*.spec.ts` | Quantidade de testes por pasta e o runner, quando está nas dependências |
| `TODO`, `FIXME` e `HACK` no código | Lista de pendências em "Lacunas conhecidas", com arquivo e linha |
| `.husky/` | O que cada hook de git roda |
| `.github/workflows/` | Quando cada workflow dispara e quais comandos roda |
| `Dockerfile` | Estágios, porta, usuário, comando de início, argumentos de build e a versão do runtime da imagem base |
| `docker-compose.yml` | Ferramenta reconhecida e o comando `docker compose up -d` |
| Arquivos de configuração | Ferramentas em uso (Biome, ESLint, TypeScript, Vite, Next, Orval etc.) |
| CSS, Sass, Less, `tailwind.config`, manifest | Cores da marca (só em frontend) |
| `public/`, `static/`, `assets/`, `www/`, `images/` | Arquivos de marca: logotipo, símbolo, mascote, favicon, OG image, com formato e dimensões medidas (tipo `slides`) |
| `next/font`, `<link>` do Google Fonts, `@font-face`, `fontFamily` do Tailwind, variáveis de CSS/Sass/Less | Famílias tipográficas e pesos declarados (tipo `slides`) |
| `layout.tsx`, `index.html`, `manifest.json`, `app.json`, `pubspec.yaml`, `package.json` | Título, template de título, descrição e idioma, cada um com o arquivo que o declara (tipo `slides`) |

### Seções aproveitadas do README

Cada seção do README entra na seção equivalente do documento, com as subseções
dela viradas em subtítulos. O que o documento já mostra como fato extraído
(stack, scripts, instalação, variáveis, Docker) não é repetido.

| Título no README (por aproximação) | Seção do documento |
|---|---|
| Decisões, arquitetura, regras, convenções, padrões | Regras e decisões de arquitetura |
| Como usar, uso, funcionalidades, telas, fluxos, rotas | Como se usa a aplicação |
| APIs, integrações, contratos, OpenAPI, webhooks | APIs e integrações |
| Módulos, domínios, componentes | Módulos e componentes |
| Organização, estrutura, pastas | Organização do código |
| Qualidade, testes, lint, CI, scripts | Qualidade e testes |
| Lacunas, limitações, pendências, roadmap, dívida | Lacunas conhecidas |

Uma seção do README é aproveitada uma única vez. Sem README, o documento é
montado só com o que o código confirma: rotas, módulos, dependências, testes,
hooks, CI e Docker.

### O que continua marcado com `(TODO)`

Nada que esteja escrito nos arquivos. Sobra o que depende de interpretação e
que nenhum arquivo responde:

- o propósito do app, quando não há README nem `description`;
- o caminho principal do usuário entre as telas ou endpoints (as rotas entram,
  a narrativa não);
- a responsabilidade de cada pasta e de cada módulo (os arquivos entram, o
  "para que serve" não);
- as invariantes de arquitetura, quando o README não as documenta;
- o que cada checagem de CI protege.

Detalhes:

- **Segurança:** `.env`, `.env.local` e outros arquivos de ambiente reais nunca
  são lidos. Só os arquivos de exemplo da tabela.
- **Codificação:** arquivos em UTF-8, UTF-8 com BOM, UTF-16 (comum em README
  criado no Windows) e Latin-1 são lidos corretamente, com qualquer fim de
  linha (LF ou CRLF).
- **Caminhos:** os arquivos citados no documento (`src/features/auth`,
  `app/routes.py:16`) aparecem com barra normal nas três plataformas, para o
  mesmo YAML servir em Linux, WSL, macOS e Windows.
- **Pastas ignoradas:** `node_modules`, `.git`, `dist`, `build`, `.next`,
  `.venv` e outras de artefatos. A varredura para em 1500 arquivos de código.
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
No Linux, no WSL e no macOS, `~/.local/bin` não está no `PATH`. Adicione ao
`~/.zshrc` (ou `~/.bashrc`) e abra um novo terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

No Windows o comando é `doc-app`, com hífen. Se não for encontrado depois do
`uv tool install`, rode `uv tool update-shell` e abra um novo terminal.

**Erro de fonte ao gerar o PDF**
Nenhuma pasta conhecida tinha o trio de fontes. No Ubuntu, Debian ou WSL:
`sudo apt install fonts-dejavu-core`. Em outro sistema, aponte
`DOC_APP_FONT_DIR` para uma pasta com `DejaVuSans.ttf`,
`DejaVuSans-Bold.ttf` e `DejaVuSansMono.ttf` (veja
[Requisitos](#requisitos)). A mensagem de erro diz qual arquivo faltou.

**O documento ficou com pouca coisa e muitos `(TODO)`**
O repositório não tem README, ou o README só tem instalação e scripts. O texto
das seções de uso, arquitetura e lacunas vem das seções equivalentes do README
(veja [Seções aproveitadas do README](#seções-aproveitadas-do-readme)).
Sem elas, só o que o código declara entra: rotas, módulos, dependências,
testes, hooks, CI e Docker.

**As rotas ou os módulos do app não apareceram**
As rotas são reconhecidas por declaração: `APIRouter` do FastAPI, `Blueprint`
do Flask, `page.tsx` do App Router do Next e `<Route path=…>` do react-router.
Outro framework, ou rotas montadas em tempo de execução, não aparecem. Os
módulos saem de uma pasta `features/`, `modules/`, `domains/`, `apps/`,
`packages/` ou `services/`, na raiz, em `src/` ou em `app/`.

**O PDF repetiu algo errado que está no README do app**
O doc_app não corrige o README: ele aproveita o texto como está. Corrija no
README do app e recrie (`doc_app clean <app>`), ou corrija direto no YAML.

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

Em Linux, WSL ou macOS:

```bash
./scripts/cleanup.sh            # remove comando, conexões MCP, cache e artefatos
./scripts/cleanup.sh --venv     # também remove o ambiente .venv
./scripts/cleanup.sh --yes      # sem confirmação
```

No Windows:

```powershell
uv run python -m doc_app.clients unregister all   # conexões MCP
uv run doc-app clean --yes                        # cache
uv tool uninstall doc-app                         # comando
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
scripts/install.sh     instalação (Linux, WSL, macOS)
scripts/cleanup.sh     desinstalação (Linux, WSL, macOS)
scripts/check_platform.py  checagem das partes que dependem da plataforma
src/doc_app/
  cli.py               painel e comandos de linha
  core.py              criar documento e gerar o arquivo (usado pela CLI e pelo MCP)
  extract.py           fatos do repositório (README, scripts, env, pastas, rotas,
                       módulos, testes, CI, Docker)
  identity.py          identidade visual (assets, cores, fontes, tokens)
  md.py                Markdown do README convertido em blocos do documento
  detect.py            stack e tipo do app (frontend, backend...)
  brand.py             cores da marca de frontends
  skeleton.py          documento inicial a partir dos fatos
  sections.py          leitura e edição do YAML por seção
  dsl.py               tipos de bloco e validação
  loader.py            leitura e escrita do YAML
  theme.py             paleta, fontes, tipografia e tipos de documentação
  renderer.py          desenho do PDF (fpdf2): capa, sumário, blocos, marca
  builder.py           monta capa, sumário e corpo
  slides.py            apresentação 16:9: capa, divisórias e blocos de marca
  office.py            Word (.docx) e PowerPoint (.pptx) com o desenho do PDF
  textio.py            leitura de arquivos com detecção de codificação
  mcp_server.py        servidor MCP (ferramentas para assistentes)
  clients.py           conexão com os assistentes de IA
  agent/               reservado para um modo com modelo próprio (não implementado)
workspace/             cache local dos documentos (fora do git)
```

As checagens rodam em qualquer sistema, inclusive no PowerShell:

```bash
uv run python scripts/check_platform.py   # fontes, caminhos, destino do arquivo
uv run python scripts/check_extract.py    # análise do repositório
uv run python scripts/check_slides.py     # identidade visual e deck em PDF
uv run python scripts/check_office.py     # exportação .docx e .pptx
uv run python scripts/check_menu.py       # navegação do painel
```

## Limitações

- No Windows, os scripts `install.sh` e `cleanup.sh` não rodam; a instalação é
  feita com `uv tool install` (veja [No Windows](#no-windows)).
- No Windows sem as fontes DejaVu, o PDF sai com Arial e Consolas: o desenho
  muda um pouco em relação ao Linux.
- A extração lê arquivos, estrutura e declarações de rota; ela não interpreta o
  que o código faz. Propósito, fluxos e regras não documentadas no README
  dependem de uma pessoa ou de um assistente.
- No guia de identidade visual (`slides`), a fonte da marca não é embutida no
  PDF e arquivos `.ico` não são desenhados; o deck também depende do
  `app_path` gravado no YAML para achar as imagens.
- As rotas são encontradas por declaração conhecida (FastAPI, Flask, App Router
  do Next, react-router). Rotas montadas em tempo de execução, ou por outro
  framework, não aparecem.
- Só a prosa do README é aproveitada: se o README estiver desatualizado, o
  documento herda o erro. Revise o YAML.
- O texto escrito por um assistente pode conter erros de interpretação. Revise
  o YAML antes de distribuir o PDF.
- O cache é apagado por `clean` e `cleanup.sh`; documentos com muito trabalho
  manual precisam de cópia em outro lugar.
- A marca de uso restrito é só visual.
- O `.docx` e o `.pptx` repetem o desenho do PDF, mas não as quebras: Word e
  PowerPoint refluem o texto, e a fonte é substituída se a família do tema não
  estiver instalada na máquina que abre. Logo e área de proteção em SVG também
  não entram (o Office não lê SVG).
