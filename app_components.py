"""Reusable Streamlit render functions for PDF_Crusher."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import streamlit as st

_CONFIDENCE_LABEL = {
    "ALTO": "🟢 ALTO",
    "MÉDIO": "🟡 MÉDIO",
    "BAIXO": "🟠 BAIXO",
    "CRÍTICO": "🔴 CRÍTICO",
}

_ERROR_CONTEXT: dict[str, tuple[str, str]] = {
    "validation": (
        "Erro de validação do arquivo",
        "Verifique se o arquivo selecionado é um PDF válido e não está corrompido ou protegido por senha.",
    ),
    "groq": (
        "Erro na anonimização via Groq",
        "Verifique se a Groq API Key está correta e se há cota disponível. "
        "Você pode desmarcar a opção Groq e tentar novamente — a higienização por regex continuará ativa.",
    ),
    "processing": (
        "Erro no processamento do PDF",
        "O PDF pode estar criptografado, corrompido ou em formato não suportado pelo Docling. "
        "Tente remover a senha do PDF antes de processar, ou use outro arquivo.",
    ),
    "unexpected": (
        "Erro inesperado",
        "Um erro interno ocorreu. Reporte o problema com os detalhes técnicos abaixo.",
    ),
}

_AUDIT_LABELS: dict[str, tuple[str, str]] = {
    "auditoria/relatorio_preprocessamento_pdf.md": ("Relatório de pré-processamento", "text/markdown"),
    "auditoria/estrutura_pdf.json": ("Estrutura completa do PDF (JSON)", "application/json"),
    "auditoria/auditoria_pdf.json": ("Auditoria de páginas (JSON)", "application/json"),
    "auditoria/auditoria_privacidade.json": ("Auditoria de privacidade (JSON)", "application/json"),
    "auditoria/processo_higienizado.md": ("Texto higienizado (Markdown)", "text/markdown"),
    "auditoria/texto_extraido_bruto.txt": ("Texto extraído bruto (TXT)", "text/plain"),
}

_PAGE_TYPE_LABELS = [
    ("paginas_candidatas_decisoes", "Decisões judiciais"),
    ("paginas_candidatas_manifestacoes", "Petições / manifestações"),
    ("paginas_candidatas_provas", "Provas / documentos"),
    ("paginas_candidatas_audiencias", "Atas / audiências"),
    ("paginas_candidatas_calculos", "Cálculos / demonstrativos"),
    ("paginas_candidatas_documentos_trabalhistas", "Documentos trabalhistas"),
]


def _fmt_bytes(n: int) -> str:
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f} MB"
    if n >= 1_024:
        return f"{n / 1_024:.1f} KB"
    return f"{n} B"


# ── Header ────────────────────────────────────────────────────────────────────

def render_header() -> None:
    col_title, col_desc = st.columns([1, 3])
    with col_title:
        st.title("⚡ PDF_Crusher")
    with col_desc:
        st.caption(
            "Transforma PDFs jurídicos brasileiros densos em poucos arquivos de contexto "
            "para Claude/LLM — com higienização local de dados pessoais."
        )
    st.divider()


# ── Upload & Configuration ────────────────────────────────────────────────────

def render_upload_panel() -> dict:
    """Render the upload form with enhanced privacy and output options. Returns widget values as a dict."""
    uploaded = st.file_uploader(
        "Selecione o PDF jurídico",
        type=["pdf"],
        help="Apenas arquivos .pdf são aceitos.",
    )

    with st.expander("⚙️ Opções de Privacidade e Conformidade", expanded=False):
        st.markdown("**Anonimização de Dados Pessoais**")
        use_groq = st.checkbox(
            "Usar Groq para anonimizar nomes de pessoas",
            value=False,
            help="Além das máscaras regex locais (CPF, CNPJ, e-mail, telefone, RG, CNH, PIS/PASEP), "
                 "envia o texto já mascarado ao Groq para substituir nomes por [NOME_ANONIMIZADO].",
        )

        groq_key = None
        if use_groq:
            with st.container(border=True):
                groq_key = st.text_input(
                    "Groq API Key",
                    type="password",
                    placeholder="gsk_...",
                    help="Formato esperado: gsk_ seguido de 20+ caracteres alfanuméricos",
                )
                st.caption(
                    "Modelo: `llama-3.3-70b-versatile` · chunks de 30.000 chars · "
                    "até 3 tentativas com backoff · timeout de 60 s por chunk"
                )
        
        st.divider()
        st.markdown("**Conformidade LGPD**")
        data_residency = st.selectbox(
            "Residência de Dados",
            options=["brazil", "us", "eu"],
            index=0,
            help="Define onde os dados processados devem residir para conformidade com regulamentações locais.",
        )
        
        retention_days = st.number_input(
            "Dias de Retenção",
            min_value=1,
            max_value=3650,
            value=None,
            placeholder="Indefinido",
            help="Número máximo de dias para reter os dados processados. Deixe em branco para retenção indefinida.",
        )
        
        enable_audit = st.checkbox(
            "Habilitar Logs de Auditoria",
            value=True,
            help="Registra todas as operações em logs detalhados para rastreabilidade.",
        )

    with st.expander("📤 Opções de Exportação", expanded=False):
        output_format = st.selectbox(
            "Formato de Saída",
            options=["markdown", "json", "html", "txt"],
            index=0,
            help="Formato dos arquivos exportados.",
        )
        
        language = st.selectbox(
            "Idioma",
            options=["pt-BR", "en", "es"],
            index=0,
            help="Idioma preferencial para processamento e saída.",
        )

    submitted = st.button(
        "▶ Processar PDF",
        type="primary",
        disabled=uploaded is None,
        use_container_width=True,
    )

    return {
        "uploaded": uploaded,
        "use_groq": use_groq,
        "groq_key": groq_key,
        "submitted": submitted,
        "data_residency": data_residency,
        "retention_days": retention_days,
        "enable_audit_log": enable_audit,
        "output_format": output_format,
        "language": language,
    }


# ── Processing feedback ───────────────────────────────────────────────────────

def render_processing_steps(use_groq: bool) -> None:
    steps = [
        "Pré-processamento técnico do PDF (pypdf)",
        "Extração de texto e Markdown (Docling)",
        "Máscaras de privacidade — regex local (CPF, CNPJ, e-mail, telefone)",
    ]
    if use_groq:
        steps.append("Anonimização de nomes via Groq *(pode levar 1–2 min em documentos longos)*")
    steps.append("Geração do Claude Pack")

    items = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    st.info(f"**Etapas em execução:**\n\n{items}")


# ── Success banner ────────────────────────────────────────────────────────────

def render_success_banner(on_reset: Callable) -> None:
    col_msg, col_btn = st.columns([4, 1])
    with col_msg:
        st.success("PDF processado com sucesso! Baixe os arquivos abaixo e anexe ao Claude.")
    with col_btn:
        if st.button("Processar novo PDF", use_container_width=True):
            on_reset()
            st.rerun()


# ── Metrics strip ─────────────────────────────────────────────────────────────

def render_metrics_strip(structure: dict, privacy_audit: dict, claude_files: list) -> None:
    audit = structure["auditoria"]
    cls = structure["classificacao_tecnica"]
    arq = structure["arquivo"]

    n_md = sum(1 for name, _ in claude_files if name.endswith(".md"))
    confidence_display = _CONFIDENCE_LABEL.get(cls["confianca_global"], cls["confianca_global"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Páginas totais", audit["paginas_totais"])
    with c2:
        st.metric("Confiança global", confidence_display)
    with c3:
        st.metric("Tipo de PDF", cls["tipo_pdf"])
    with c4:
        st.metric(
            "Volumes gerados",
            n_md,
            help="Número de arquivos PDF_CRUSHER_CONTEXT*.md criados. Anexe todos ao Claude.",
        )

    with st.container(border=True):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown(f"**Arquivo:** `{arq['nome']}`")
        with col_b:
            st.markdown(f"**Tamanho:** {_fmt_bytes(arq['tamanho_bytes'])}")
        with col_c:
            ocr_status = "Sim ⚠️" if cls["necessita_ocr"] else "Não"
            st.markdown(f"**Necessita OCR:** {ocr_status}")


# ── Alerts ────────────────────────────────────────────────────────────────────

def render_alerts(structure: dict) -> None:
    alerts = structure.get("alertas", [])
    if not alerts:
        return
    with st.container(border=True):
        st.warning(f"**{len(alerts)} alerta(s) técnico(s) detectado(s)**")
        for alert in alerts:
            st.markdown(f"- {alert}")


# ── Page classification ───────────────────────────────────────────────────────

def render_page_classification(structure: dict) -> None:
    audit = structure["auditoria"]
    total = max(audit["paginas_totais"], 1)

    non_zero = [(label, audit[key]) for key, label in _PAGE_TYPE_LABELS if audit.get(key, 0) > 0]

    with st.expander("Classificação de páginas candidatas", expanded=True):
        if not non_zero:
            st.info("Nenhuma página com tipo específico detectado.")
            return

        for label, count in non_zero:
            col_label, col_bar, col_count = st.columns([3, 5, 1])
            with col_label:
                st.markdown(f"**{label}**")
            with col_bar:
                st.progress(min(count / total, 1.0))
            with col_count:
                st.markdown(f"`{count}`")


# ── Privacy summary ───────────────────────────────────────────────────────────

def render_privacy_summary(privacy_audit: dict) -> None:
    first = privacy_audit["regex_primeira_passada"]
    final = privacy_audit["regex_passada_final"]
    groq_used = privacy_audit["groq_usado_para_nomes"]
    
    # Calculate totals for all PII types
    total_cpf = first.get("cpf", 0) + final.get("cpf", 0)
    total_cnpj = first.get("cnpj", 0) + final.get("cnpj", 0)
    total_email = first.get("email", 0) + final.get("email", 0)
    total_telefone = first.get("telefone", 0) + final.get("telefone", 0)
    total_rg = first.get("rg", 0) + final.get("rg", 0)
    total_cnh = first.get("cnh", 0) + final.get("cnh", 0)
    total_pis = first.get("pis_pasep", 0) + final.get("pis_pasep", 0)
    total_cep = first.get("cep", 0) + final.get("cep", 0)

    with st.container(border=True):
        st.markdown("**Dados pessoais mascarados**")
        
        # First row - Core identifiers
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("CPF", total_cpf, help="Substituídos por [CPF_ANONIMIZADO]")
        with c2:
            st.metric("CNPJ", total_cnpj, help="Substituídos por [CNPJ_ANONIMIZADO]")
        with c3:
            st.metric("RG", total_rg, help="Substituídos por [RG_ANONIMIZADO]")
        with c4:
            st.metric("CNH", total_cnh, help="Substituídos por [CNH_ANONIMIZADA]")
        
        # Second row - Contact and other identifiers
        c5, c6, c7, c8 = st.columns(4)
        with c5:
            st.metric("E-mail", total_email, help="Substituídos por [EMAIL_ANONIMIZADO]")
        with c6:
            st.metric("Telefone", total_telefone, help="Substituídos por [TELEFONE_ANONIMIZADO]")
        with c7:
            st.metric("PIS/PASEP", total_pis, help="Substituídos por [PIS_PASEP_ANONIMIZADO]")
        with c8:
            st.metric("CEP", total_cep, help="Substituídos por [CEP_ANONIMIZADO]")
        
        # Third row - Groq and summary
        st.divider()
        c9, c10 = st.columns(2)
        with c9:
            st.metric(
                "Groq (nomes)",
                "Sim" if groq_used else "Não",
                help="Se Sim, nomes de pessoas foram substituídos por [NOME_ANONIMIZADO]",
            )
        with c10:
            total_all = total_cpf + total_cnpj + total_email + total_telefone + total_rg + total_cnh + total_pis + total_cep
            st.metric(
                "Total de Máscaras",
                total_all,
                help="Total geral de dados pessoais mascarados",
            )


# ── Downloads ─────────────────────────────────────────────────────────────────

def render_downloads(claude_files: list, result: dict, out_dir: Path) -> None:
    st.subheader("Arquivos para o Claude")
    st.caption(
        "Anexe **apenas estes arquivos** ao Claude e use a skill `pdf-crusher-context-reader`. "
        "Não é necessário enviar os arquivos de auditoria."
    )

    n_context = sum(1 for name, _ in claude_files if name.endswith(".md"))

    if n_context == 0:
        st.warning("Nenhum arquivo de contexto gerado. Verifique o relatório técnico.")
    elif n_context > 1:
        st.info(f"O PDF foi dividido em **{n_context} volumes**. Anexe todos ao Claude.")

    for name, content in claude_files:
        filename = Path(name).name
        mime = "application/json" if name.endswith(".json") else "text/markdown"
        icon = "📋" if name.endswith(".json") else "📄"
        desc = "Manifesto JSON" if name.endswith(".json") else f"{len(content):,} caracteres"

        col_icon, col_desc, col_btn = st.columns([0.5, 6, 2])
        with col_icon:
            st.write(icon)
        with col_desc:
            st.markdown(f"**{filename}**  \n`{desc}`")
        with col_btn:
            st.download_button(
                label="Baixar",
                data=content,
                file_name=filename,
                mime=mime,
                key=f"dl_claude_{filename}",
                use_container_width=True,
            )

    st.divider()

    with st.expander("Arquivos de auditoria local — não enviar ao Claude"):
        st.caption(
            "Estes arquivos ficam em sua máquina para conferência humana. "
            "Não precisam ser anexados ao Claude em uso normal."
        )
        for relative in result["audit_files"]:
            path = out_dir / relative
            if not path.exists():
                continue
            label, mime = _AUDIT_LABELS.get(relative, (Path(relative).name, "text/plain"))
            content = path.read_bytes()
            col_desc, col_btn = st.columns([6, 2])
            with col_desc:
                st.markdown(f"**{Path(relative).name}**  \n{label}")
            with col_btn:
                st.download_button(
                    label="Baixar",
                    data=content,
                    file_name=Path(relative).name,
                    mime=mime,
                    key=f"dl_audit_{Path(relative).name}",
                    use_container_width=True,
                )


# ── File preview ──────────────────────────────────────────────────────────────

def render_file_preview(claude_files: list) -> None:
    md_files = [(name, content) for name, content in claude_files if name.endswith(".md")]
    if not md_files:
        return

    st.subheader("Pré-visualização dos arquivos de contexto")

    if len(md_files) == 1:
        name, content = md_files[0]
        st.markdown(f"`{Path(name).name}` · {len(content):,} caracteres")
        st.text_area(
            "Conteúdo",
            content,
            height=420,
            label_visibility="collapsed",
        )
    else:
        tab_labels = [Path(name).name for name, _ in md_files]
        tabs = st.tabs(tab_labels)
        for tab, (name, content) in zip(tabs, md_files):
            with tab:
                st.markdown(f"`{Path(name).name}` · {len(content):,} caracteres")
                st.text_area(
                    "Conteúdo",
                    content,
                    height=420,
                    label_visibility="collapsed",
                    key=f"preview_{Path(name).name}",
                )


# ── Technical report ──────────────────────────────────────────────────────────

def render_technical_report(report_md: str) -> None:
    with st.expander("Relatório técnico completo (auditoria local)", expanded=False):
        st.markdown(report_md)


# ── Error panel ───────────────────────────────────────────────────────────────

def render_error_panel(error_msg: str, error_type: str, on_reset: Callable) -> None:
    title, suggestion = _ERROR_CONTEXT.get(error_type, _ERROR_CONTEXT["unexpected"])
    st.error(f"**{title}**\n\n{suggestion}")
    with st.expander("Detalhes técnicos do erro"):
        st.code(error_msg)
    if st.button("Tentar novamente com outro arquivo", type="primary"):
        on_reset()
        st.rerun()
