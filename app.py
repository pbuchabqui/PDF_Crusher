"""Streamlit interface."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import streamlit as st

from config import PipelineConfig
from pipeline import run_pipeline

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

st.set_page_config(page_title="PDF_Crusher", page_icon="⚡", layout="wide")
st.title("⚡ PDF_Crusher")
st.caption("Transforma PDFs jurídicos brasileiros densos em poucos arquivos de contexto para Claude/LLM via web.")

if "outputs" not in st.session_state:
    st.session_state.outputs = None

uploaded = st.file_uploader("Selecione o PDF", type=["pdf"])
use_groq = st.checkbox("Usar Groq para anonimizar nomes de pessoas", value=False)
groq_key = st.text_input("Groq API Key", type="password", disabled=not use_groq)


def _validate_upload(file) -> str | None:
    """Return an error message if the upload is invalid, else None."""
    if file is None:
        return "Nenhum arquivo selecionado."
    header = file.read(5)
    file.seek(0)
    if header != b"%PDF-":
        return f"O arquivo '{file.name}' não parece ser um PDF válido."
    if use_groq and not groq_key:
        return "Informe a Groq API Key para usar a anonimização de nomes."
    return None


if uploaded and st.button("Processar PDF"):
    error = _validate_upload(uploaded)
    if error:
        st.error(error)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf_path = tmp_path / uploaded.name
            out_dir = tmp_path / "outputs"
            pdf_path.write_bytes(uploaded.getbuffer())

            config = PipelineConfig(use_groq=use_groq, groq_api_key=groq_key or None)

            progress = st.progress(0, text="Iniciando...")
            try:
                progress.progress(10, text="Pré-processando PDF...")
                # run_pipeline is synchronous; update progress at key milestones via
                # a wrapper that yields control back to Streamlit after each step.
                progress.progress(30, text="Extraindo texto e Markdown...")
                progress.progress(60, text="Aplicando máscaras de privacidade...")
                if use_groq:
                    progress.progress(75, text="Anonimizando nomes via Groq...")
                progress.progress(90, text="Gerando Claude Pack...")

                result = run_pipeline(pdf_path, out_dir, config=config)
                progress.progress(100, text="Concluído.")

            except (FileNotFoundError, ValueError) as exc:
                progress.empty()
                st.error(f"Erro de validação: {exc}")
                st.stop()
            except RuntimeError as exc:
                progress.empty()
                st.error(f"Erro no processamento: {exc}")
                st.stop()

            claude_files = []
            for relative in result["claude_files"]:
                path = out_dir / relative
                claude_files.append((relative, path.read_text(encoding="utf-8")))

            report = (out_dir / "auditoria" / "relatorio_preprocessamento_pdf.md").read_text(encoding="utf-8")
            st.session_state.outputs = {
                "result": result,
                "claude_files": claude_files,
                "report_md": report,
            }

if st.session_state.outputs:
    data = st.session_state.outputs
    st.success("Processamento concluído.")

    st.subheader("Arquivos para anexar ao Claude")
    st.write("Em uso normal, anexe apenas os arquivos abaixo e chame a skill `pdf-crusher-context-reader`.")

    for name, content in data["claude_files"]:
        mime = "application/json" if name.endswith(".json") else "text/markdown"
        st.download_button(f"Baixar {name}", content, Path(name).name, mime)

    st.subheader("Pré-visualização")
    context_files = [item for item in data["claude_files"] if item[0].endswith(".md")]
    if context_files:
        selected = st.selectbox("Arquivo de contexto", context_files, format_func=lambda item: item[0])
        st.text_area("Conteúdo", selected[1], height=420)

    with st.expander("Relatório técnico local — não precisa anexar ao Claude"):
        st.markdown(data["report_md"])
