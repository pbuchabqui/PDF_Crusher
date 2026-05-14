# Modo de Síntese de Decisões — Direito Brasileiro

Este documento resume o modo adicional incorporado à Skill `pdf-crusher-context-reader`.

## Finalidade

Permitir que Claude use os arquivos gerados pelo PDF_Crusher para organizar uma síntese segura de decisões em qualquer área do direito brasileiro.

O PDF_Crusher continua fazendo apenas o pré-processamento técnico. A síntese é feita pelo Claude, usando a Skill.

## Regra principal

Separar sempre:

1. **Transcrição documental** — dispositivos ou comandos relevantes, transcritos de forma literal e rastreável.
2. **Extração de comandos/critérios** — extração posterior, limitada ao que foi expressamente decidido.

## O que a Skill não pode fazer

- criar critério ausente;
- transformar petição em decisão;
- transformar jurisprudência citada em decisão do processo;
- presumir consequência jurídica não expressa;
- usar cálculo de parte como título executivo;
- certificar OCR de baixa confiança como transcrição literal;
- realizar cálculo judicial sem pedido expresso e sem dados suficientes.

## Prompt recomendado no Claude

```text
Use a skill pdf-crusher-context-reader, no modo Síntese de Decisões — Direito Brasileiro, para analisar os arquivos anexos do PDF_Crusher.

Primeiro leia o cabeçalho técnico dos arquivos PDF_CRUSHER_CONTEXT anexados.
Depois identifique decisões judiciais verdadeiras, transcreva os dispositivos ou comandos relevantes literalmente e somente então extraia os comandos expressamente definidos.
Marque como NAO_CONFIRMADO tudo que não estiver expressamente comprovado no contexto.
Responda em português brasileiro jurídico.
```

## Submodo trabalhista

Quando o usuário pedir liquidação trabalhista, use o submodo específico descrito no `SKILL.md`, preservando a separação entre dispositivos transcritos e critérios expressamente decididos.

## Arquivos mais úteis

No fluxo normal, use apenas:

- `PDF_CRUSHER_CONTEXT.md`; ou
- `PDF_CRUSHER_CONTEXT_001.md`, `PDF_CRUSHER_CONTEXT_002.md`, etc.;
- `PDF_CRUSHER_MANIFEST.json`, se disponível.

Os arquivos de auditoria completos ficam em `outputs/auditoria/` para conferência local.
