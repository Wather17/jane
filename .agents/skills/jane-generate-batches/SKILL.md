---
name: jane-generate-batches
description: Gera novos lotes de cards de vocabulário em inglês no Jane (status, next, redação pedagógica i+1, validação/save em chunks e exportação TSV para Anki/HyperTTS). Use quando o usuário pedir para gerar cards pendentes, preencher um lote ou continuar a construção do deck.
---

# Skill: Geração de Lotes de Vocabulário (`jane-generate-batches`)

Fluxo operacional para transformar palavras `pending` de um lote do Jane em cards validados no SQLite e exportados em `.tsv` prontos para o Anki + HyperTTS.

> **Comando CLI:** Use `jane <subcomando>` quando instalado globalmente (`uv tool install --editable .`), ou o fallback `python3 -m jane <subcomando>` na raiz do repositório.

## 1. Consultar Progresso e Selecionar Lote

1. Verifique o estado atual do banco e identifique o próximo lote com palavras `pending`:
   ```bash
   jane status
   ```
2. Busque um mini-lote de palavras pendentes (recomendado `20` a `30` por chunk para manter alta qualidade pedagógica):
   ```bash
   jane next --batch <N> --limit 30
   ```
   - Nos lotes avançados (quando `known_words` já for muito grande), use `--no-known` para economizar contexto e manter a regra `i+1` usando vocabulário cotidiano básico:
     ```bash
     jane next --batch <N> --limit 30 --no-known
     ```

## 2. Regras Pedagógicas e Técnicas de Redação

Siga rigorosamente [docs/01-visao-e-pedagogia.md](../../../docs/01-visao-e-pedagogia.md) e [docs/03-edge-cases-e-regras.md](../../../docs/03-edge-cases-e-regras.md):

- **Regra `i+1`:** Introduza apenas a palavra-alvo como conceito novo; use vocabulário já conhecido ou estrutural básico no restante da frase.
- **Tamanho da frase:** Entre **3 e 18 palavras** (ideal: 5–12 palavras para economizar cota do HyperTTS e facilitar revisão rápida no Anki).
- **`sentence_display` vs `sentence_audio`:**
  - `sentence_display` deve destacar a palavra-alvo (ou sua flexão na frase) com `<b>...</b>`.
  - `sentence_audio` deve ser texto puro (zero tags HTML) e **idêntico** a `sentence_display` sem as tags.
- **PT-BR natural:** `sentence_pt` deve soar natural em português brasileiro (nunca tradução robótica literal); `word_meaning_pt` traz o significado específico da palavra naquele contexto.
- **`difficulty`:** Apenas `easy`, `medium` ou `hard`.
- **`notes`:** Opcional e curta (somente quando acrescentar dica real de uso, pronúncia ou falso cognato).
- **Edge cases conhecidos:**
  - **Lemas numerados** (ex: `wind 1`, `can 2`): mantenha exatamente o `lemma` do banco no JSON, mas use a palavra natural sem o número na frase (`<b>wind</b>`, `<b>can</b>`).
  - **Abreviações / prefixos** (ex: `etc.`, `un-`): crie uma frase cotidiana clara explicando o uso em `notes`.
  - **Flexões / irregulares** (ex: `go` → `<b>went</b>`): destaque a forma flexionada usada na frase com `<b>...</b>`.

## 3. Salvar em Chunks (Evitando Problemas de Quoting)

Prefira salvar via arquivo temporário ou `stdin` (`--file -`) em vez de strings inline complexas no shell (evita quebra com apóstrofos como `don't`, `it's`).

Exemplo de payload JSON válido:

```json
[
  {
    "lemma": "water",
    "sense_index": 1,
    "pos": "noun",
    "difficulty": "easy",
    "sentence_display": "I drink <b>water</b> every morning.",
    "sentence_audio": "I drink water every morning.",
    "sentence_pt": "Eu bebo água toda manhã.",
    "word_meaning_pt": "água",
    "notes": ""
  }
]
```

Salve o chunk e valide a saída:

```bash
jane save --file /tmp/jane_chunk.json
# ou via stdin:
jane save --file - <<'EOF'
[ ... ]
EOF
```

Repita `jane next` → `jane save` até `pending == 0` no lote `<N>`.

## 4. Exportar Lote e Reportar Cota HyperTTS

1. Exporte o lote completo para `.tsv`:
   ```bash
   jane export --batch <N>
   ```
   Saída padrão: `<jane_home>/exports/batch_<NN>.tsv` (com as 4 diretivas Anki e `Card_UID` na 1ª coluna).
2. Informe ao usuário:
   - Caminho do arquivo `.tsv` gerado e quantidade de cards.
   - Estimativa de cota HyperTTS retornada no JSON (`1x_azure_google`, `2x_openai`, `15x_elevenlabs`).
3. Após o usuário confirmar a importação no Anki, mova o arquivo para `exports/imported/` para manter `exports/` limpo e versionar o estado importado:
   ```bash
   mv exports/batch_<NN>.tsv exports/imported/
   ```
4. Quando o usuário concluir o estudo do lote no Anki, marque como dominado:
   ```bash
   jane master --batch <N>
   ```
