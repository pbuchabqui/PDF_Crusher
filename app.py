"""Streamlit interface."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from pipeline import run_pipeline

st.set_page_config(page_title="PDF_Crusher", page_icon="⚡", layout="wide")
st.title("⚡ PDF_Crusher")
st.caption("Transforma PDFs jurídicos brasileiros densos em contexto higienizado e fracionado para LLM via web.")

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

        with st.spinner("Processando PDF e gerando contexto jurídico em português brasileiro para LLM..."):
            result = run_pipeline(pdf_path, out_dir, use_groq=use_groq, groq_api_key=groq_key or None)

        chunk_files = sorted((out_dir / "chunks").glob("parte_*.md"))
        st.session_state.outputs = {
            "result": result,
            "final_md": (out_dir / "processo_higienizado.md").read_text(encoding="utf-8"),
            "guide_md": (out_dir / "guia_uso_llm.md").read_text(encoding="utf-8"),
            "report_md": (out_dir / "relatorio_preprocessamento_pdf.md").read_text(encoding="utf-8"),
            "structure_json": (out_dir / "estrutura_pdf.json").read_text(encoding="utf-8"),
            "chunks": [(path.name, path.read_text(encoding="utf-8")) for path in chunk_files],
        }

if st.session_state.outputs:
    data = st.session_state.outputs
    st.success("Processamento concluído.")
    st.json(data["result"]["privacy_audit"])

    st.subheader("Arquivos principais")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button("Baixar guia_uso_llm.md", data["guide_md"], "guia_uso_llm.md", "text/markdown")
    with col2:
        st.download_button("Baixar processo_higienizado.md", data["final_md"], "processo_higienizado.md", "text/markdown")
    with col3:
        st.download_button("Baixar estrutura_pdf.json", data["structure_json"], "estrutura_pdf.json", "application/json")

    st.subheader("Copiar blocos para ChatGPT / Claude")
    selected = st.selectbox("Bloco", data["chunks"], format_func=lambda item: item[0])
    st.text_area("Conteúdo do bloco selecionado", selected[1], height=420)
    st.download_button("Baixar bloco selecionado", selected[1], selected[0], "text/markdown")

    with st.expander("Relatório de pré-processamento"):
        st.markdown(data["report_md"])
