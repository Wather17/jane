# 05 — Schema do SQLite, Priorização e Contrato da CLI

Este documento consolida a especificação técnica da base de dados SQLite (`data/jane.db`) e da interface de linha de comando (`jane`).

---

## 1. Decisão de Enriquecimento (Opção A)

Na análise dos arquivos brutos em `data/raw/`:
- **União (`NGSL 1.2 + Oxford 3000`):** **3.705** palavras únicas.
- **Cobertura automática sem IA:** **3.051 palavras (~82,3%)** já possuem `ngsl_rank` (2.809) e/ou `cefr_level` `A1–B2` + `pos` via `oxford_cefr.json` (1.986).
- **Decisão:** O comando `seed` faz todo o cruzamento e enriquecimento de forma **100% determinística** em Python. As **654 palavras** exclusivas do `oxford_3000.json` que não possuem rank nem CEFR caem naturalmente nos últimos lotes (Tier 4) e têm classe gramatical e sentido definidos quando chega a vez do seu lote.
- **Vocabulário customizado:** Palavras e expressões adicionadas via `jane add` ou importadas de TSVs fora de `data/raw/` via `jane rebuild` recebem **Tier 5** (`in_oxford = 0`, `in_ngsl = 0`).

---

## 2. Schema do SQLite (`data/jane.db`)

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS words (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma           TEXT NOT NULL UNIQUE,
    in_oxford       INTEGER NOT NULL DEFAULT 0, -- 0 ou 1
    in_ngsl         INTEGER NOT NULL DEFAULT 0, -- 0 ou 1
    cefr_level      TEXT,                       -- 'A1', 'A2', 'B1', 'B2', 'C1', 'C2' ou NULL
    pos             TEXT,                       -- ex: 'noun', 'verb', 'phrasal verb' ou NULL
    ngsl_rank       INTEGER,                    -- 1..2809 ou NULL
    ngsl_freq       REAL,                       -- Adjusted Frequency per Million ou NULL
    tier            INTEGER NOT NULL,           -- 1..4 (base) ou 5 (customizado)
    priority_score  REAL NOT NULL,              -- menor = mais prioritário
    batch_number    INTEGER NOT NULL,           -- 1, 2, 3...
    status          TEXT NOT NULL DEFAULT 'pending', -- 'pending' | 'generated' | 'exported' | 'mastered'
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cards (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    card_uid          TEXT NOT NULL UNIQUE,     -- chave estável para o Anki, ex: 'jane_0001_01'
    word_id           INTEGER NOT NULL,
    sense_index       INTEGER NOT NULL DEFAULT 1, -- permite polissemia (1, 2, 3...)
    pos               TEXT,                     -- classe gramatical usada nesta frase
    difficulty        TEXT NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    sentence_display  TEXT NOT NULL,            -- com <b>palavra</b> para o card
    sentence_audio    TEXT NOT NULL,            -- texto puro sem HTML para o HyperTTS
    sentence_pt       TEXT NOT NULL,            -- tradução natural em PT-BR
    word_meaning_pt   TEXT NOT NULL,            -- sentido específico no contexto
    notes             TEXT DEFAULT '',          -- dica curta opcional
    char_count        INTEGER NOT NULL,         -- LENGTH(sentence_audio)
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    exported_at       TEXT,                     -- NULL quando novo ou alterado via save --force
    FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE,
    UNIQUE (word_id, sense_index)
);

CREATE INDEX IF NOT EXISTS idx_words_batch_status ON words(batch_number, status);
CREATE INDEX IF NOT EXISTS idx_words_priority ON words(priority_score);
CREATE INDEX IF NOT EXISTS idx_cards_word_id ON cards(word_id);
```

- **Migração idempotente (`init_db`):** Bancos criados antes da adição de `cards.updated_at` e `cards.exported_at` são migrados automaticamente com backfill (`updated_at = created_at` para todos os cards; `exported_at = created_at` para cards cujas palavras já estão em `exported` ou `mastered`).
- **Rastreamento de modificações:** `save` grava `updated_at = datetime('now')` e `exported_at = NULL` (inclusive em `--force`); `export` e `rebuild` gravam `exported_at = datetime('now')`.

---

## 3. Regra de Priorização e Divisão em Lotes

Para garantir que um **iniciante absoluto** receba pronomes, verbos auxiliares, conectores e palavras `A1` logo no Lote 1:

1. **Tiers:**
   - **Tier 1:** `in_oxford = 1 AND in_ngsl = 1` (Núcleo de Ouro — 2.309 palavras)
   - **Tier 2:** `in_ngsl = 1 AND in_oxford = 0` (Frequentes na NGSL — 500 palavras)
   - **Tier 3:** `in_oxford = 1 AND in_ngsl = 0 AND cefr_level IS NOT NULL` (Oxford com CEFR)
   - **Tier 4:** `in_oxford = 1 AND in_ngsl = 0 AND cefr_level IS NULL` (Restante Oxford 3000)
   - **Tier 5:** Palavras e expressões customizadas (`jane add` / `jane rebuild` fora de `data/raw/`)

2. **Ordenação dentro dos Tiers:**
   - Palavras com `ngsl_rank <= 150` recebem bônus máximo no Tier 1 para garantir que palavras estruturais (*the, be, I, you, have, do, can, in, on, to, not, what*) fiquem no **Lote 1**, mesmo que alguma não tenha CEFR explícito no JSON auxiliar.
   - Nos demais casos base (Tiers 1–4): ordenar por `tier ASC`, peso do `cefr_level` (`A1=1, A2=2, B1=3, B2=4, NULL=5`), e desempate por `ngsl_rank ASC` (e alfabético por último).
   - No Tier 5: `priority_score = 5_000_000 + batch_number * 1000 + offset_no_lote`.

3. **Tamanho do Lote:**
   - Padrão: **`120` palavras por lote** (configurável via `--batch-size` em `seed`, `rebuild` e `add`).
   - Motivo: Ritmo confortável de estudo (~10–12 dias a 10 palavras/dia) e margem segura na cota mensal de 250k caracteres do HyperTTS (mesmo com multiplicador 15x).

---

## 4. Contrato da CLI (`jane`)

Interface empacotada via `pyproject.toml` (`jane ...` ou `python3 -m jane ...`), sem dependências externas.

### Flags Globais e Resolução de Workspace (`jane/paths.py`)

| Flag / Variável | Função |
| :--- | :--- |
| `--version` | Exibe `jane <versão>` (`jane.__version__`) e encerra com exit code `0`. |
| `--home <dir>` | Define explicitamente o diretório base do workspace (sobrescreve `JANE_HOME`). |
| `JANE_HOME` | Variável de ambiente usada quando `--home` não é passado. |
| `--db <caminho>` | Caminho explícito do banco SQLite (padrão: `<jane_home>/data/jane.db`). |

Ordem de precedência para `<jane_home>`: `--home` → `JANE_HOME` → `CWD` (se contiver `data/raw/` ou `data/jane.db`) → raiz do pacote (se contiver `data/raw/`) → `CWD`.

### Subcomandos

| Comando | Flags Principais | Função e Comportamento |
| :--- | :--- | :--- |
| `seed` | `--batch-size 120`, `--raw-dir`, `--sample N`, `--rng-seed 42` | Popula `words` idempotentemente a partir de `data/raw/` preservando cards e palavras customizadas (`tier = 5`). |
| `rebuild` | `--exports-dir`, `--raw-dir`, `--batch-size 120`, `--skip-seed` | Reconstrói o SQLite determinística e idempotentemente a partir de `data/raw/` (opcional) + `exports/imported/batch_*.tsv` e `exports/batch_*.tsv`, preservando `Card_UID`, `mastered` e criando palavras customizadas ausentes. |
| `status` | *(nenhuma)* | Mostra resumo JSON de totais de palavras por status, total de cards/caracteres e progresso por lote. |
| `add` | `words...`, `--batch N`, `--batch-size 120`, `--pos`, `--cefr` | Cadastra palavras/expressões customizadas (`tier = 5`, `status = 'pending'`), deduplica, lista existentes em `skipped_existing` e abre novo lote automaticamente quando o maior lote já tem palavras `exported`/`mastered`. |
| `next` | `--batch 1`, `--limit 20`, `--no-known` | Retorna JSON com as próximas palavras `pending` do lote e a lista `known_words` para `i+1` (omitida com `--no-known`). |
| `save` | `--file <path\|->`, `--force` | Valida e grava cards a partir de JSON (arquivo ou `stdin`), verificando 3–18 palavras, `<b>...</b>` em `sentence_display`, texto puro idêntico em `sentence_audio`, gera `card_uid`, atualiza `updated_at` e limpa `exported_at = NULL`. |
| `export` | `--batch N` \| `--uids` \| `--words` \| `--modified` \| `--since`, `--out`, `--no-header` | Exporta lote completo (`exports/batch_NN.tsv`) ou subconjunto seletivo (`exports/update_YYYYMMDD_HHMMSS.tsv`), atualiza `cards.exported_at` e `words.status = 'exported'`, e retorna estimativa de cota HyperTTS (`1x`, `2x`, `15x`). |
| `master` | `--batch N` | Marca todas as palavras do lote como `mastered`. |
| `template` | `--out` | Gera o pacote `.apkg` standalone com o Note Type `Jane Vocab` (padrão: `<jane_home>/anki/jane_vocab_template.apkg`). |
