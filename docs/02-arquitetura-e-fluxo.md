# 02 — Arquitetura e Fluxo de Trabalho

> **Objetivo arquitetural:** Pipeline simples, local, determinístico e sem custo extra de API de LLM — usando um banco **SQLite** + **Mini CLI** operado diretamente pelo agente de IA no terminal, exportando `.tsv` limpo para o **Anki + HyperTTS**.

---

## 1. Fonte de Palavras: Cruzamento Oxford 3000 + NGSL

Fazer a **união** das duas listas no banco, preservando os metadados de origem para ordenação inteligente:

- **Oxford 3000:** Curada por lexicógrafos para estudantes, já classificada por nível CEFR (`A1`, `A2`, `B1`, `B2`).
- **NGSL (New General Service List):** ~2.800 lemas baseados em frequência estatística de uso real.

### Priorização no Banco
Em vez de misturar tudo aleatoriamente, calculamos uma prioridade de estudo:
1. **Tier 1 (Núcleo de Ouro):** Palavras presentes em **ambas** as listas, ordenadas por `CEFR` (`A1` → `A2`) e `ngsl_rank`.
2. **Tier 2 (Práticas / Frequentes):** Palavras que aparecem apenas na Oxford `A1/A2` ou no topo da NGSL.
3. **Tier 3 (Expansão):** Restante da interseção (`B1/B2`) e cauda exclusiva de cada lista.

---

## 2. Banco de Dados (SQLite)

Arquivo único local (ex: `data/jane.db`). Conceito inicial das tabelas:

### Tabela `words`
- `id` (PK)
- `lemma` (texto único, ex: `run`, `water`)
- `in_oxford` (bool)
- `in_ngsl` (bool)
- `cefr_level` (`A1`, `A2`, `B1`, `B2`, null)
- `ngsl_rank` (int, null)
- `priority_score` (int/float para ordenação dos lotes)
- `batch_number` (int — lote ao qual pertence)
- `status` (`pending`, `generated`, `exported`, `mastered`)

### Tabela `cards` (relação 1:N com `words`)
- `id` (PK)
- `word_id` (FK → `words.id`)
- `difficulty` (`easy`, `medium`, `hard`)
- `sentence_en` (frase em inglês; pode guardar marcação da palavra-alvo ou texto puro + destaque)
- `sentence_pt` (tradução natural em PT-BR)
- `word_meaning_pt` (sentido específico na frase)
- `notes` (nota opcional curta)
- `char_count` (contagem de caracteres do texto em inglês para estimativa de HyperTTS)
- `created_at` (timestamp)

---

## 3. Fluxo com Mini CLI + Agente (Sem API paga)

Para não gastar turnos nem travar com 1 palavra por vez, o Mini CLI trabalha em **mini-lotes** (ex: 15 a 25 palavras por execução):

```text
[1. Seed]         Importa Oxford 3000 + NGSL para o SQLite e calcula prioridades/lotes.
     │
     ▼
[2. Next]         CLI: `jane next --batch 1 --limit 20`
                  Retorna JSON com as próximas 20 palavras pendentes
                  + resumo do vocabulário já liberado/dominado (para manter o i+1).
     │
     ▼
[3. Geração]      O Agente (usando a cota do plano no terminal) gera as frases,
                  traduções naturais, significados e dificuldades em JSON.
     │
     ▼
[4. Save]         CLI: `jane save --file batch_chunk.json`
                  Valida os dados, confere se a palavra-alvo está na frase,
                  calcula `char_count` e grava no SQLite.
     │
     ▼
[5. Export]       CLI: `jane export --batch 1`
                  Gera `exports/batch_01.tsv` pronto para o Anki
                  + exibe relatório de caracteres totais (estimativa HyperTTS).
     │
     ▼
[6. Anki + TTS]   Usuário importa o `.tsv` no Anki e roda o HyperTTS no lote.
```
