# 03 — Edge Cases e Regras (O que fazer / Não fazer)

Checklist vivo de problemas potenciais e decisões para evitar retrabalho no meio do projeto.

---

## 1. Edge Cases Linguísticos e Pedagógicos

### Flexões vs. Lemas (ex: `run` vs `running`, `go` vs `went`)
- **Problema:** O banco guarda o lema (`go`), mas na frase natural pode aparecer `went` ou `going`. Se a validação buscar apenas a string exata `go`, vai rejeitar frases válidas.
- **Regra:** A validação no `save` deve aceitar flexões conhecidas ou usar um campo/marcação explícita na frase (ex: `I **went** to work.` ou `I <b>went</b> to work.`), garantindo que o destaque visual no Anki funcione mesmo com verbos irregulares.

### Palavras Homógrafas (mesma escrita, classes diferentes)
- **Problema:** `water` (substantivo: água) vs `water` (verbo: regar); `book` (livro) vs `book` (reservar).
- **Regra:** Se a lista de origem trouxer a classe gramatical (*POS tag* — noun, verb, adj), preservar isso no banco. Se não trouxer, deixar o modelo gerar o sentido mais comum primeiro no card principal.

### Tradução literal vs. Tradução natural
- **Problema:** Traduções robóticas ao pé da letra confundem quem está começando (ex: *"How old are you?"* → *"Quão velho você é?"*).
- **Regra:** O prompt/instrução do agente no passo de geração deve exigir **PT-BR natural e equivalente** (*"Quantos anos você tem?"*).

### Destaque da palavra-alvo na frase
- **Problema:** No TSV para o Anki, o destaque (ex: `<b>palavra</b>`) não pode atrapalhar o **HyperTTS** na hora de ler a frase.
- **Resultado da pesquisa (ver [04-hypertts-e-anki.md](04-hypertts-e-anki.md)):** O HyperTTS remove tags HTML automaticamente por padrão antes de enviar ao TTS. Mesmo assim, manter **duas colunas** (`Sentence_Display` com `<b>...</b>` e `Sentence_Audio` em texto puro) + um campo dedicado `Audio_Sentence` no Anki continua sendo a prática mais segura para evitar problemas com regex ou re-geração de áudio.

---

## 2. Edge Cases de Infraestrutura e HyperTTS

### Cota do HyperTTS (250.000 caracteres/mês, cobrança não 1:1)
- **Problema:** Dependendo da voz/serviço dentro do HyperTTS, 1 caractere de texto pode consumir mais de 1 caractere da cota, e re-gerar áudio consome novamente.
- **Regras:**
  1. Manter o campo `char_count` no SQLite e somar o total antes de exportar cada lote.
  2. Começar com lotes de **100 a 150 palavras** (em vez de 250 direto) para medir na prática quanto de cota real o HyperTTS consome por lote no seu plano/voz escolhida.
  3. Gerar áudio **apenas da frase** inicialmente (ou testar o custo antes de decidir gerar áudio da palavra isolada também).
  4. Nunca colocar HTML no campo que o HyperTTS vai ler.

### Exportação Idempotente (Não duplicar cards no Anki)
- **Problema:** Se você exportar o Lote 1, importar no Anki, e depois precisar corrigir 2 frases e re-exportar, o Anki pode duplicar os cards se não tiver um ID único.
- **Regra:** A **primeira coluna** do `.tsv` deve ser sempre um `card_uid` único e estável (ex: `jane_0001`, `jane_0002`), mapeado no primeiro campo do Note Type no Anki. Assim, re-importar um `.tsv` atualizado **atualiza** os cards existentes em vez de duplicar (e preserva seu histórico de revisão e áudios dos cards que não mudaram).

### Validação de Dados no `save`
- Não aceitar frases vazias, traduções vazias ou duplicadas exatas.
- Verificar se a frase tem tamanho razoável (ex: 3 a 18 palavras — frases gigantes são ruins para Anki).
- Impedir que uma palavra marcada como `generated`/`exported` seja sobrescrita acidentalmente sem flag explícita (`--force`).

---

## 3. O que NÃO fazer (Decisões para manter o foco)

- **Não** começar integrando API paga de LLM: usar o fluxo local CLI + agente.
- **Não** tentar gerar áudio via código agora, já que o HyperTTS resolve isso dentro do Anki.
- **Não** gerar as 3.000 frases de uma vez antes de testar o Lote 1 no Anki por pelo menos 1 semana (o uso real vai revelar ajustes no tamanho da frase e no formato do card).
- **Não** construir interface web/GUI agora: CLI + SQLite + TSV é mais rápido, versionável e fácil de evoluir.
