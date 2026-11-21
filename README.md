# Jane — English Vocabulary Builder for Anki

CLI em Python para construir, gerenciar e exportar um deck estruturado de vocabulário em inglês (~3.705 palavras base a partir do cruzamento **Oxford 3000 + NGSL**, extensível com vocabulário customizado), com curadoria pedagógica (`i+1`), persistência local em SQLite e exportação em `.tsv` compatível com o **Anki** e geração de áudio via **HyperTTS / vocab.ai**.

## Requisitos e Instalação

- **Python 3.12+**
- Nenhuma dependência externa de runtime (usa apenas a biblioteca padrão do Python).

Instale o comando global `jane` em modo editável:

```bash
uv tool install --editable .
# ou com pip:
# pip install -e .

jane --version
```

*(Sem instalação global, todos os comandos funcionam via `python3 -m jane <subcomando>` na raiz do repositório.)*

### Workspace (`JANE_HOME` / `--home`)

Os caminhos padrão (`data/jane.db`, `data/raw/`, `exports/`, `anki/`) são resolvidos na seguinte ordem: `--home` > `JANE_HOME` > diretório atual (se for um workspace Jane) > raiz do pacote (em instalação editável) > diretório atual. Flags explícitas (`--db`, `--raw-dir`, `--exports-dir`, `--out`) têm prioridade absoluta.

## Uso Rápido da CLI

```bash
# Reconstruir data/jane.db a partir de data/raw/ e dos TSVs versionados em exports/
jane rebuild

# Popular o banco do zero a partir dos datasets em data/raw/
jane seed

# Consultar progresso geral e por lote
jane status

# Adicionar palavras ou expressões customizadas
jane add "burn out" "deploy" --pos "phrasal verb" --cefr B1

# Buscar próximas palavras pendentes de um lote (JSON com contexto i+1)
jane next --batch 1 --limit 20
# (opcional: --no-known para omitir a lista de palavras já conhecidas)

# Validar e salvar cards gerados a partir de um arquivo JSON (ou '-' para stdin)
jane save --file cards.json
# (opcional: --force para sobrescrever cards existentes)

# Exportar um lote inteiro ou subconjunto seletivo em .tsv UTF-8 + estimativa HyperTTS
jane export --batch 1
jane export --modified
jane export --uids jane_0001_01,jane_0042_01
jane export --words "run,burn out"
jane export --since 2026-11-20

# Marcar todas as palavras de um lote como dominadas (mastered)
jane master --batch 1

# Gerar o pacote .apkg com o Note Type "Jane Vocab" para o Anki
jane template
```

Para consultar todas as opções disponíveis:

```bash
jane --help
```

## Skills Operacionais (`.agents/skills/`)

O repositório inclui 3 skills versionadas para agentes de IA operarem o Jane de forma padronizada:

- [`jane-generate-batches`](.agents/skills/jane-generate-batches/SKILL.md) — Geração de novos lotes de cards (`status` → `next` → redação `i+1` → `save` → `export`).
- [`jane-expand-and-curate`](.agents/skills/jane-expand-and-curate/SKILL.md) — Cadastro de palavras customizadas (`add`), polissemia, correção com `--force` e exportação seletiva com alerta de áudio HyperTTS.
- [`jane-setup`](.agents/skills/jane-setup/SKILL.md) — Runbook de instalação da CLI `jane`, reconstrução do banco (`rebuild`) e configuração do Anki + HyperTTS.

## Estrutura do Repositório

```text
.
├── .agents/skills/    # Skills operacionais do Jane para agentes de IA
├── anki/              # Templates HTML/CSS e pacote .apkg do Note Type "Jane Vocab"
├── data/
│   └── raw/           # Datasets de referência (NGSL 1.2 e Oxford 3000 / CEFR)
├── docs/              # Documentação de pedagogia, arquitetura, schema e lições aprendidas
├── exports/           # Lotes .tsv recém-exportados aguardando importação no Anki
│   └── imported/      # Lotes .tsv já importados no Anki (fonte de verdade versionada)
├── jane/              # Código-fonte da CLI e pipeline SQLite
└── tests/             # Suíte de testes unitários e de integração
```

- `data/jane.db` é gerado localmente e ignorado pelo Git (`.gitignore`); use `jane rebuild` para recriá-lo a partir dos `.tsv`.
- `exports/` armazena arquivos `.tsv` prontos para importação; após importados no Anki, os lotes são movidos para `exports/imported/`.

## Testes

Execute a suíte de testes com `unittest`:

```bash
python3 -m unittest discover -s tests -v
```

## Releases

Versões estáveis são publicadas manualmente por tags semânticas `v*.*.*` via GitHub Actions (`.github/workflows/release.yml`), gerando `.whl`, `.tar.gz` e `jane_vocab_template.apkg` na GitHub Release após validar versão e testes:

```bash
# Instalar uma versão publicada diretamente de uma tag
uv tool install git+https://github.com/Wather17/jane@vX.Y.Z
```

Para publicar uma nova versão, atualize `jane/__init__.py` e `pyproject.toml`, integre na `main` e envie a tag `vX.Y.Z` (`git tag vX.Y.Z && git push origin vX.Y.Z`). Veja o guia completo em [Desenvolvimento, CI e Releases](docs/07-desenvolvimento-ci-e-releases.md).

## Documentação

As decisões pedagógicas, arquiteturais e técnicas estão detalhadas em `docs/`:

1. [Visão e Princípios Pedagógicos](docs/01-visao-e-pedagogia.md) — Como o método funciona para quem está começando do zero, regra do `i+1`, estrutura dos cards e controle de lotes.
2. [Arquitetura e Fluxo de Trabalho](docs/02-arquitetura-e-fluxo.md) — SQLite, cruzamento Oxford 3000 + NGSL, Mini CLI operado por agente em mini-lotes e exportação `.tsv` + HyperTTS.
3. [Edge Cases e Regras (O que fazer / Não fazer)](docs/03-edge-cases-e-regras.md) — Armadilhas mapeadas, validações obrigatórias e margem de segurança para a cota de TTS.
4. [Pesquisa: HyperTTS e Anki](docs/04-hypertts-e-anki.md) — Como o HyperTTS trata HTML, multiplicadores de cota (1x, 2x, 15x), boas práticas de campos e formato final do `.tsv`.
5. [Schema do SQLite, Priorização e Mini CLI](docs/05-schema-e-cli.md) — Modelo de dados final (`words` e `cards`), cálculo de tiers/lotes e contrato completo da CLI `jane`.
6. [Lições do Teste de 50 Palavras](docs/06-melhorias-e-licoes-teste-50.md) — Resultados reais do `test_50.tsv`, consumo medido de caracteres e melhorias mapeadas.
7. [Desenvolvimento, CI e Releases](docs/07-desenvolvimento-ci-e-releases.md) — Workflows do GitHub Actions, política SemVer por tags `v*.*.*`, convenções de branches/commits/labels e fluxo operacional para agentes.

## Licença

O código-fonte deste repositório é distribuído sob a [Licença MIT](LICENSE).

> **Nota de atribuição sobre `data/raw/`:** Os datasets de referência em `data/raw/` (New General Service List — **NGSL** e **Oxford 3000 / CEFR**) permanecem sujeitos às licenças e termos de uso de seus respectivos autores e mantenedores originais.
