# Uso da Skill no Claude

O pacote inclui a skill `pdf-crusher-context-reader`, criada para aplicar sempre o mesmo método de leitura aos arquivos gerados pelo PDF_Crusher.

A skill é geral para o **direito brasileiro** e responde em **português brasileiro jurídico**.

## Arquivo para upload no Claude

Use o ZIP separado:

```text
pdf-crusher-context-reader-skill.zip
```

## Fluxo recomendado

1. Rode o PDF_Crusher no PDF.
2. Anexe no Claude somente os arquivos da pasta `outputs/claude/`:
   - `PDF_CRUSHER_CONTEXT.md`, se houver arquivo único; ou
   - `PDF_CRUSHER_CONTEXT_001.md`, `PDF_CRUSHER_CONTEXT_002.md` etc., se o contexto foi dividido em volumes;
   - `PDF_CRUSHER_MANIFEST.json`, opcional, quando quiser informar a lista de volumes.
3. Peça ao Claude:

```text
Use a skill pdf-crusher-context-reader para analisar os arquivos anexos do PDF_Crusher em português brasileiro jurídico.
```

## Quando usar Project

Use Project apenas se quiser manter o processo aberto por vários dias, com histórico e múltiplos chats. Para análise pontual, anexar os arquivos e chamar a skill costuma ser suficiente.

## Modo geral de síntese de decisões

Use quando o objetivo for localizar decisões, transcrever dispositivos/comandos e organizar critérios expressamente definidos em qualquer área do direito brasileiro.

Prompt sugerido:

```text
Use a skill pdf-crusher-context-reader, no modo Síntese de Decisões — Direito Brasileiro, para analisar os arquivos anexos do PDF_Crusher.

Primeiro leia o cabeçalho técnico do `PDF_CRUSHER_CONTEXT`.
Depois identifique decisões judiciais verdadeiras, transcreva os dispositivos ou comandos relevantes literalmente e somente então extraia os comandos expressamente definidos.
Marque como NAO_CONFIRMADO tudo que não estiver expressamente comprovado no contexto.
Responda em português brasileiro jurídico.
```

## Submodo de liquidação trabalhista

Use apenas quando o caso for trabalhista e o objetivo for preparar síntese para liquidação.

Prompt sugerido:

```text
Use a skill pdf-crusher-context-reader, no submodo Liquidação Trabalhista, para analisar os arquivos anexos do PDF_Crusher.

Primeiro leia o cabeçalho técnico do `PDF_CRUSHER_CONTEXT`.
Depois identifique decisões judiciais verdadeiras, transcreva os dispositivos relevantes literalmente e somente então extraia os critérios expressamente definidos para futura liquidação.
Marque como NAO_CONFIRMADO tudo que não estiver expressamente comprovado no contexto.
```
