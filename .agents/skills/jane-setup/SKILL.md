---
name: jane-setup
description: Runbook de instalação, reconstrução do banco SQLite a partir dos TSVs, empacotamento global da CLI jane e configuração completa do Anki + HyperTTS. Use ao configurar o Jane em uma máquina nova, reinstalar a CLI ou reproduzir o deck do zero.
---

# Skill: Setup e Reprodutibilidade do Jane (`jane-setup`)

Runbook passo a passo para instalar a CLI `jane`, reconstruir o banco SQLite a partir dos TSVs versionados e configurar o Anki + HyperTTS.

## 1. Verificar Ambiente e Executar Testes

1. Confirme **Python 3.12+** (o Jane não possui dependências externas de runtime):
   ```bash
   python3 --version
   ```
2. Execute a suíte de testes na raiz do repositório:
   ```bash
   python3 -m unittest discover -s tests -v
   ```

## 2. Instalar o Comando Global `jane`

Instale em modo editável para ter o executável `jane` disponível em qualquer terminal:

```bash
uv tool install --editable .
# alternativa com pip:
# pip install -e .
```

Valide a instalação:

```bash
jane --version
```

*(Caso prefira não instalar globalmente, todos os comandos funcionam via `python3 -m jane <subcomando>` na raiz do repositório.)*

### Workspace (`JANE_HOME` / `--home`)

Por padrão, em instalação editável, o `jane` encontra automaticamente `data/`, `exports/` e `anki/` na raiz do repositório mesmo quando executado a partir de outro diretório. Para apontar para um workspace específico, use:

- Variável de ambiente: `export JANE_HOME=/caminho/para/jane`
- Ou flag por execução: `jane --home /caminho/para/jane status`

### (Opcional) Registrar Skills Globalmente sem Duplicar Arquivos

Para disponibilizar as skills do Jane em agentes abertos em outros projetos, adicione o caminho da pasta `.agents/skills` em `~/.gemini/config/skills.json` apontando diretamente para o repositório (ex: `~/projetos/jane/.agents/skills`) sem copiar arquivos.

## 3. Reconstruir `data/jane.db` (ou Iniciar do Zero)

`data/jane.db` não é versionado no Git; os arquivos em `exports/imported/batch_*.tsv` e `exports/batch_*.tsv` são a fonte de verdade.

- **Reconstruir o deck completo existente (recomendado):**
  ```bash
  jane rebuild
  jane status
  ```
  *(Use `jane rebuild --skip-seed` caso queira importar apenas os TSVs sem ler `data/raw/`.)*

- **Ou começar um deck vazio apenas com a lista base Oxford 3000 + NGSL:**
  ```bash
  jane seed
  jane status
  ```

## 4. Gerar e Importar o Note Type no Anki

1. Gere (ou regere) o pacote do Note Type `Jane Vocab`:
   ```bash
   jane template
   ```
   Saída padrão: `anki/jane_vocab_template.apkg` (ou `--out <caminho>`).
2. No **Anki**, importe `anki/jane_vocab_template.apkg` (File → Import). Ele instala o Note Type `Jane Vocab` com os 10 campos (incluindo `Card_UID` e `Audio_Sentence`) e 1 card de exemplo que pode ser apagado após importar.
3. Importe os lotes `.tsv` desejados em `exports/imported/` (ou `exports/`), mantendo a opção de atualizar notas existentes pelo primeiro campo (`Card_UID`).

## 5. Configurar Ordem de Exibição no Anki e HyperTTS

### Ordem de Estudo no Anki (Deck Options → Display Order)

Configure nas opções do deck para seguir a ordem pedagógica (`i+1`) dos lotes sem precisar suspender cards:

- **New card gather order:** `Deck` / `Ascending position`
- **New card sort order:** `Order gathered`

### Perfil do HyperTTS

Consulte [docs/04-hypertts-e-anki.md](../../../docs/04-hypertts-e-anki.md) para detalhes completos de presets e segurança:

- **Source Field:** `Sentence_Audio` (texto puro, sem HTML)
- **Target Field:** `Audio_Sentence` (campo dedicado para `[sound:...]`, modo *Collection Audio*)
- **Multiplicadores de cota (250k chars/mês no HyperTTS Pro):**
  - Azure / Google / Polly: **1x**
  - OpenAI Voices: **2x**
  - ElevenLabs: **15x**
- Sempre teste o preset em 3–5 cards e faça backup da coleção antes de gerar áudio em lote.
