# Claude Pack

O PDF_Crusher gera uma saída mínima para anexação no Claude.

## Uso normal

Anexe apenas os arquivos em:

```text
outputs/claude/
```

Na maioria dos casos haverá:

```text
PDF_CRUSHER_CONTEXT.md
PDF_CRUSHER_MANIFEST.json
```

Se o processo for grande, haverá volumes:

```text
PDF_CRUSHER_CONTEXT_001.md
PDF_CRUSHER_CONTEXT_002.md
PDF_CRUSHER_CONTEXT_003.md
PDF_CRUSHER_MANIFEST.json
```

## Prompt sugerido

```text
Use a skill pdf-crusher-context-reader para analisar os arquivos PDF_CRUSHER_CONTEXT anexados, em português brasileiro jurídico.
```

## Auditoria local

Os arquivos em `outputs/auditoria/` são mantidos para conferência técnica local. Não precisam ser anexados ao Claude no fluxo comum.
