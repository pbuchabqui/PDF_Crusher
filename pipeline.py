"""End-to-end pipeline used by CLI and Streamlit."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from chunker import split_text
from config import PipelineConfig
from groq_anonymizer import anonymize_names
from pdf_engine import extract_markdown_docling, extract_markdown_hybrid_ocr
from preprocess import build_preprocess, write_preprocess_outputs
from privacy_engine import mask_structured_data

logger = logging.getLogger(__name__)


def _mask_chunk(chunk: str) -> dict:
    """Mask privacy data in a single chunk. Used for parallel processing."""
    result = mask_structured_data(chunk)
    return {"text": result.text, "counts": result.counts}


def _mask_text_parallel(text: str, max_workers: int | None = None, chunk_size: int = 50000) -> tuple[str, dict]:
    """Mask privacy data in parallel chunks for faster processing.

    Args:
        text: Full text to mask
        max_workers: Number of parallel workers (None = auto-detect CPU cores)
        chunk_size: Size of each chunk in characters

    Returns:
        Tuple of (masked_text, aggregated_counts)
    """
    # Auto-detect number of CPU cores if not specified
    if max_workers is None:
        import os
        max_workers = min(os.cpu_count() or 4, 8)  # Cap at 8 to avoid overhead

    # Split into chunks
    chunks = split_text(text, chunk_size)

    if len(chunks) <= 1:
        # Single chunk, no need to parallelize
        result = mask_structured_data(text)
        return result.text, result.counts

    logger.info(f"Masking {len(chunks)} chunks in parallel (workers={max_workers}, CPU cores available)...")
    start_time = time.time()

    # Process chunks in parallel
    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_mask_chunk, chunks))

        # Recombine text
        masked_text = "\n\n".join(r["text"] for r in results)

        # Aggregate counts
        aggregated_counts = {}
        for result in results:
            for key, value in result["counts"].items():
                aggregated_counts[key] = aggregated_counts.get(key, 0) + value

        elapsed = time.time() - start_time
        logger.info(f"Parallel masking complete in {elapsed:.1f}s: {aggregated_counts}")

        return masked_text, aggregated_counts

    except Exception as e:
        # Fall back to single-threaded processing
        logger.warning(f"Parallel processing failed ({e}), falling back to sequential...")
        result = mask_structured_data(text)
        return result.text, result.counts


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


def _write_claude_pack(final_text: str, structure: dict, privacy_audit: dict, output_dir: Path, config: PipelineConfig) -> list[str]:
    claude_dir = output_dir / "claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    for old_file in claude_dir.glob("PDF_CRUSHER_CONTEXT*.md"):
        old_file.unlink()
    manifest_path = claude_dir / "PDF_CRUSHER_MANIFEST.json"
    if manifest_path.exists():
        manifest_path.unlink()

    chunks = split_text(final_text, config.claude_context_chars)
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
        logger.info("Wrote %s (%d chars)", name, len(content))

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


def run_pipeline(
    pdf_path: str | Path,
    output_dir: str | Path,
    config: PipelineConfig | None = None,
    # Legacy keyword arguments kept for backwards compatibility
    use_groq: bool = False,
    groq_api_key: str | None = None,
) -> dict:
    """Run the full PDF_Crusher pipeline.

    Accepts either a ``PipelineConfig`` object or the legacy ``use_groq`` /
    ``groq_api_key`` keyword arguments (which are wrapped into a config internally).
    """
    if config is None:
        config = PipelineConfig(use_groq=use_groq, groq_api_key=groq_api_key)
    config.validate()

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    audit_dir = out / "auditoria"
    audit_dir.mkdir(exist_ok=True)

    logger.info("Starting pipeline for: %s", pdf_path)
    pipeline_start = time.time()

    # Step 1: Preprocess
    step_start = time.time()
    structure, raw_text = build_preprocess(pdf_path)
    write_preprocess_outputs(audit_dir, structure, raw_text)
    logger.info("Preprocessing complete. Pages: %d (%.1fs)",
               structure["auditoria"]["paginas_totais"], time.time() - step_start)

    # Step 2: Extract text with Hybrid OCR (most expensive step)
    step_start = time.time()
    markdown = extract_markdown_hybrid_ocr(pdf_path)
    logger.info("Text extraction complete. Chars: %d (%.1fs)", len(markdown), time.time() - step_start)

    # Step 3: First privacy pass (parallel if text is large)
    step_start = time.time()
    if len(markdown) > 100000:  # Only parallelize large documents
        text, first_pass_counts = _mask_text_parallel(markdown)
        logger.info("First privacy pass (parallel): %s (%.1fs)", first_pass_counts, time.time() - step_start)
    else:
        first_pass = mask_structured_data(markdown)
        text = first_pass.text
        first_pass_counts = first_pass.counts
        logger.info("First privacy pass: %s (%.1fs)", first_pass_counts, time.time() - step_start)

    # Step 4: Groq anonymization (if enabled)
    if config.use_groq:
        step_start = time.time()
        logger.info("Running Groq name anonymization...")
        chunks = split_text(text, config.groq_chunk_chars)
        pieces = [anonymize_names(chunk, config.groq_api_key, model=config.groq_model) for chunk in chunks]
        text = "\n\n".join(pieces)
        logger.info("Groq anonymization complete. %d chunk(s) processed. (%.1fs)",
                   len(chunks), time.time() - step_start)

    # Step 5: Final privacy pass (parallel if text is large)
    step_start = time.time()
    if len(text) > 100000:  # Only parallelize large documents
        final_text, final_pass_counts = _mask_text_parallel(text)
        logger.info("Final privacy pass (parallel): %s (%.1fs)", final_pass_counts, time.time() - step_start)
    else:
        final_pass = mask_structured_data(text)
        final_text = final_pass.text
        final_pass_counts = final_pass.counts
        logger.info("Final privacy pass: %s (%.1fs)", final_pass_counts, time.time() - step_start)

    (audit_dir / "processo_higienizado.md").write_text(final_text, encoding="utf-8")

    privacy_audit = {
        "regex_primeira_passada": first_pass_counts,
        "regex_passada_final": final_pass_counts,
        "groq_usado_para_nomes": config.use_groq,
        "tamanho_maximo_por_arquivo_claude": config.claude_context_chars,
    }
    (audit_dir / "auditoria_privacidade.json").write_text(
        json.dumps(privacy_audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    claude_files = _write_claude_pack(final_text, structure, privacy_audit, out, config)
    total_elapsed = time.time() - pipeline_start
    logger.info("Pipeline complete in %.1f seconds. Claude files: %s", total_elapsed, claude_files)

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
