---
name: jane-expand-and-curate
description: Adiciona palavras ou expressões customizadas, cria sentidos extras (polissemia), corrige cards existentes e exporta atualizações seletivas para o Anki com segurança via Card_UID. Use quando o usuário quiser cadastrar vocabulário novo, melhorar um card ou exportar apenas cards alterados.
---

# Skill: Expansão e Curadoria do Deck (`jane-expand-and-curate`)

Fluxo para expandir o deck pessoal com vocabulário customizado e aplicar correções cirúrgicas em cards já importados no Anki — inclusive a partir de outros repositórios usando o comando global `jane`.

> **Workspace (`JANE_HOME` / `--home`):** Quando acionado fora do repositório do Jane, `jane` resolve automaticamente a base via `--home`, variável `JANE_HOME` ou raiz da instalação editável. Se `jane` não estiver instalado globalmente, use `python3 -m jane`.

## 1. Adicionar Palavras ou Expressões Customizadas

1. Cadastre um ou mais termos (suporta expressões compostas, phrasal verbs, hífens e apóstrofos):
   ```bash
   jane add "burn out" "deploy" "trade-off" --pos "phrasal verb" --cefr B1
   ```
   - Sem `--batch`, o Jane aloca automaticamente em um **novo lote** (`max_batch + 1`) sempre que o último lote já tiver palavras `exported` ou `mastered`, evitando contaminar lotes fechados; caso o último lote ainda esteja aberto (`pending`/`generated`), continua preenchendo até `--batch-size` (padrão `120`).
   - Use `--batch <N>` somente quando quiser forçar explicitamente um lote específico.
2. Inspecione o JSON retornado:
   - Confira `added` (lote atribuído a cada termo).
   - Confira `skipped_existing` (palavras que já existiam no banco não são sobrescritas).
3. Gere e salve os cards das palavras adicionadas seguindo as regras de `jane-generate-batches`:
   ```bash
   jane next --batch <N> --limit 30 --no-known
   jane save --file /tmp/custom_cards.json
   ```

## 2. Criar Sentidos Adicionais (Polissemia)

Para palavras já existentes em `words` que merecem um 2º ou 3º card (ex: `run` como "gerenciar"), basta salvar um card com `sense_index` maior (`2`, `3`, ...):

```bash
jane save --file - <<'EOF'
[
  {
    "lemma": "run",
    "sense_index": 2,
    "pos": "verb",
    "difficulty": "medium",
    "sentence_display": "She will <b>run</b> the new store.",
    "sentence_audio": "She will run the new store.",
    "sentence_pt": "Ela vai administrar a loja nova.",
    "word_meaning_pt": "administrar / gerenciar",
    "notes": "Outro sentido muito comum além de 'correr'."
  }
]
EOF
```

- Se a palavra já estiver como `exported` ou `mastered`, passe `--force` junto ao `jane save` para liberar a inclusão do novo sentido.

## 3. Corrigir ou Melhorar Cards Existentes

1. Salve a versão corrigida informando o mesmo `lemma` e `sense_index` com `--force`:
   ```bash
   jane save --file /tmp/fix_cards.json --force
   ```
2. O `jane save --force` preserva o `Card_UID`, atualiza `updated_at` e marca `exported_at = NULL`, permitindo captura automática por `--modified`.

## 4. Exportação Seletiva para Atualização no Anki

Escolha exatamente **um** seletor (mutuamente exclusivos) em `jane export`:

```bash
# Todos os cards nunca exportados ou alterados desde a última exportação
jane export --modified

# Cards específicos por Card_UID
jane export --uids jane_0001_01,jane_0042_01

# Todos os sentidos de uma ou mais palavras
jane export --words "run,burn out"

# Cards criados/atualizados a partir de uma data ou timestamp
jane export --since 2026-11-20
jane export --since 2026-11-20T14:30:00
```

- Quando `--out` não é informado nos modos seletivos, o arquivo é salvo em `<jane_home>/exports/update_<YYYYMMDD_HHMMSS>.tsv` com o cabeçalho Anki completo.
- Para lotes customizados inteiros novos, continue usando `jane export --batch <N>`.

## 5. Checklist Obrigatório ao Entregar o `.tsv` ao Usuário

Sempre informe ao usuário:

1. **Caminho do `.tsv` gerado** e lista de `card_uids` exportados.
2. **Importação segura no Anki:** orientar a importar escolhendo **Update existing notes when first field matches** (o campo `Card_UID` atualiza os cards existentes sem duplicar e sem perder histórico FSRS/SM-2).
3. **Alerta explícito de áudio (HyperTTS):**
   - **Se `Sentence_Audio` mudou** (ou se é um card/sentido novo): **alerte explicitamente** que será necessário regerar/gerar o áudio no HyperTTS para esses cards e informe a estimativa de caracteres (`hypertts_estimate`: `1x`, `2x`, `15x`).
   - **Se apenas `Sentence_PT`, `Word_Meaning_PT`, `Notes` ou `Difficulty` mudaram** (e `Sentence_Audio` permaneceu idêntico): informe que **não** é necessário gastar cota no HyperTTS.
