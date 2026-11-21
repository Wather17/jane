# 07 — Desenvolvimento, CI, Releases e Fluxo de Engenharia

Guia operacional de engenharia do repositório `Wather17/jane` para contribuidores humanos e agentes de IA.

---

## 1. Workflows do GitHub Actions

O repositório mantém dois workflows enxutos usando apenas actions oficiais (`actions/checkout@v4`, `actions/setup-python@v5`) e Python 3.12:

### CI Contínua (`.github/workflows/ci.yml`)
- **Triggers:** `push` na branch `main` e `pull_request` direcionado a `main`.
- **Permissões:** `contents: read` (menor privilégio).
- **Validação:** Executa `python3 -m unittest discover -s tests -v` sem dependências externas, incluindo o teste de sincronia entre `jane.__version__` e `pyproject.toml`.

### GitHub Release por Tag (`.github/workflows/release.yml`)
- **Trigger:** Exclusivamente `push` de tags semânticas no padrão `v*.*.*` (ex: `v0.2.0`, `v1.0.0`).
- **Permissões:** `contents: write` (usa apenas `secrets.GITHUB_TOKEN` nativo).
- **Pipeline de publicação:**
  1. **Validação de versão:** Confere via `tomllib` (stdlib) que a tag (`vX.Y.Z` sem o prefixo `v`) coincide exatamente com `jane.__version__` (`jane/__init__.py`) e `project.version` (`pyproject.toml`). Qualquer divergência aborta o workflow antes do build.
  2. **Gate de testes:** Executa `python3 -m unittest discover -s tests -v`.
  3. **Build de artefatos:** Gera wheel (`dist/*.whl`) e sdist (`dist/*.tar.gz`) com `python3 -m build`, além do template standalone do Anki em `dist/jane_vocab_template.apkg` via `python3 -m jane template --out dist/jane_vocab_template.apkg`.
  4. **Publicação:** Cria a GitHub Release via `gh release create "$GITHUB_REF_NAME" ... --generate-notes --title "$GITHUB_REF_NAME"` anexando `.whl`, `.tar.gz` e `jane_vocab_template.apkg`.

---

## 2. Política de Versionamento e Passo a Passo de Release

O projeto segue **Semantic Versioning (SemVer: `MAJOR.MINOR.PATCH`)**.

### Por que não usamos auto-release a cada merge?
O repositório recebe commits frequentes de conteúdo de vocabulário (como `feat(content): add batch ...`) e ajustes operacionais. Ferramentas de auto-release a cada merge na `main` gerariam ruído excessivo de versões e releases vazias de mudança de CLI. O disparo manual por tag `v*.*.*` garante controle explícito de quando consolidar uma versão estável.

### Como publicar uma nova versão

1. Atualize a versão nos dois arquivos (mantendo ambos idênticos):
   - `jane/__init__.py` (`__version__ = "X.Y.Z"`)
   - `pyproject.toml` (`version = "X.Y.Z"`)
2. Valide localmente os testes e a sincronia de versão:
   ```bash
   python3 -m unittest discover -s tests -v
   ```
3. Integre a alteração na branch `main` (via PR com CI verde).
4. Na `main` atualizada, crie e publique a tag semântica:
   ```bash
   git switch main && git pull --ff-only
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. O workflow `.github/workflows/release.yml` executará automaticamente a checagem de versão, os testes, o build e publicará a GitHub Release com os artefatos `.whl`, `.tar.gz` e `jane_vocab_template.apkg`.

### Instalação a partir de uma tag publicada

```bash
uv tool install git+https://github.com/Wather17/jane@vX.Y.Z
```

---

## 3. Convenções de Engenharia (Humanos e Agentes de IA)

### Branches e Pull Requests
- `main` é a branch de integração.
- Trabalhe em uma issue por branch no padrão `issue/<numero>-<slug>` a partir de `main`.
- Todo PR deve referenciar a issue com `Resolves #<numero>` e só deve ser mergeado após a CI (`gh pr checks --watch`) ficar verde.

### Conventional Commits
Use mensagens curtas e descritivas:
- `feat(<escopo>): ...` — nova funcionalidade na CLI ou novos lotes de conteúdo (`feat(content): ...`).
- `fix(<escopo>): ...` — correção de bug.
- `refactor(<escopo>): ...` — refatoração sem mudança de contrato.
- `test(<escopo>): ...` — adição ou melhoria de testes.
- `docs(<escopo>): ...` — documentação e skills operacionais.
- `chore(<escopo>): ...` — CI, empacotamento, manutenção de exports/infra.

### Labels e Sincronização de Issues
O GitHub é a fonte de verdade para o backlog. A pasta local `issues/` (ignorada pelo Git) funciona apenas como cache sincronizado sob demanda:

```bash
./scripts/sync-issues.sh
```

Convenção de labels:
- **Estado:** `status:ready`, `status:in-progress`, `status:blocked`, `status:needs-refinement`
- **Prioridade:** `priority:critical`, `priority:high`, `priority:medium`, `priority:low`
- **Área:** `area:cli`, `area:infra`, `area:skills`

### Política de Fonte de Verdade do Banco SQLite
- `data/jane.db` é **ignorado pelo Git** (`.gitignore`) para evitar binários no histórico e conflitos de merge.
- Os arquivos `.tsv` versionados em `exports/imported/batch_*.tsv` e `exports/batch_*.tsv` (junto com `data/raw/`) são a **fonte de verdade reproduzível**.
- Em qualquer máquina nova ou clone limpo, recrie o banco de forma determinística e idempotente com:
  ```bash
  jane rebuild
  ```
