"""End-to-end pipeline used by CLI and Streamlit."""

from __future__ import annotations

import json
from pathlib import Path

from chunker import split_text
from groq_anonymizer import anonymize_names
from pdf_engine import extract_markdown
from preprocess import build_preprocess, write_preprocess_outputs
from privacy_engine import mask_structured_data


GROQ_CHUNK_CHARS = 30000
CLAUDE_CONTEXT_CHARS = 180000


def _pages_with_type(structure: dict, label: str) -> list[int]:
    return [
        page["pagina_pdf"]
        for page in structure.get("paginas", [])
        if label in page.get("possiveis_tipos", [])
    ]


def _format_pages(pages: list[int], limit: int = 40) -> str:
    if not pages:
        return "nenhuma detectada"
    shown = ", ".join(str(page) for page in pages[:limit])
    if len(pages) > limit:
        shown += f" ... (+{len(pages) - limit})"
    return shown


def _alert_lines(alerts: list[str]) -> str:
    return "\n".join(f"- {alert}" for alert in alerts) if alerts else "- Nenhum alerta crítico no pré-processamento."


def _claude_header(structure: dict, privacy_audit: dict, volume: int, total: int) -> str:
    cls = structure["classificacao_tecnica"]
    audit = structure["auditoria"]
    alerts = structure.get("alertas", [])

    decision_pages = _pages_with_type(structure, "página candidata a conter decisão judicial")
    petition_pages = _pages_with_type(structure, "possível petição/manifestação")
    evidence_pages = _pages_with_type(structure, "possível prova/documento")
    hearing_pages = _pages_with_type(structure, "possível ata/audiência/depoimento")
    calc_pages = _pages_with_type(structure, "possível cálculo/demonstrativo")
    labor_pages = _pages_with_type(structure, "possível documento trabalhista")

    title = "PDF_CRUSHER_CONTEXT" if total == 1 else f"PDF_CRUSHER_CONTEXT — VOLUME {volume:03d} DE {total:03d}"

    return f"""# {title}

## 1. Identificação

- Arquivo original: {structure['arquivo']['nome']}
- Escopo jurídico: {structure.get('escopo_juridico', 'direito brasileiro em geral')}
- Idioma preferencial: {structure.get('idioma_preferencial', 'português brasileiro')}
- Volume: {volume} de {total}

## 2. Resumo técnico

- Páginas totais: {audit['paginas_totais']}
- Tipo técnico do PDF: {cls['tipo_pdf']}
- Confiança global: {cls['confianca_global']}
- Necessita OCR/conferência adicional: {cls['necessita_ocr']}
- Sumário/índice processual detectado: {structure['sumario']['detectado']}
- Groq usado para nomes: {privacy_audit['groq_usado_para_nomes']}

## 3. Páginas candidatas detectadas

- Possíveis decisões judiciais: {_format_pages(decision_pages)}
- Possíveis petições/manifestações/recursos: {_format_pages(petition_pages)}
- Possíveis provas/documentos: {_format_pages(evidence_pages)}
- Possíveis atas/audiências/depoimentos: {_format_pages(hearing_pages)}
- Possíveis cálculos/demonstrativos: {_format_pages(calc_pages)}
- Possíveis documentos trabalhistas: {_format_pages(labor_pages)}

## 4. Alertas técnicos

{_alert_lines(alerts)}

## 5. Auditoria resumida

```json
{json.dumps(audit, ensure_ascii=False, indent=2)}
```

## 6. Auditoria de privacidade

```json
{json.dumps(privacy_audit, ensure_ascii=False, indent=2)}
```

## 7. Instrução para Claude

Use a skill `pdf-crusher-context-reader` para ler este arquivo.
Responda em português brasileiro jurídico.
Trate este conteúdo como extração técnica preliminar, não como transcrição definitiva.
Não invente dados ausentes.
Não trate página candidata como decisão confirmada.
Não use petições, argumentos das partes, cálculos das partes ou jurisprudência citada como se fossem decisão do processo.
Quando houver OCR, baixa confiança ou ausência de origem clara, ressalve a necessidade de conferência humana.

---

## 8. Conteúdo extraído e higienizado

"""


def _write_claude_pack(final_text: str, structure: dict, privacy_audit: dict, output_dir: Path) -> list[str]:
    claude_dir = output_dir / "claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    for old_file in claude_dir.glob("PDF_CRUSHER_CONTEXT*.md"):
        old_file.unlink()
    manifest_path = claude_dir / "PDF_CRUSHER_MANIFEST.json"
    if manifest_path.exists():
        manifest_path.unlink()

    chunks = split_text(final_text, CLAUDE_CONTEXT_CHARS)
    total = len(chunks)
    files: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        if total == 1:
            name = "PDF_CRUSHER_CONTEXT.md"
        else:
            name = f"PDF_CRUSHER_CONTEXT_{index:03d}.md"
        content = _claude_header(structure, privacy_audit, index, total) + chunk.strip() + "\n"
        (claude_dir / name).write_text(content, encoding="utf-8")
        files.append(f"claude/{name}")

    manifest = {
        "modo_saida": "claude_pack",
        "descricao": "Arquivos mínimos para anexar ao Claude.",
        "arquivos_para_anexar": files,
        "quantidade_arquivos_contexto": total,
        "arquivo_original": structure["arquivo"]["nome"],
        "escopo_juridico": structure.get("escopo_juridico", "direito brasileiro em geral"),
        "idioma_preferencial": structure.get("idioma_preferencial", "português brasileiro"),
        "confianca_global": structure["classificacao_tecnica"]["confianca_global"],
        "usar_skill": "pdf-crusher-context-reader",
        "prompt_sugerido": "Use a skill pdf-crusher-context-reader para analisar os arquivos PDF_CRUSHER_CONTEXT anexados, em português brasileiro jurídico.",
        "observacao": "Os demais arquivos ficam na pasta auditoria/ para conferência local e não precisam ser anexados ao Claude em uso normal.",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    files.append("claude/PDF_CRUSHER_MANIFEST.json")
    return files


def run_pipeline(pdf_path: str | Path, output_dir: str | Path, use_groq: bool = False, groq_api_key: str | None = None) -> dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    audit_dir = out / "auditoria"
    audit_dir.mkdir(exist_ok=True)

    structure, raw_text = build_preprocess(pdf_path)
    write_preprocess_outputs(audit_dir, structure, raw_text)

    markdown = extract_markdown(pdf_path)

    first_pass = mask_structured_data(markdown)
    text = first_pass.text

    if use_groq:
        if not groq_api_key:
            raise ValueError("Groq API key is required when use_groq=True")
        pieces = [anonymize_names(chunk, groq_api_key) for chunk in split_text(text, GROQ_CHUNK_CHARS)]
        text = "\n\n".join(pieces)

    final_pass = mask_structured_data(text)
    final_text = final_pass.text

    (audit_dir / "processo_higienizado.md").write_text(final_text, encoding="utf-8")

    privacy_audit = {
        "regex_primeira_passada": first_pass.counts,
        "regex_passada_final": final_pass.counts,
        "groq_usado_para_nomes": use_groq,
        "tamanho_maximo_por_arquivo_claude": CLAUDE_CONTEXT_CHARS,
    }
    (audit_dir / "auditoria_privacidade.json").write_text(json.dumps(privacy_audit, ensure_ascii=False, indent=2), encoding="utf-8")

    claude_files = _write_claude_pack(final_text, structure, privacy_audit, out)

    return {
        "output_dir": str(out),
        "structure": structure,
        "privacy_audit": privacy_audit,
        "claude_files": claude_files,
        "audit_files": [
            "auditoria/processo_higienizado.md",
            "auditoria/texto_extraido_bruto.txt",
            "auditoria/estrutura_pdf.json",
            "auditoria/auditoria_pdf.json",
            "auditoria/auditoria_privacidade.json",
            "auditoria/relatorio_preprocessamento_pdf.md",
        ],
        "files": claude_files,
    }
