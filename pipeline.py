"""End-to-end pipeline used by CLI and Streamlit."""

from __future__ import annotations

import json
from pathlib import Path

from chunker import split_text
from groq_anonymizer import anonymize_names
from pdf_engine import extract_markdown_docling
from preprocess import build_preprocess, write_preprocess_outputs
from privacy_engine import mask_structured_data


LLM_CHUNK_CHARS = 65000
GROQ_CHUNK_CHARS = 30000


def _pages_with_type(structure: dict, label: str) -> list[int]:
    return [
        page["pagina_pdf"]
        for page in structure.get("paginas", [])
        if label in page.get("possiveis_tipos", [])
    ]


def _format_pages(pages: list[int], limit: int = 30) -> str:
    if not pages:
        return "nenhuma detectada"
    shown = ", ".join(str(page) for page in pages[:limit])
    if len(pages) > limit:
        shown += f" ... (+{len(pages) - limit})"
    return shown


def _chunk_header(index: int, total: int, structure: dict) -> str:
    cls = structure["classificacao_tecnica"]
    audit = structure["auditoria"]
    alerts = structure.get("alertas", [])

    decision_pages = _pages_with_type(structure, "página candidata a conter decisão judicial")
    petition_pages = _pages_with_type(structure, "possível petição/manifestação")
    evidence_pages = _pages_with_type(structure, "possível prova/documento")
    hearing_pages = _pages_with_type(structure, "possível ata/audiência/depoimento")
    calc_pages = _pages_with_type(structure, "possível cálculo/demonstrativo")
    labor_pages = _pages_with_type(structure, "possível documento trabalhista")

    next_instruction = (
        "Este não é o último bloco. Apenas absorva o contexto, mantenha a ordem cronológica e aguarde os próximos blocos antes de concluir."
        if index < total
        else "Este é o último bloco. Após ler, consolide a resposta usando todos os blocos anteriores."
    )

    return f"""# CONTEXTO LLM — PARTE {index:03d} DE {total:03d}

## Metadados do arquivo

- Arquivo original: {structure['arquivo']['nome']}
- Escopo jurídico: {structure.get('escopo_juridico', 'direito brasileiro em geral')}
- Idioma preferencial: {structure.get('idioma_preferencial', 'português brasileiro')}
- Páginas totais: {audit['paginas_totais']}
- Tipo técnico do PDF: {cls['tipo_pdf']}
- Confiança global: {cls['confianca_global']}
- Necessita OCR/conferência adicional: {cls['necessita_ocr']}
- Sumário/índice processual detectado: {structure['sumario']['detectado']}

## Páginas candidatas detectadas no PDF inteiro

- Possíveis decisões judiciais: {_format_pages(decision_pages)}
- Possíveis petições/manifestações/recursos: {_format_pages(petition_pages)}
- Possíveis provas/documentos: {_format_pages(evidence_pages)}
- Possíveis atas/audiências/depoimentos: {_format_pages(hearing_pages)}
- Possíveis cálculos/demonstrativos: {_format_pages(calc_pages)}
- Possíveis documentos trabalhistas: {_format_pages(labor_pages)}

## Alertas técnicos

{chr(10).join(f'- {alert}' for alert in alerts) if alerts else '- Nenhum alerta crítico no pré-processamento.'}

## Instrução para a LLM

Você receberá autos ou documentos jurídicos brasileiros em partes. Use português brasileiro jurídico, preserve termos técnicos e trate este bloco como contexto documental preliminar, não como transcrição definitiva.
Não invente dados ausentes. Não trate página candidata como decisão confirmada. Quando houver baixa confiança, ressalve a necessidade de conferência humana.
{next_instruction}

---

"""


def _manifest(structure: dict, total_chunks: int) -> str:
    cls = structure["classificacao_tecnica"]
    audit = structure["auditoria"]
    return f"""# Guia de Uso do Contexto em LLM Web

Use os arquivos de `chunks/` em ordem: `parte_001.md`, `parte_002.md`, etc.

Cada parte contém um cabeçalho com metadados, alertas e páginas candidatas. O conteúdo é preliminar e deve ser conferido quando usado para fins jurídicos ou periciais.

## Resumo técnico

- Arquivo: {structure['arquivo']['nome']}
- Escopo jurídico: {structure.get('escopo_juridico', 'direito brasileiro em geral')}
- Idioma preferencial: {structure.get('idioma_preferencial', 'português brasileiro')}
- Páginas totais: {audit['paginas_totais']}
- Tipo técnico: {cls['tipo_pdf']}
- Confiança global: {cls['confianca_global']}
- Partes geradas: {total_chunks}
- Sumário/índice processual detectado: {structure['sumario']['detectado']}

## Prompt sugerido para a primeira mensagem

```text
Vou enviar um processo ou conjunto de documentos jurídicos brasileiros em partes. Cada parte terá cabeçalho técnico e conteúdo documental higienizado.
Use português brasileiro jurídico. Não responda conclusivamente até eu informar que enviei a última parte.
Ao receber cada parte, apenas confirme a assimilação e registre pontos relevantes para posterior consolidação.
```

## Prompt sugerido para a última mensagem

```text
Esta foi a última parte. Agora consolide a análise considerando todos os blocos enviados, preservando cautela quanto a OCR, páginas candidatas e trechos de baixa confiança.
```
"""


def _write_llm_chunks(text: str, structure: dict, output_dir: Path) -> int:
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    for old_chunk in chunks_dir.glob("parte_*.md"):
        old_chunk.unlink()

    chunks = split_text(text, LLM_CHUNK_CHARS)
    total = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        content = _chunk_header(index, total, structure) + chunk.strip() + "\n"
        (chunks_dir / f"parte_{index:03d}.md").write_text(content, encoding="utf-8")

    (output_dir / "guia_uso_llm.md").write_text(_manifest(structure, total), encoding="utf-8")
    return total


def run_pipeline(pdf_path: str | Path, output_dir: str | Path, use_groq: bool = False, groq_api_key: str | None = None) -> dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    structure, raw_text = build_preprocess(pdf_path)
    write_preprocess_outputs(out, structure, raw_text)

    markdown = extract_markdown_docling(pdf_path)

    first_pass = mask_structured_data(markdown)
    text = first_pass.text

    if use_groq:
        if not groq_api_key:
            raise ValueError("Groq API key is required when use_groq=True")
        pieces = [anonymize_names(chunk, groq_api_key) for chunk in split_text(text, GROQ_CHUNK_CHARS)]
        text = "\n\n".join(pieces)

    final_pass = mask_structured_data(text)
    final_text = final_pass.text

    (out / "processo_higienizado.md").write_text(final_text, encoding="utf-8")
    chunk_count = _write_llm_chunks(final_text, structure, out)

    privacy_audit = {
        "regex_primeira_passada": first_pass.counts,
        "regex_passada_final": final_pass.counts,
        "groq_usado_para_nomes": use_groq,
        "chunks_llm_gerados": chunk_count,
        "tamanho_maximo_conteudo_por_chunk": LLM_CHUNK_CHARS,
    }
    (out / "auditoria_privacidade.json").write_text(json.dumps(privacy_audit, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "output_dir": str(out),
        "structure": structure,
        "privacy_audit": privacy_audit,
        "files": [
            "processo_higienizado.md",
            "guia_uso_llm.md",
            "texto_extraido_bruto.txt",
            "estrutura_pdf.json",
            "auditoria_pdf.json",
            "auditoria_privacidade.json",
            "relatorio_preprocessamento_pdf.md",
            "chunks/",
        ],
    }
