"""Streamlit interface — PDF_Crusher."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import streamlit as st

import app_components as ui
from config import PipelineConfig
from pipeline import run_pipeline

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

st.set_page_config(page_title="PDF_Crusher", page_icon="⚡", layout="wide")

# ── Session state defaults ────────────────────────────────────────────────────

_DEFAULTS: dict = {
    "state": "idle",      # "idle" | "done" | "error"
    "outputs": None,
    "claude_files": None,
    "report_md": None,
    "error_msg": None,
    "error_type": None,
    "tmp_ctx": None,      # TemporaryDirectory kept alive so audit files remain accessible
    "out_dir": None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reset() -> None:
    if st.session_state.tmp_ctx is not None:
        st.session_state.tmp_ctx.cleanup()
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v


def _validate_upload(file, use_groq: bool, groq_key: str | None) -> str | None:
    header = file.read(5)
    file.seek(0)
    if header != b"%PDF-":
        return f"O arquivo '{file.name}' não é um PDF válido (assinatura incorreta)."
    if use_groq and not groq_key:
        return "Informe a Groq API Key para usar a anonimização de nomes."
    return None


# ── Header (always visible) ───────────────────────────────────────────────────

ui.render_header()

# ── State router ──────────────────────────────────────────────────────────────

if st.session_state.state == "idle":
    form = ui.render_upload_panel()

    if form["submitted"] and form["uploaded"] is not None:
        # Validate Groq API key format if enabled
        if form["use_groq"] and form["groq_key"]:
            import re
            groq_pattern = re.compile(r"^gsk_[A-Za-z0-9]{20,}$")
            if not groq_pattern.match(form["groq_key"]):
                st.error("Formato inválido de Groq API Key. Esperado: gsk_ seguido de 20+ caracteres alfanuméricos.")
                form["use_groq"] = False
                form["groq_key"] = None
        
        error = _validate_upload(form["uploaded"], form["use_groq"], form["groq_key"])
        if error:
            st.error(error)
        else:
            tmp_ctx = tempfile.TemporaryDirectory()
            st.session_state.tmp_ctx = tmp_ctx
            tmp_path = Path(tmp_ctx.name)
            out_dir = tmp_path / "outputs"
            st.session_state.out_dir = out_dir

            pdf_path = tmp_path / form["uploaded"].name
            pdf_path.write_bytes(form["uploaded"].getbuffer())

            config = PipelineConfig(
                use_groq=form["use_groq"],
                groq_api_key=form["groq_key"] or None,
            )
            
            # Store compliance settings in session state for audit
            st.session_state.compliance_settings = {
                "data_residency": form.get("data_residency", "brazil"),
                "retention_days": form.get("retention_days"),
                "enable_audit_log": form.get("enable_audit_log", True),
                "output_format": form.get("output_format", "markdown"),
                "language": form.get("language", "pt-BR"),
            }

            with st.spinner("Processando PDF — aguarde..."):
                ui.render_processing_steps(form["use_groq"])
                try:
                    result = run_pipeline(pdf_path, out_dir, config=config)

                    claude_files = [
                        (rel, (out_dir / rel).read_text(encoding="utf-8"))
                        for rel in result["claude_files"]
                    ]
                    report_md = (
                        out_dir / "auditoria" / "relatorio_preprocessamento_pdf.md"
                    ).read_text(encoding="utf-8")

                    st.session_state.outputs = result
                    st.session_state.claude_files = claude_files
                    st.session_state.report_md = report_md
                    st.session_state.state = "done"
                    st.rerun()

                except (FileNotFoundError, ValueError) as exc:
                    st.session_state.error_msg = str(exc)
                    st.session_state.error_type = "validation"
                    st.session_state.state = "error"
                    st.rerun()

                except RuntimeError as exc:
                    st.session_state.error_msg = str(exc)
                    st.session_state.error_type = "groq" if "Groq" in str(exc) else "processing"
                    st.session_state.state = "error"
                    st.rerun()

                except Exception as exc:
                    st.session_state.error_msg = str(exc)
                    st.session_state.error_type = "unexpected"
                    st.session_state.state = "error"
                    st.rerun()

elif st.session_state.state == "done":
    result = st.session_state.outputs
    structure = result["structure"]
    privacy_audit = result["privacy_audit"]
    claude_files = st.session_state.claude_files
    out_dir = st.session_state.out_dir

    ui.render_success_banner(on_reset=_reset)
    ui.render_metrics_strip(structure, privacy_audit, claude_files)
    ui.render_alerts(structure)
    ui.render_page_classification(structure)
    ui.render_privacy_summary(privacy_audit)
    ui.render_downloads(claude_files, result, out_dir)
    ui.render_file_preview(claude_files)
    ui.render_technical_report(st.session_state.report_md)

elif st.session_state.state == "error":
    ui.render_error_panel(
        st.session_state.error_msg,
        st.session_state.error_type,
        on_reset=_reset,
    )
