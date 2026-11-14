# 04 — Pesquisa: Integração com HyperTTS (`vocab.ai`) e Anki

Levantamento técnico sobre como o **HyperTTS** funciona com HTML, campos do Anki e multiplicadores de cota, para desenhar nosso `.tsv` e Note Type sem retrabalho.

---

## 1. Como o HyperTTS lida com Tags HTML

- Por padrão, antes de enviar o texto para o motor de TTS, o HyperTTS faz o *parse* do campo e **remove tags HTML automaticamente** (`<b>`, `<i>`, `<br>`, `<div>`, etc.).
- **Por que ainda vale separar os campos?**
  - Mesmo com a remoção automática, as boas práticas do HyperTTS recomendam manter o **campo de origem (Source)** o mais limpo possível (sem marcações extras, colchetes ou notas entre parênteses) e usar um **campo dedicado para o áudio (Target)** (ex: `Audio_Sentence`).
  - Separar `Sentence_Display` (com `<b>palavra</b>` para destaque visual) e `Sentence_Audio` (texto puro) elimina qualquer risco caso você use regras de regex ou troque de configuração no futuro.

---

## 2. Cota Mensal (250.000 chars) e Multiplicadores por Voz

Na assinatura HyperTTS Pro (`vocab.ai`), a cobrança **depende do provedor/voz** escolhido:

| Provedor / Voz | Multiplicador | Capacidade real com 250k chars/mês (~50 chars/frase) |
| :--- | :---: | :--- |
| **Padrão** (Microsoft Azure, Google, Amazon Polly — Inglês) | **1x** | ~5.000 frases/mês |
| **OpenAI Voices** | **2x** | ~2.500 frases/mês |
| **Naver TTS** | **6x** | ~830 frases/mês |
| **ElevenLabs** (via cota HyperTTS) | **15x** | ~333 frases/mês (~16.666 chars reais) |

> **Impacto no nosso projeto:**
> - Se você escolher **ElevenLabs (15x)**, um lote de **100 a 150 frases** (~5.000 a 7.500 caracteres reais) consome **75.000 a 112.500 caracteres da cota** — ou seja, cabe com folga na cota mensal, mas um lote de 300+ frases já estouraria!
> - Se usar **OpenAI (2x)** ou **Azure Neural (1x)**, você gera lotes inteiros gastando uma fração mínima da cota.
> - É possível acompanhar o saldo exato em `app.vocab.ai/languagetools/quota`.

---

## 3. Boas Práticas de Campos no Anki (Note Type)

Ao configurar o Note Type no Anki para receber nosso `.tsv`, a arquitetura recomendada pelo próprio HyperTTS é:

1. **Campo dedicado de Áudio (`Audio_Sentence`, `Audio_Word`):**
   - Nunca misture o `[sound:...]` dentro do campo de texto da frase.
   - Com um campo exclusivo para o som, se você quiser trocar de voz ou re-gerar um áudio no futuro, o HyperTTS sobrescreve apenas o campo de áudio sem risco de corromper ou duplicar o texto.
2. **Modo *Collection Audio* (não *Realtime*):**
   - Gerar os `.mp3` em lote na coleção (*Collection Audio*) garante que os áudios funcionem offline, no AnkiDroid/AnkiMobile e no AnkiWeb.
3. **Presets salvos:**
   - Configurar e salvar um **Preset** no HyperTTS (ex: `Jane-EN-Sentence`) para garantir que todos os lotes futuros usem exatamente a mesma voz, velocidade e campos.
4. **Regra de segurança antes de rodar no lote:**
   - Sempre testar o preset em **3 a 5 cards** antes de rodar no lote inteiro.
   - Fazer backup rápido (`Export Collection .colpkg`) antes de gerações em massa.

---

## 4. Estrutura sugerida para o `.tsv`

Com base nisso, as colunas do nosso `.tsv` de exportação ficam assim:

1. `Card_UID` *(chave única estável, ex: `jane_0001` — evita duplicatas ao re-importar)*
2. `Word` *(lema ou forma base, ex: `water`)*
3. `Sentence_Display` *(ex: `I need <b>water</b>.`)*
4. `Sentence_Audio` *(texto puro para o HyperTTS ler: `I need water.`)*
5. `Sentence_PT` *(tradução natural em PT-BR)*
6. `Word_Meaning_PT` *(sentido da palavra naquele contexto)*
7. `Difficulty` *(`easy`, `medium`, `hard`)*
8. `Batch` *(ex: `batch_01`)*
9. `Notes` *(nota gramatical/uso opcional)*
*(Os campos `Audio_Sentence` e `Audio_Word` ficam vazios na importação e são preenchidos pelo HyperTTS dentro do Anki.)*
