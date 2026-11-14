# Jane — English Vocabulary Builder for Anki

Projeto pessoal para construir um deck de inglês estruturado (~3.000+ palavras mais frequentes), com curadoria pedagógica para iniciantes, geração controlada de frases em contexto via agente CLI e exportação em `.tsv` para o Anki (com áudio gerado via **HyperTTS / vocab.ai**).

## Documentação (Planejamento & Decisões)

Antes de escrever código, estamos consolidando as decisões pedagógicas, arquiteturais e *edge cases* na pasta `docs/`:

1. [Visão e Princípios Pedagógicos](docs/01-visao-e-pedagogia.md) — Como o método funciona para quem está começando do zero, regra do `i+1`, estrutura dos cards e controle de lotes.
2. [Arquitetura e Fluxo de Trabalho](docs/02-arquitetura-e-fluxo.md) — SQLite, cruzamento Oxford 3000 + NGSL, Mini CLI operado por agente em mini-lotes e exportação `.tsv` + HyperTTS.
3. [Edge Cases e Regras (O que fazer / Não fazer)](docs/03-edge-cases-e-regras.md) — Armadilhas mapeadas, validações obrigatórias e margem de segurança para a cota de TTS.
4. [Pesquisa: HyperTTS e Anki](docs/04-hypertts-e-anki.md) — Como o HyperTTS trata HTML, multiplicadores de cota (1x, 2x, 15x), boas práticas de campos e formato final do `.tsv`.
5. [Schema do SQLite, Priorização e Mini CLI](docs/05-schema-e-cli.md) — Modelo de dados final (`words` e `cards`), cálculo de tiers/lotes e contrato dos comandos `seed`, `next`, `save`, `export`.
6. [Lições do Teste de 50 Palavras](docs/06-melhorias-e-licoes-teste-50.md) — Resultados reais do `test_50.tsv`, consumo medido de caracteres e melhorias mapeadas.
