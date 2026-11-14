# 05 — Schema do SQLite, Priorização e Contrato do Mini CLI

Este documento fecha a especificação técnica da base de dados e da interface de linha de comando (`jane`) antes da implementação.

---

## 1. Decisão de Enriquecimento (Opção A)

Na análise dos arquivos brutos em `data/raw/`:
- **União (`NGSL 1.2 + Oxford 3000`):** **3.705** palavras únicas.
- **Cobertura automática sem IA:** **3.051 palavras (~82,3%)** já possuem `ngsl_rank` (2.809) e/ou `cefr_level` `A1–B2` + `pos` via `oxford_cefr.json` (1.986).
- **Decisão:** O comando `seed` faz todo o cruzamento e enriquecimento de forma **100% determinística** em Python. As **654 palavras** exclusivas do `oxford_3000.json` que não possuem rank nem CEFR caem naturalmente nos últimos lotes (Tier 4) e terão sua classe gramatical e sentido definidos pelo agente apenas quando chegar a vez do seu lote.

---

## 2. Schema do SQLite (`data/jane.db`)

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS words (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma           TEXT NOT NULL UNIQUE,
    in_oxford       INTEGER NOT NULL DEFAULT 0, -- 0 ou 1
    in_ngsl         INTEGER NOT NULL DEFAULT 0, -- 0 ou 1
    cefr_level      TEXT,                       -- 'A1', 'A2', 'B1', 'B2' ou NULL
    pos             TEXT,                       -- ex: 'noun', 'verb', 'noun, verb' ou NULL
    ngsl_rank       INTEGER,                    -- 1..2809 ou NULL
    ngsl_freq       REAL,                       -- Adjusted Frequency per Million ou NULL
    tier            INTEGER NOT NULL,           -- 1..4 (regra de prioridade)
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
    FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE,
    UNIQUE (word_id, sense_index)
);

CREATE INDEX IF NOT EXISTS idx_words_batch_status ON words(batch_number, status);
CREATE INDEX IF NOT EXISTS idx_words_priority ON words(priority_score);
CREATE INDEX IF NOT EXISTS idx_cards_word_id ON cards(word_id);
```

---

## 3. Regra de Priorização e Divisão em Lotes

Para garantir que um **iniciante absoluto** receba pronomes, verbos auxiliares, conectores e palavras `A1` logo no Lote 1:

1. **Tiers:**
   - **Tier 1:** `in_oxford = 1 AND in_ngsl = 1` (Núcleo de Ouro — 2.309 palavras)
   - **Tier 2:** `in_ngsl = 1 AND in_oxford = 0` (Frequentes na NGSL — 500 palavras)
   - **Tier 3:** `in_oxford = 1 AND in_ngsl = 0 AND cefr_level IS NOT NULL` (Oxford com CEFR)
   - **Tier 4:** `in_oxford = 1 AND in_ngsl = 0 AND cefr_level IS NULL` (Restante Oxford 3000)

2. **Ordenação dentro dos Tiers:**
   - Palavras com `ngsl_rank <= 150` recebem bônus máximo no Tier 1 para garantir que palavras estruturais (*the, be, I, you, have, do, can, in, on, to, not, what*) fiquem no **Lote 1**, mesmo que alguma não tenha CEFR explícito no JSON auxiliar.
   - Nos demais casos: ordenar por `tier ASC`, peso do `cefr_level` (`A1=1, A2=2, B1=3, B2=4, NULL=5`), e desempate por `ngsl_rank ASC` (e alfabético por último).

3. **Tamanho do Lote:**
   - Padrão inicial: **`120` palavras por lote** (configurável via `--batch-size` no `seed`).
   - Motivo: Ritmo confortável de estudo (~10–12 dias a 10 palavras/dia) e margem segura na cota mensal de 250k caracteres do HyperTTS (mesmo com multiplicador 15x).

---

## 4. Contrato do Mini CLI (`jane`)

Interface simples em Python (`python -m jane ...` ou script `jane`) pensada para ser operada em **mini-lotes** pelo agente no terminal:

| Comando | Função | Detalhes |
| :--- | :--- | :--- |
| `seed` | Popula o SQLite com `data/raw/` | `--batch-size 120`. Idempotente (não apaga cards já gerados se rodar de novo). |
| `status` | Mostra resumo do banco e lotes | Lista lotes com contagem por status (`pending`, `generated`, `exported`, `mastered`) e soma de `char_count`. |
| `next` | Entrega próximo mini-lote para o agente | `--batch 1 --limit 20`. Retorna JSON com as próximas palavras `pending` + lista `known_words` (lotes anteriores / já geradas) para respeitar o `i+1`. |
| `save` | Valida e grava frases geradas | `--file chunk.json`. Valida campos obrigatórios, tamanho da frase (3–18 palavras), presença da palavra/flexão, gera `card_uid`, calcula `char_count` e atualiza `status='generated'`. |
| `export` | Exporta lote para `.tsv` (Anki) | `--batch 1`. Gera `exports/batch_01.tsv` (com `Card_UID` na 1ª coluna), marca como `exported` e exibe estimativa de consumo HyperTTS (`1x`, `2x`, `15x`). |
| `master` | Marca lote como dominado | `--batch 1`. Atualiza palavras do lote para `mastered` quando você concluir o estudo no Anki. |
