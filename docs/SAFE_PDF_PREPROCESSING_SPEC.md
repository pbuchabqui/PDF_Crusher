# Pré-processamento Seguro de PDF — Especificação mínima

O pré-processamento técnico não decide nada. Ele apenas prepara o material para análise posterior.

## Regras

- Não interpretar decisões.
- Não definir verbas deferidas ou indeferidas.
- Não definir critérios de liquidação.
- Não realizar cálculos.
- Não tratar OCR ou texto extraído como transcrição definitiva.

## Saídas

- `texto_extraido_bruto.txt`
- `estrutura_pdf.json`
- `auditoria_pdf.json`
- `relatorio_preprocessamento_pdf.md`
- `processo_higienizado.md`

## Confiança

- `ALTO`: texto nativo suficiente.
- `MÉDIO`: texto extraído, mas curto ou com possível perda.
- `BAIXO`: texto muito curto.
- `CRÍTICO`: sem texto extraível.

## Bloqueio

Se a confiança global for `BAIXO` ou `CRÍTICO`, o relatório deve alertar que a conferência humana é necessária antes de uso pericial.
