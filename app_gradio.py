"""Gradio interface for PDF_Crusher — entry point for Hugging Face Spaces."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("TRANSFORMERS_CACHE", "/tmp/hf_cache")
os.environ.setdefault("HF_HOME", "/tmp/hf_cache")

import gradio as gr

from config import PipelineConfig
from pipeline import run_pipeline

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

# ── Constants ─────────────────────────────────────────────────────────────────

_CONFIDENCE_LABEL = {
    "ALTO": "🟢 ALTO",
    "MÉDIO": "🟡 MÉDIO",
    "BAIXO": "🟠 BAIXO",
    "CRÍTICO": "🔴 CRÍTICO",
}

_PAGE_TYPE_LABELS = [
    ("paginas_candidatas_decisoes", "Decisões judiciais"),
    ("paginas_candidatas_manifestacoes", "Petições / manifestações"),
    ("paginas_candidatas_provas", "Provas / documentos"),
    ("paginas_candidatas_audiencias", "Atas / audiências"),
    ("paginas_candidatas_calculos", "Cálculos / demonstrativos"),
    ("paginas_candidatas_documentos_trabalhistas", "Documentos trabalhistas"),
]

_ERROR_CONTEXT: dict[str, tuple[str, str]] = {
    "validation": (
        "Erro de validação do arquivo",
        "Verifique se o arquivo selecionado é um PDF válido e não está corrompido ou protegido por senha.",
    ),
    "groq": (
        "Erro na anonimização via Groq",
        "Verifique se a Groq API Key está correta e se há cota disponível. "
        "Você pode desmarcar a opção Groq e tentar novamente.",
    ),
    "processing": (
        "Erro no processamento do PDF",
        "O PDF pode estar criptografado, corrompido ou em formato não suportado. "
        "Tente remover a senha do PDF antes de processar, ou use outro arquivo.",
    ),
    "unexpected": (
        "Erro inesperado",
        "Um erro interno ocorreu. Reporte o problema com os detalhes técnicos abaixo.",
    ),
}

_STEPS_BASE = """\
**Etapas em execução:**

1. Pré-processamento técnico do PDF (pypdf)
2. Extração de texto e Markdown (Docling)
3. Máscaras de privacidade — regex local (CPF, CNPJ, e-mail, telefone)
"""
_STEPS_GROQ = "4. Anonimização de nomes via Groq *(pode levar 1–2 min em documentos longos)*\n"
_STEPS_PACK = "5. Geração do Claude Pack\n"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_bytes(n: int) -> str:
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f} MB"
    if n >= 1_024:
        return f"{n / 1_024:.1f} KB"
    return f"{n} B"


def _validate_upload(file_path: str | None, use_groq: bool, groq_key: str | None) -> str | None:
    if not file_path:
        return "Nenhum arquivo selecionado."
    with open(file_path, "rb") as f:
        header = f.read(5)
    if header != b"%PDF-":
        return f"O arquivo não é um PDF válido (assinatura incorreta)."
    if use_groq and not groq_key:
        return "Informe a Groq API Key para usar a anonimização de nomes."
    return None


def _build_classification_md(structure: dict) -> str:
    audit = structure["auditoria"]
    total = max(audit["paginas_totais"], 1)
    lines = []
    for key, label in _PAGE_TYPE_LABELS:
        count = audit.get(key, 0)
        if count > 0:
            pct = int(count / total * 20)
            bar = "█" * pct + "░" * (20 - pct)
            lines.append(f"**{label}**: `{bar}` {count} pág.")
    return "\n\n".join(lines) if lines else "_Nenhuma página com tipo específico detectado._"


def _build_privacy_md(privacy_audit: dict) -> str:
    first = privacy_audit["regex_primeira_passada"]
    final = privacy_audit["regex_passada_final"]
    groq_used = privacy_audit["groq_usado_para_nomes"]
    return (
        f"| Tipo | Quantidade |\n|---|---|\n"
        f"| CPF | {first['cpf'] + final['cpf']} |\n"
        f"| CNPJ | {first['cnpj'] + final['cnpj']} |\n"
        f"| E-mail | {first['email'] + final['email']} |\n"
        f"| Telefone | {first['telefone'] + final['telefone']} |\n"
        f"| Nomes via Groq | {'Sim ✓' if groq_used else 'Não'} |"
    )


def _build_alerts_md(structure: dict) -> str:
    alerts = structure.get("alertas", [])
    if not alerts:
        return ""
    items = "\n".join(f"- {a}" for a in alerts)
    return f"⚠️ **{len(alerts)} alerta(s) técnico(s):**\n\n{items}"


def _error_md(error_msg: str, error_type: str) -> str:
    title, suggestion = _ERROR_CONTEXT.get(error_type, _ERROR_CONTEXT["unexpected"])
    return (
        f"### ❌ {title}\n\n{suggestion}\n\n"
        f"<details><summary>Detalhes técnicos</summary>\n\n```\n{error_msg}\n```\n</details>"
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

def on_pdf_change(file):
    return gr.update(interactive=file is not None)


def on_groq_toggle(checked):
    return gr.update(visible=checked)


def on_submit(pdf_file, use_groq, groq_key, tmp_ctx_state):
    # pdf_file is the filepath string from gr.File()
    error = _validate_upload(pdf_file, use_groq, groq_key)
    if error:
        return (
            gr.update(visible=False),   # status_md
            gr.update(value=f"### ❌ {error}", visible=True),  # error_box
            gr.update(visible=False),   # results_panel
            "", "", "", "",             # metrics
            "",                         # file_info_md
            gr.update(value="", visible=False),  # alerts_md
            "", "",                     # classification_md, privacy_md
            None, None,                 # claude_files_output, audit_files_output
            "",                         # report_md
            gr.update(choices=[], visible=False),   # preview_selector
            gr.update(value="", visible=False),     # preview_content
            None, None, None,           # states
        )

    # Cleanup previous temp dir if exists
    if tmp_ctx_state is not None:
        try:
            tmp_ctx_state.cleanup()
        except Exception:
            pass

    tmp_ctx = tempfile.TemporaryDirectory()
    tmp_path = Path(tmp_ctx.name)
    out_dir = tmp_path / "outputs"

    # Copy uploaded PDF to temp dir (preserve original filename)
    original_name = Path(pdf_file).name
    dest_pdf = tmp_path / original_name
    dest_pdf.write_bytes(Path(pdf_file).read_bytes())

    config = PipelineConfig(use_groq=use_groq, groq_api_key=groq_key or None)

    try:
        result = run_pipeline(dest_pdf, out_dir, config=config)
    except (FileNotFoundError, ValueError) as exc:
        tmp_ctx.cleanup()
        return _error_outputs(str(exc), "validation")
    except RuntimeError as exc:
        tmp_ctx.cleanup()
        error_type = "groq" if "Groq" in str(exc) else "processing"
        return _error_outputs(str(exc), error_type)
    except Exception as exc:
        tmp_ctx.cleanup()
        return _error_outputs(str(exc), "unexpected")

    structure = result["structure"]
    privacy_audit = result["privacy_audit"]
    audit = structure["auditoria"]
    cls = structure["classificacao_tecnica"]
    arq = structure["arquivo"]

    n_md = sum(1 for f in result["claude_files"] if f.endswith(".md"))

    # Build metric values
    confidence_display = _CONFIDENCE_LABEL.get(cls["confianca_global"], cls["confianca_global"])
    ocr_flag = " ⚠️ (necessita OCR)" if cls["necessita_ocr"] else ""
    file_info = (
        f"**Arquivo:** `{arq['nome']}` · "
        f"**Tamanho:** {_fmt_bytes(arq['tamanho_bytes'])} · "
        f"**Tipo:** {cls['tipo_pdf']}{ocr_flag}"
    )

    alerts_text = _build_alerts_md(structure)
    classification_text = _build_classification_md(structure)
    privacy_text = _build_privacy_md(privacy_audit)

    # File paths for gr.File() outputs
    claude_paths = [str(out_dir / rel) for rel in result["claude_files"]]
    audit_paths = [
        str(out_dir / rel)
        for rel in result["audit_files"]
        if (out_dir / rel).exists()
    ]

    # Technical report
    report_path = out_dir / "auditoria" / "relatorio_preprocessamento_pdf.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""

    # Preview: list of (name, content) for markdown files
    md_files = [
        (Path(rel).name, (out_dir / rel).read_text(encoding="utf-8"))
        for rel in result["claude_files"]
        if rel.endswith(".md")
    ]
    preview_choices = [name for name, _ in md_files]
    first_content = md_files[0][1] if md_files else ""

    volume_label = f"{n_md} arquivo(s)"
    if n_md > 1:
        volume_label += " — anexe todos ao Claude"

    return (
        gr.update(visible=False),                              # status_md
        gr.update(value="", visible=False),                   # error_box
        gr.update(visible=True),                              # results_panel
        str(audit["paginas_totais"]),                         # metric_pages
        confidence_display,                                   # metric_confidence
        cls["tipo_pdf"],                                      # metric_type
        volume_label,                                         # metric_volumes
        file_info,                                            # file_info_md
        gr.update(value=alerts_text, visible=bool(alerts_text)),  # alerts_md
        classification_text,                                  # classification_md
        privacy_text,                                         # privacy_md
        claude_paths,                                         # claude_files_output
        audit_paths,                                          # audit_files_output
        report_text,                                          # report_md
        gr.update(choices=preview_choices, value=preview_choices[0] if preview_choices else None, visible=bool(preview_choices)),  # preview_selector
        gr.update(value=first_content, visible=bool(first_content)),  # preview_content
        result,                                               # state_result
        tmp_ctx,                                              # state_tmp_ctx
        str(out_dir),                                         # state_out_dir
    )


def on_preview_select(choice, result_state, out_dir_state):
    if not choice or not result_state or not out_dir_state:
        return ""
    out_dir = Path(out_dir_state)
    for rel in result_state["claude_files"]:
        if Path(rel).name == choice and rel.endswith(".md"):
            path = out_dir / rel
            if path.exists():
                return path.read_text(encoding="utf-8")
    return ""


def on_reset(tmp_ctx_state):
    if tmp_ctx_state is not None:
        try:
            tmp_ctx_state.cleanup()
        except Exception:
            pass
    return (
        gr.update(visible=False),                             # results_panel
        gr.update(value="", visible=False),                   # error_box
        gr.update(interactive=False),                         # submit_btn
        None,                                                 # pdf_input
        False,                                                # use_groq
        "",                                                   # groq_key
        gr.update(visible=False),                             # groq_panel
        None, None, None,                                     # states
    )


def _error_outputs(error_msg: str, error_type: str):
    """Return the full output tuple for an error state."""
    return (
        gr.update(visible=False),                             # status_md
        gr.update(value=_error_md(error_msg, error_type), visible=True),  # error_box
        gr.update(visible=False),                             # results_panel
        "", "", "", "",                                       # metrics
        "",                                                   # file_info_md
        gr.update(value="", visible=False),                   # alerts_md
        "", "",                                               # classification_md, privacy_md
        None, None,                                           # claude_files_output, audit_files_output
        "",                                                   # report_md
        gr.update(choices=[], visible=False),                 # preview_selector
        gr.update(value="", visible=False),                   # preview_content
        None, None, None,                                     # states
    )


# ── UI Definition ─────────────────────────────────────────────────────────────

_SUBMIT_OUTPUTS_COUNT = 19  # must match the number of return values in on_submit


with gr.Blocks(title="PDF_Crusher") as demo:

    # States
    state_result  = gr.State(None)
    state_tmp_ctx = gr.State(None)
    state_out_dir = gr.State(None)

    # ── Header ────────────────────────────────────────────────────────────────
    gr.Markdown("# ⚡ PDF_Crusher")
    gr.Markdown(
        "Transforma PDFs jurídicos brasileiros densos em poucos arquivos de contexto "
        "para Claude/LLM — com higienização local de dados pessoais (CPF, CNPJ, e-mail, telefone)."
    )
    gr.Markdown("---")

    # ── Upload & Config ───────────────────────────────────────────────────────
    pdf_input = gr.File(label="Selecione o PDF jurídico", file_types=[".pdf"])

    use_groq = gr.Checkbox(label="Usar Groq para anonimizar nomes de pessoas", value=False)

    with gr.Group(visible=False) as groq_panel:
        groq_key = gr.Textbox(
            label="Groq API Key",
            type="password",
            placeholder="gsk_...",
        )
        gr.Markdown(
            "`llama-3.3-70b-versatile` · chunks de 30.000 chars · "
            "até 3 tentativas com backoff · timeout de 60 s por chunk"
        )

    submit_btn = gr.Button("▶ Processar PDF", variant="primary", interactive=False)

    # ── Status / Error ────────────────────────────────────────────────────────
    status_md = gr.Markdown(visible=False)
    error_box = gr.Markdown(visible=False)

    # ── Results ───────────────────────────────────────────────────────────────
    with gr.Column(visible=False) as results_panel:
        gr.Markdown("---")
        gr.Markdown("## ✅ PDF processado com sucesso!")

        # Metrics
        with gr.Row():
            metric_pages      = gr.Textbox(label="Páginas totais", interactive=False)
            metric_confidence = gr.Textbox(label="Confiança global", interactive=False)
            metric_type       = gr.Textbox(label="Tipo de PDF", interactive=False)
            metric_volumes    = gr.Textbox(label="Volumes gerados", interactive=False)

        file_info_md = gr.Markdown()

        alerts_md = gr.Markdown(visible=False)

        with gr.Accordion("Classificação de páginas candidatas", open=True):
            classification_md = gr.Markdown()

        with gr.Accordion("Dados pessoais mascarados", open=True):
            privacy_md = gr.Markdown()

        gr.Markdown("---")
        gr.Markdown("## Arquivos para o Claude")
        gr.Markdown(
            "Anexe **apenas estes arquivos** ao Claude e use a skill "
            "`pdf-crusher-context-reader`. Não é necessário enviar os arquivos de auditoria."
        )
        claude_files_output = gr.File(
            label="Arquivos para o Claude",
            file_count="multiple",
            interactive=False,
        )

        with gr.Accordion("Arquivos de auditoria local — não enviar ao Claude", open=False):
            gr.Markdown(
                "Estes arquivos ficam para conferência humana. "
                "Não precisam ser anexados ao Claude em uso normal."
            )
            audit_files_output = gr.File(
                label="Arquivos de auditoria",
                file_count="multiple",
                interactive=False,
            )

        gr.Markdown("---")
        gr.Markdown("## Pré-visualização dos arquivos de contexto")
        preview_selector = gr.Dropdown(
            label="Arquivo de contexto",
            choices=[],
            visible=False,
        )
        preview_content = gr.Textbox(
            label="",
            lines=20,
            interactive=False,
            visible=False,
        )

        with gr.Accordion("Relatório técnico completo (auditoria local)", open=False):
            report_md_out = gr.Markdown()

        reset_btn = gr.Button("Processar novo PDF", variant="secondary")

    # ── Event wiring ──────────────────────────────────────────────────────────

    pdf_input.change(fn=on_pdf_change, inputs=[pdf_input], outputs=[submit_btn])
    use_groq.change(fn=on_groq_toggle, inputs=[use_groq], outputs=[groq_panel])

    _submit_outputs = [
        status_md, error_box, results_panel,
        metric_pages, metric_confidence, metric_type, metric_volumes,
        file_info_md, alerts_md,
        classification_md, privacy_md,
        claude_files_output, audit_files_output,
        report_md_out,
        preview_selector, preview_content,
        state_result, state_tmp_ctx, state_out_dir,
    ]

    submit_btn.click(
        fn=on_submit,
        inputs=[pdf_input, use_groq, groq_key, state_tmp_ctx],
        outputs=_submit_outputs,
    )

    preview_selector.change(
        fn=on_preview_select,
        inputs=[preview_selector, state_result, state_out_dir],
        outputs=[preview_content],
    )

    reset_btn.click(
        fn=on_reset,
        inputs=[state_tmp_ctx],
        outputs=[
            results_panel, error_box, submit_btn,
            pdf_input, use_groq, groq_key, groq_panel,
            state_result, state_tmp_ctx, state_out_dir,
        ],
    )


if __name__ == "__main__":
    demo.launch()
