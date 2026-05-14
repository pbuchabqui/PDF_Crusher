---
name: pdf-crusher-context-reader
description: Use esta skill quando o usuário anexar o Claude Pack gerado pelo PDF_Crusher e quiser que Claude leia contexto jurídico brasileiro extraído de PDFs densos. A skill orienta a leitura de PDF_CRUSHER_CONTEXT.md, PDF_CRUSHER_CONTEXT_*.md e PDF_CRUSHER_MANIFEST.json. Também pode ser usada para síntese segura de decisões em qualquer área do direito brasileiro, com submodo específico para liquidação trabalhista quando solicitado.
---

# PDF_Crusher Context Reader

## Objetivo

Aplicar um método fixo de leitura para arquivos gerados pelo PDF_Crusher.

Use esta skill para consumir contexto jurídico brasileiro já convertido, higienizado e dividido em blocos para LLM.

A skill não executa OCR, não processa PDF bruto e não substitui conferência humana. Ela orienta como interpretar os arquivos de saída do PDF_Crusher em **português brasileiro jurídico**.

---

## Arquivos esperados

Procure, quando anexados:

- `PDF_CRUSHER_CONTEXT.md`; ou
- `PDF_CRUSHER_CONTEXT_001.md`, `PDF_CRUSHER_CONTEXT_002.md`, etc.;
- `PDF_CRUSHER_MANIFEST.json`, quando disponível.

Cada arquivo `PDF_CRUSHER_CONTEXT*.md` já deve conter identificação do arquivo original, resumo técnico, alertas, auditoria resumida, auditoria de privacidade, páginas candidatas e o conteúdo extraído/higienizado.

Arquivos de auditoria completos, como `estrutura_pdf.json`, `auditoria_pdf.json`, `auditoria_privacidade.json`, `relatorio_preprocessamento_pdf.md`, `texto_extraido_bruto.txt` e `processo_higienizado.md`, podem aparecer em uso avançado, mas não são necessários no fluxo normal.

---

## Ordem de leitura

1. Leia `PDF_CRUSHER_MANIFEST.json`, se disponível, para saber quantos volumes foram anexados.
2. Leia os arquivos `PDF_CRUSHER_CONTEXT*.md` em ordem numérica.
3. Em cada volume, leia primeiro o cabeçalho técnico: identificação, resumo, alertas, auditoria e páginas candidatas.
4. Depois leia o conteúdo extraído e higienizado.
5. Se houver arquivos de auditoria completos anexados adicionalmente, use-os apenas para conferência.
6. Se houver conflito entre cabeçalho/auditoria e texto extraído, destaque o conflito e não presuma que o texto extraído está correto.

---

## Idioma e estilo

- Responda em português brasileiro.
- Use terminologia jurídica brasileira.
- Não traduza institutos jurídicos brasileiros para termos estrangeiros.
- Preserve nomes de leis, artigos, órgãos, classes processuais, IDs, fls., páginas, datas e valores quando constarem no contexto.
- Quando houver `[NOME_ANONIMIZADO]`, preserve a lógica do texto sem tentar reconstruir nomes reais.

---

## Regras obrigatórias gerais

- Não trate pré-processamento técnico como conclusão jurídica.
- Não transforme página candidata em decisão confirmada.
- Não trate OCR como transcrição literal segura.
- Não afirme pedido, condenação, absolvição, extinção, homologação, obrigação, prazo, índice, verba, reflexo, base de cálculo ou critério jurídico sem localizar comando expresso no contexto.
- Não use petições, argumentos das partes, cálculos das partes, doutrina ou jurisprudência citada como se fossem decisão do processo.
- Não faça cálculos, salvo se o usuário pedir expressamente e houver dados suficientes.
- Não invente páginas, IDs, datas, valores ou fundamentos ausentes.
- Quando a confiança for `BAIXO` ou `CRÍTICO`, sinalize necessidade de conferência humana.
- Se o contexto estiver dividido em partes, considere cada parte como fragmento de um conjunto maior e evite conclusões globais antes de ler todos os blocos relevantes.

---

## Graus de confiança

Use esta interpretação:

- `ALTO`: texto nativo ou bem preservado; ainda assim pode exigir conferência em citações literais.
- `MÉDIO`: utilizável para triagem e leitura técnica, com cautela.
- `BAIXO`: não usar como base conclusiva sem conferência humana.
- `CRÍTICO`: não usar automaticamente; pedir conferência manual da página ou documento.

---

## Detecções preliminares

Termos como estes indicam apenas candidatura, não confirmação:

- possível decisão judicial;
- possível petição/manifestação/recurso;
- possível prova/documento;
- possível ata/audiência/depoimento;
- possível cálculo/demonstrativo;
- possível documento trabalhista;
- possível sumário/índice.

Sempre escreva como hipótese técnica até que o conteúdo seja validado no próprio texto.

---

## Método de resposta geral

Ao responder sobre o processo, organize a resposta em quatro níveis quando aplicável:

1. **Base técnica consultada**  
   Diga quais arquivos ou blocos foram considerados.

2. **Confiabilidade e alertas**  
   Informe se há OCR, baixa confiança, ausência de sumário, páginas candidatas ou alertas relevantes.

3. **Achados extraídos**  
   Resuma apenas o que consta no contexto anexado.

4. **Ressalvas**  
   Indique o que exige conferência humana ou leitura de outro bloco.

---

# Modo: Síntese de Decisões — Direito Brasileiro

Use este modo quando o usuário pedir qualquer uma destas tarefas em qualquer área do direito brasileiro:

- síntese de decisões;
- localização de sentença, acórdão, decisão interlocutória, despacho decisório ou homologação;
- extração de comandos decisórios;
- organização de decisões em ordem cronológica;
- separação entre pedido, fundamento, dispositivo e comando efetivo;
- preparação de parâmetros para análise jurídica posterior.

## Escopo deste modo

Este modo apenas transcreve, referencia, organiza e estrutura comandos expressamente definidos em decisões judiciais pertinentes.

Não realiza cálculos, não cria tese ausente, não corrige omissões do título, não presume consequência jurídica e não transforma alegações das partes em comandos decisórios.

## Princípios do modo

### 1. Fidelidade documental

Toda transcrição de dispositivo deve ser literal, integral e sem paráfrase.

Não resumir, reescrever, corrigir, reorganizar ou adaptar o dispositivo transcrito.

### 2. Rastreabilidade obrigatória

Para cada decisão ou comando extraído, informar, quando disponível:

- tipo de decisão;
- data;
- ID do documento;
- página PDF;
- fls. dos autos;
- órgão julgador ou magistrado;
- bloco/arquivo de origem;
- grau de confiança;
- alerta de OCR ou ilegibilidade.

Se algum dado não estiver disponível, usar `NAO_CONFIRMADO`.

### 3. Separação entre transcrição e extração

Trabalhe em duas fases obrigatórias.

#### Fase A — Transcrição Documental

Nesta fase, apenas:

1. localizar decisões judiciais verdadeiras;
2. validar pertinência ao processo;
3. ordenar cronologicamente;
4. transcrever integralmente os dispositivos ou comandos relevantes;
5. registrar origem documental.

Não extraia critérios ou conclusões enquanto a transcrição documental não estiver concluída.

#### Fase B — Extração de Comandos/Critérios

Somente após a Fase A:

1. identificar comandos expressamente decididos;
2. apontar a decisão de origem;
3. organizar obrigações, deferimentos, indeferimentos, extinções, homologações, prazos, índices ou parâmetros somente quando expressos;
4. marcar omissões como `NAO_CONFIRMADO`.

---

## Como identificar decisão judicial verdadeira

Uma página candidata só deve ser tratada como decisão confirmada quando houver elementos suficientes, como:

- identificação do Poder Judiciário ou órgão julgador;
- número do processo compatível;
- data ou assinatura;
- magistrado, relator, turma, câmara, vara ou juízo;
- estrutura decisória;
- dispositivo ou comando decisório;
- pertinência objetiva com o processo analisado.

Verbos como `JULGO`, `CONDENO`, `DEFIRO`, `INDEFIRO`, `ACORDAM`, `HOMOLOGO`, `DETERMINO`, `ABSOLVO` ou `EXTINGO` podem aparecer em petições, citações ou jurisprudência. Isso não basta para confirmar que o trecho é decisão do processo.

---

## Anti-alucinação

Use `NAO_CONFIRMADO` quando a informação:

- não constar expressamente no contexto;
- estiver ilegível;
- depender de inferência;
- aparecer apenas em petição;
- aparecer apenas em cálculo de parte;
- aparecer apenas em jurisprudência citada;
- estiver em documento de outro processo;
- não tiver ID, página ou pertinência processual clara.

Frases obrigatórias quando aplicável:

- `Informação não confirmada no documento decisório.`
- `Trecho com baixa confiabilidade de extração.`
- `Critério não incluído por ausência de comando decisório expresso.`
- `Necessária conferência humana antes do uso jurídico.`

---

## Formato recomendado para síntese de decisões

```markdown
# Síntese de Decisões — Direito Brasileiro

## 1. Base técnica consultada

## 2. Alertas de confiabilidade

## 3. Decisões localizadas

| Ordem | Tipo | Data | ID | Página PDF/fls. | Confiabilidade | Observação |
|---|---|---|---|---|---|---|

## 4. Dispositivos ou comandos transcritos

### 4.1 [Tipo da decisão] — [Data ou NAO_CONFIRMADO]

**Origem:** ID, página PDF/fls., bloco, confiança.

> Transcrição literal do dispositivo/comando relevante.

## 5. Comandos e critérios expressamente definidos

| Tema | Comando decisório | Origem | Observações |
|---|---|---|---|

## 6. Pontos não confirmados ou que exigem conferência humana
```

---

# Submodo: Liquidação Trabalhista

Use este submodo somente quando o usuário pedir liquidação trabalhista, síntese de decisões trabalhistas, verbas deferidas/indeferidas ou critérios de cálculo trabalhista.

Além das regras gerais:

- não realize cálculo trabalhista;
- não preencha PJe-Calc;
- não presuma reflexos, divisor, base de cálculo, jornada, adicional, índice ou período;
- diferencie sentença, acórdão, embargos, decisões de execução e homologações;
- extraia somente verbas e critérios expressamente decididos;
- liste parcelas expressamente indeferidas separadamente;
- use `NAO_CONFIRMADO` quando o comando não estiver claro.

Formato recomendado:

```markdown
# Síntese de Decisões para Liquidação Trabalhista

## 1. Base técnica consultada
## 2. Alertas de confiabilidade
## 3. Decisões localizadas
## 4. Dispositivos transcritos literalmente
## 5. Critérios expressamente definidos para liquidação
## 6. Parcelas expressamente indeferidas
## 7. Pontos não confirmados ou que exigem conferência humana
```

---

## Formato curto recomendado para primeira leitura

```markdown
## Leitura inicial do contexto PDF_Crusher

### 1. Arquivos considerados
### 2. Confiabilidade técnica
### 3. Alertas relevantes
### 4. Páginas/blocos candidatos
### 5. Conteúdo efetivamente aproveitável
### 6. Próxima ação recomendada
```

---

## Se os arquivos esperados não estiverem anexados

Diga objetivamente quais arquivos faltam. Não peça todos se apenas um for necessário.

Exemplo:

```text
Para aplicar o método do PDF_Crusher com segurança, preciso ao menos do arquivo PDF_CRUSHER_CONTEXT.md ou dos volumes PDF_CRUSHER_CONTEXT_001.md, PDF_CRUSHER_CONTEXT_002.md etc. O PDF_CRUSHER_MANIFEST.json ajuda a conferir se todos os volumes foram anexados.
```

---

## Limite da skill

Esta skill não garante anonimização perfeita, não certifica literalidade de OCR e não substitui revisão jurídica ou pericial.
