# 06 — Lições do Teste de 50 Palavras e Melhorias no Fluxo

Registro prático da execução completa do fluxo (`seed --sample 50` → `next` → `save` → `export`) no banco sandbox `data/test_50.db`, gerando `exports/test_50.tsv`.

---

## 1. Resultados Medidos no Teste (`exports/test_50.tsv`)

- **Total de palavras/cards:** 50
- **Caracteres reais (`Sentence_Audio`):** **1.890** (~37,8 caracteres/frase em média)
- **Estimativa de consumo no HyperTTS:**
  - **1x (Azure / Google / Polly):** 1.890 chars
  - **2x (OpenAI Voices):** 3.780 chars
  - **15x (ElevenLabs):** 28.350 chars *(~11,3% da cota mensal de 250k)*

---

## 2. Problemas Encontrados e Pontos de Atenção

### 1) `pos` parcial no `oxford_cefr.json`
- **O que aconteceu:** Palavras como `fly`, `pass`, `lack` e `repeat` vieram marcadas apenas como `noun` no `oxford_cefr.json`, mesmo o uso como `verb` sendo tão ou mais comum para iniciantes.
- **Solução adotada:** O `pos` da tabela `words` funciona apenas como *hint*. No `save`, o card pode registrar o `pos` real da frase gerada (ex: `verb`).

### 2) Expressões compostas no `oxford_3000.json`
- **O que aconteceu:** Apareceu `"high school"` (duas palavras) no lote de teste.
- **Comportamento:** A validação do `save` funcionou normalmente porque compara `sentence_display` sem HTML contra `sentence_audio` e aceita destaques compostos (`<b>high school</b>`).

### 3) Cabeçalho do `.tsv` ao importar no Anki
- **Ponto de atenção:** Por padrão, o `export` inclui a linha de cabeçalho (`Card_UID	Word	...`). Ao importar no Anki, lembre-se de conferir se o Anki ignorou a primeira linha (ou use `--no-header` no `export`).

### 4) Suporte a `stdin` no `save` (`--file -`)
- **Melhoria aplicada:** Adicionado suporte a `--file -` no comando `save` para evitar criar arquivos temporários quando o agente enviar o JSON diretamente via pipe.

---

## 3. Melhorias Futuras (Backlog pós-teste no Anki)

1. **`--no-known` no `next`:** Quando o banco principal passar do Lote 15 (~1.800+ palavras), a lista `known_words` no JSON do `next` vai crescer bastante; adicionar `--no-known` ou `--known-limit` mantém o output enxuto.
2. **Estabilidade do `card_uid`:** Como `card_uid` usa `words.id`, nunca apague e recrie `data/jane.db` do zero após começar a importar no Anki — use `seed` de forma incremental/idempotente.
3. **Verificação pós-teste no HyperTTS:** Após importar `exports/test_50.tsv` no Anki e rodar o HyperTTS, validar:
   - Se `Sentence_Display` renderiza o negrito corretamente.
   - Se o HyperTTS lê `Sentence_Audio` de forma natural (velocidade e entonação) e grava em `Audio_Sentence`.
   - Quanto de cota real foi descontado em `app.vocab.ai/languagetools/quota`.
