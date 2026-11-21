# Jane — English Vocabulary Builder for Anki

CLI em Python para construir, gerenciar e exportar um deck estruturado de vocabulário em inglês (~3.705 palavras base a partir do cruzamento **Oxford 3000 + NGSL**), com curadoria pedagógica (`i+1`), persistência local em SQLite e exportação em `.tsv` compatível com o **Anki** e geração de áudio via **HyperTTS / vocab.ai**.

## Requisitos

- **Python 3.12+**
- Nenhuma dependência externa (usa apenas a biblioteca padrão do Python).

## Uso Rápido da CLI

Todos os comandos aceitam a flag global `--db <caminho>` (padrão: `data/jane.db`):

```bash
# 1. Popular o banco SQLite a partir dos datasets em data/raw/
python3 -m jane seed

# 2. Consultar progresso geral e por lote
python3 -m jane status

# 3. Buscar próximas palavras pendentes de um lote (JSON com contexto i+1)
python3 -m jane next --batch 1 --limit 20
# (opcional: --no-known para omitir a lista de palavras já conhecidas)

# 4. Validar e salvar cards gerados a partir de um arquivo JSON (ou '-' para stdin)
python3 -m jane save --file cards.json
# (opcional: --force para sobrescrever cards existentes)

# 5. Exportar um lote em .tsv UTF-8 pronto para importar no Anki + estimativa HyperTTS
python3 -m jane export --batch 1
# (opcionais: --out caminho.tsv, --no-header)

# 6. Marcar todas as palavras de um lote como dominadas (mastered)
python3 -m jane master --batch 1

# 7. Gerar o pacote .apkg com o Note Type "Jane Vocab" para o Anki
python3 -m jane template
```

Para consultar todas as opções disponíveis:

```bash
python3 -m jane --help
```

## Estrutura do Repositório

```text
.
├── anki/              # Templates HTML/CSS e pacote .apkg do Note Type "Jane Vocab"
├── data/
│   └── raw/           # Datasets de referência (NGSL 1.2 e Oxford 3000 / CEFR)
├── docs/              # Documentação de pedagogia, arquitetura, schema e lições aprendidas
├── exports/           # Lotes .tsv recém-exportados aguardando importação no Anki
│   └── imported/      # Lotes .tsv já importados no Anki (fonte de verdade versionada)
├── jane/              # Código-fonte da CLI e pipeline SQLite
└── tests/             # Suíte de testes unitários e de integração
```

- `data/jane.db` é gerado localmente e ignorado pelo Git (`.gitignore`).
- `exports/` armazena arquivos `.tsv` prontos para importação; após importados no Anki, os lotes são movidos para `exports/imported/`.

## Testes

Execute a suíte de testes com `unittest`:

```bash
python3 -m unittest discover -s tests -v
```

## Documentação

As decisões pedagógicas, arquiteturais e técnicas estão detalhadas em `docs/`:

1. [Visão e Princípios Pedagógicos](docs/01-visao-e-pedagogia.md) — Como o método funciona para quem está começando do zero, regra do `i+1`, estrutura dos cards e controle de lotes.
2. [Arquitetura e Fluxo de Trabalho](docs/02-arquitetura-e-fluxo.md) — SQLite, cruzamento Oxford 3000 + NGSL, Mini CLI operado por agente em mini-lotes e exportação `.tsv` + HyperTTS.
3. [Edge Cases e Regras (O que fazer / Não fazer)](docs/03-edge-cases-e-regras.md) — Armadilhas mapeadas, validações obrigatórias e margem de segurança para a cota de TTS.
4. [Pesquisa: HyperTTS e Anki](docs/04-hypertts-e-anki.md) — Como o HyperTTS trata HTML, multiplicadores de cota (1x, 2x, 15x), boas práticas de campos e formato final do `.tsv`.
5. [Schema do SQLite, Priorização e Mini CLI](docs/05-schema-e-cli.md) — Modelo de dados final (`words` e `cards`), cálculo de tiers/lotes e contrato dos comandos `seed`, `next`, `save`, `export`.
6. [Lições do Teste de 50 Palavras](docs/06-melhorias-e-licoes-teste-50.md) — Resultados reais do `test_50.tsv`, consumo medido de caracteres e melhorias mapeadas.

## Licença

O código-fonte deste repositório é distribuído sob a [Licença MIT](LICENSE).

> **Nota de atribuição sobre `data/raw/`:** Os datasets de referência em `data/raw/` (New General Service List — **NGSL** e **Oxford 3000 / CEFR**) permanecem sujeitos às licenças e termos de uso de seus respectivos autores e mantenedores originais.
