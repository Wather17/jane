# 01 — Visão e Princípios Pedagógicos

> **Contexto do estudante:** Iniciante absoluto (A0/A1). O sistema precisa respeitar uma curva de aprendizado real, evitando que o deck vire uma parede impossível nas primeiras semanas.

---

## 1. Por que aprender por Frequência + Frases (Contexto)

- As **~2.800 a 3.000 palavras** mais frequentes cobrem cerca de **85% a 92%** do inglês cotidiano.
- Aprender palavra solta gera tradução mecânica e trava na leitura/escuta real.
- Aprender em **frase curta e natural** ensina *collocations* (palavras que andam juntas), gramática implícita e pronúncia conectada (*connected speech*).

---

## 2. Regras de Ouro de Aprendizagem

### Regra do `i+1` (Compreensibilidade)
Cada card deve introduzir **apenas 1 conceito/palavra nova** (a palavra-alvo), usando no restante da frase apenas palavras que o estudante já viu nos lotes anteriores ou vocabulário ultra-básico já coberto.
- *Erro a evitar:* Gerar uma frase para a palavra #50 contendo 3 palavras do nível #2000. O aluno erra o card pelas palavras ao redor, não pela palavra-alvo.

### Ordem Pedagógica dos Lotes Iniciais
Nos primeiros lotes, palavras estruturais (**pronomes, verbos auxiliares, preposições e conectores básicos** como *I, you, is, are, have, do, can, not, in, on, to, the, a, what, where*) precisam vir **primeiro**. Sem elas, não é possível formar frases naturais respeitando o `i+1`.

### Dificuldade (Fácil / Média / Difícil) sem quebrar o `i+1`
Dentro de um lote, podemos variar o nível das frases sem usar palavras raras:
- **Fácil:** Frase bem curta (4–6 palavras), presente simples, direta. *(Ex: "I need water.")*
- **Média:** Frase do cotidiano (7–10 palavras), negativa, pergunta ou tempo verbal simples. *(Ex: "Do you want to drink some water?")*
- **Difícil (Desafio):** Usa **vocabulário já conhecido**, mas em estrutura um pouco mais longa, expressão idiomática comum ou sentido secundário da palavra. *(Ex: "I'm going to water the plants later.")*

### Polissemia (1 palavra, vários sentidos)
Palavras do topo da lista (ex: *get, make, take, put, run, set*) têm muitos significados diferentes.
- Para palavras concretas (ex: *window, umbrella*), **1 card** resolve.
- Para palavras altamente polissêmicas, o banco deve permitir **mais de 1 card por palavra** (ex: 2 ou 3 sentidos principais), em vez de forçar "1 palavra = 1 frase".

---

## 3. Design do Card no Anki

- **Frente:**
  - Frase em inglês com a palavra-alvo destacada (ex: negrito).
  - Áudio da frase (gerado no Anki via HyperTTS).
  - *Sem tradução na frente* (treinar compreensão direta, não tradução automática).
- **Verso:**
  - Tradução natural da frase em PT-BR (não literal).
  - Significado específico da palavra-alvo naquele contexto.
  - Nota rápida de uso/gramática (apenas quando ajudar, sem textão).
  - Áudio isolado da palavra (opcional, avaliando impacto na cota do HyperTTS).

---

## 4. Estratégia de Lotes (Ritmo + Cota de TTS)

- Em vez de importar 3.000 cards de uma vez (fadiga e abandono), o banco é dividido em **lotes menores** (ex: **100 a 150 palavras** por lote, ou **250** dependendo do consumo de caracteres).
- Só avançamos para gerar/importar o próximo lote quando o lote atual estiver dominado no Anki.
- **Motivo extra para lotes menores:** O **HyperTTS (`vocab.ai`)** possui cota mensal de **250.000 caracteres**, e a cobrança não é 1:1 (depende do motor/voz escolhida e se há áudio para palavra + frase). Lotes menores garantem margem de segurança para nunca estourar a cota no meio de um lote.
