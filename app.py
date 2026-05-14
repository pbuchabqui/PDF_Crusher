"""Streamlit interface."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from pipeline import run_pipeline

st.set_page_config(page_title="PDF_Crusher", page_icon="⚡", layout="wide")
st.title("⚡ PDF_Crusher")
st.caption("Transforma PDFs jurídicos brasileiros densos em poucos arquivos de contexto para Claude/LLM via web.")

if "outputs" not in st.session_state:
    st.session_state.outputs = None

uploaded = st.file_uploader("Selecione o PDF", type=["pdf"])
use_groq = st.checkbox("Usar Groq para anonimizar nomes de pessoas", value=False)
groq_key = st.text_input("Groq API Key", type="password", disabled=not use_groq)

if uploaded and st.button("Processar PDF"):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pdf_path = tmp_path / uploaded.name
        out_dir = tmp_path / "outputs"
        pdf_path.write_bytes(uploaded.getbuffer())

        with st.spinner("Processando PDF e gerando Claude Pack em português brasileiro jurídico..."):
            result = run_pipeline(pdf_path, out_dir, use_groq=use_groq, groq_api_key=groq_key or None)

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
