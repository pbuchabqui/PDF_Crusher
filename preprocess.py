"""Technical preprocessor for Brazilian legal PDFs: traceability, simple detection, reports."""

from __future__ import annotations

import json
from pathlib import Path

from pdf_engine import extract_page_texts, pdf_info

SUMMARY_TERMS = [
    "ÍNDICE", "INDICE", "SUMÁRIO", "SUMARIO", "RELAÇÃO DE DOCUMENTOS", "RELACAO DE DOCUMENTOS",
    "DOCUMENTOS DO PROCESSO", "LISTAGEM DE DOCUMENTOS", "LISTA DE DOCUMENTOS", "MOVIMENTAÇÕES", "MOVIMENTACOES",
]
DECISION_TERMS = [
    "JULGO", "CONDENO", "DEFIRO", "INDEFIRO", "ACORDAM", "DOU PROVIMENTO", "NEGO PROVIMENTO",
    "HOMOLOGO", "DECIDO", "DETERMINO", "EXTINGO", "REJEITO", "ACOLHO", "ABSOLVO",
    "SENTENÇA", "SENTENCA", "ACÓRDÃO", "ACORDAO", "DECISÃO", "DECISAO", "DESPACHO",
    "ANTE O EXPOSTO", "DISPOSITIVO",
]
PETITION_TERMS = [
    "PETIÇÃO", "PETICAO", "MANIFESTAÇÃO", "MANIFESTACAO", "CONTESTAÇÃO", "CONTESTACAO", "RÉPLICA", "REPLICA",
    "RECURSO", "APELAÇÃO", "APELACAO", "AGRAVO", "EMBARGOS", "IMPUGNAÇÃO", "IMPUGNACAO",
    "REQUER", "REQUERIMENTO", "RAZÕES", "RAZOES", "CONTRARRAZÕES", "CONTRARRAZOES",
]
EVIDENCE_TERMS = [
    "CONTRATO", "INSTRUMENTO", "COMPROVANTE", "RECIBO", "EXTRATO", "NOTA FISCAL", "NF-E", "NFE",
    "CERTIDÃO", "CERTIDAO", "PROCURAÇÃO", "PROCURACAO", "SUBSTABELECIMENTO", "LAUDO", "PERÍCIA", "PERICIA",
    "PARECER", "BOLETIM DE OCORRÊNCIA", "BOLETIM DE OCORRENCIA", "DECLARAÇÃO", "DECLARACAO", "DOCUMENTO",
]
HEARING_TERMS = [
    "ATA DE AUDIÊNCIA", "ATA DE AUDIENCIA", "TERMO DE AUDIÊNCIA", "TERMO DE AUDIENCIA", "DEPOIMENTO",
    "TESTEMUNHA", "INTERROGATÓRIO", "INTERROGATORIO", "AUDIÊNCIA", "AUDIENCIA",
]
CALC_TERMS = [
    "DEMONSTRATIVO", "MEMÓRIA DE CÁLCULO", "MEMORIA DE CALCULO", "PLANILHA", "ATUALIZAÇÃO", "ATUALIZACAO",
    "JUROS", "CORREÇÃO MONETÁRIA", "CORRECAO MONETARIA", "PRINCIPAL", "DÉBITO", "DEBITO", "VALOR DA CAUSA",
    "INPC", "IPCA-E", "IPCA", "SELIC", "CUSTAS", "HONORÁRIOS", "HONORARIOS",
]
LABOR_TERMS = [
    "CARTÃO-PONTO", "CARTAO-PONTO", "ESPELHO DE PONTO", "HOLERITE", "CONTRACHEQUE", "FICHA FINANCEIRA",
    "SALÁRIO BASE", "SALARIO BASE", "FGTS", "INSS", "IRRF", "RUBRICA", "COMPETÊNCIA", "COMPETENCIA",
]

LABEL_DECISION = "página candidata a conter decisão judicial"
LABEL_PETITION = "possível petição/manifestação"
LABEL_EVIDENCE = "possível prova/documento"
LABEL_HEARING = "possível ata/audiência/depoimento"
LABEL_CALC = "possível cálculo/demonstrativo"
LABEL_LABOR = "possível documento trabalhista"


def _has_any(text: str, terms: list[str]) -> bool:
    upper = text.upper()
    return any(term.upper() in upper for term in terms)


def _confidence(text: str) -> str:
    size = len(text.strip())
    if size >= 500:
        return "ALTO"
    if size >= 100:
        return "MÉDIO"
    if size > 0:
        return "BAIXO"
    return "CRÍTICO"


def _possible_types(text: str) -> list[str]:
    labels = []
    if _has_any(text, DECISION_TERMS):
        labels.append(LABEL_DECISION)
    if _has_any(text, PETITION_TERMS):
        labels.append(LABEL_PETITION)
    if _has_any(text, EVIDENCE_TERMS):
        labels.append(LABEL_EVIDENCE)
    if _has_any(text, HEARING_TERMS):
        labels.append(LABEL_HEARING)
    if _has_any(text, CALC_TERMS):
        labels.append(LABEL_CALC)
    if _has_any(text, LABOR_TERMS):
        labels.append(LABEL_LABOR)
    return labels


def _global_confidence(page_confidences: list[str]) -> str:
    total = max(len(page_confidences), 1)
    weak = sum(c in {"BAIXO", "CRÍTICO"} for c in page_confidences)
    critical = page_confidences.count("CRÍTICO")
    if critical / total > 0.5:
        return "CRÍTICO"
    if weak / total > 0.25:
        return "BAIXO"
    if weak:
        return "MÉDIO"
    return "ALTO"


def build_preprocess(pdf_path: str | Path) -> tuple[dict, str]:
    info = pdf_info(pdf_path)
    page_texts = extract_page_texts(pdf_path)

    pages = []
    raw_parts = []
    for index, text in enumerate(page_texts, start=1):
        confidence = _confidence(text)
        labels = _possible_types(text)
        pages.append({
            "pagina_pdf": index,
            "texto_extraivel": bool(text.strip()),
            "ocr_aplicado": False,
            "confianca": confidence,
            "possiveis_tipos": labels,
            "alertas": [] if text.strip() else ["Página sem texto extraível por pypdf."],
        })
        raw_parts.append(f"=== PÁGINA PDF {index:04d} ===\n{text.strip()}\n")

    search_from = max(len(page_texts) - 50, 0)
    summary_pages = [i + 1 for i, text in enumerate(page_texts[search_from:], start=search_from) if _has_any(text, SUMMARY_TERMS)]
    page_confidences = [p["confianca"] for p in pages]
    global_confidence = _global_confidence(page_confidences)

    text_pages = sum(p["texto_extraivel"] for p in pages)
    if text_pages == 0:
        pdf_type = "PDF escaneado ou sem texto extraível"
    elif text_pages < len(pages):
        pdf_type = "PDF híbrido"
    else:
        pdf_type = "PDF textual nativo"

    audit = {
        "paginas_totais": len(pages),
        "paginas_texto_nativo": text_pages,
        "paginas_sem_texto": len(pages) - text_pages,
        "paginas_baixa_confianca": sum(c == "BAIXO" for c in page_confidences),
        "paginas_criticas": sum(c == "CRÍTICO" for c in page_confidences),
        "paginas_candidatas_decisoes": sum(LABEL_DECISION in p["possiveis_tipos"] for p in pages),
        "paginas_candidatas_manifestacoes": sum(LABEL_PETITION in p["possiveis_tipos"] for p in pages),
        "paginas_candidatas_provas": sum(LABEL_EVIDENCE in p["possiveis_tipos"] for p in pages),
        "paginas_candidatas_audiencias": sum(LABEL_HEARING in p["possiveis_tipos"] for p in pages),
        "paginas_candidatas_calculos": sum(LABEL_CALC in p["possiveis_tipos"] for p in pages),
        "paginas_candidatas_documentos_trabalhistas": sum(LABEL_LABOR in p["possiveis_tipos"] for p in pages),
        "sumario_detectado": bool(summary_pages),
    }

    alerts = []
    if global_confidence in {"BAIXO", "CRÍTICO"}:
        alerts.append("A confiabilidade técnica do PDF é insuficiente para uso automático seguro; revisar páginas indicadas.")
    if not summary_pages:
        alerts.append("Sumário/índice processual não detectado nas páginas finais.")

    structure = {
        "arquivo": info,
        "escopo_juridico": "direito brasileiro em geral",
        "idioma_preferencial": "português brasileiro",
        "classificacao_tecnica": {
            "tipo_pdf": pdf_type,
            "confianca_global": global_confidence,
            "necessita_ocr": text_pages < len(pages),
            "possui_sumario": bool(summary_pages),
        },
        "sumario": {
            "detectado": bool(summary_pages),
            "paginas_pdf": summary_pages,
            "confianca": "ALTO" if summary_pages else "NAO_LOCALIZADO",
        },
        "paginas": pages,
        "auditoria": audit,
        "alertas": alerts,
    }
    return structure, "\n".join(raw_parts)


def write_preprocess_outputs(output_dir: str | Path, structure: dict, raw_text: str) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "texto_extraido_bruto.txt").write_text(raw_text, encoding="utf-8")
    (out / "estrutura_pdf.json").write_text(json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "auditoria_pdf.json").write_text(json.dumps(structure["auditoria"], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "relatorio_preprocessamento_pdf.md").write_text(build_report(structure), encoding="utf-8")


def build_report(structure: dict) -> str:
    audit = structure["auditoria"]
    cls = structure["classificacao_tecnica"]
    alerts = structure.get("alertas", [])
    return f"""# Relatório de Pré-Processamento do PDF

## 1. Dados do Arquivo

- Arquivo: {structure['arquivo']['nome']}
- Páginas: {audit['paginas_totais']}
- Tamanho: {structure['arquivo']['tamanho_bytes']} bytes
- Escopo jurídico: {structure.get('escopo_juridico', 'direito brasileiro em geral')}
- Idioma preferencial: {structure.get('idioma_preferencial', 'português brasileiro')}

## 2. Classificação Técnica

- Tipo: {cls['tipo_pdf']}
- Confiança global: {cls['confianca_global']}
- Necessita OCR: {cls['necessita_ocr']}

## 3. Sumário / Índice Processual

- Detectado: {structure['sumario']['detectado']}
- Páginas PDF: {structure['sumario']['paginas_pdf']}

## 4. Páginas Candidatas

- Decisões judiciais: {audit['paginas_candidatas_decisoes']}
- Petições/manifestações/recursos: {audit['paginas_candidatas_manifestacoes']}
- Provas/documentos: {audit['paginas_candidatas_provas']}
- Atas/audiências/depoimentos: {audit['paginas_candidatas_audiencias']}
- Cálculos/demonstrativos: {audit['paginas_candidatas_calculos']}
- Documentos trabalhistas: {audit['paginas_candidatas_documentos_trabalhistas']}

## 5. Auditoria Técnica

```json
{json.dumps(audit, ensure_ascii=False, indent=2)}
```

## 6. Alertas

{chr(10).join(f'- {a}' for a in alerts) if alerts else '- Nenhum alerta crítico.'}

## 7. Nota

Este relatório é técnico e preliminar. Ele é aplicável a processos judiciais brasileiros em geral, não interpreta decisões, não define teses, não cria critérios jurídicos e não substitui conferência humana.
"""
