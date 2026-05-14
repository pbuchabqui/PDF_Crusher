# ⚡ PDF_Crusher

Ferramenta local em Python para transformar PDFs jurídicos densos em contexto higienizado, fracionado e mais digerível para uso em LLMs via web, com foco no **direito brasileiro** e em **português brasileiro**.

O projeto é neutro quanto à área jurídica. Pode ser usado, com revisão humana, em documentos cíveis, trabalhistas, previdenciários, tributários, criminais, empresariais, administrativos, consumeristas, família/sucessões e outras áreas do direito brasileiro.

O projeto faz somente pré-processamento técnico:

- extrai texto e Markdown;
- preserva rastreabilidade por página no texto bruto;
- aplica máscara local em CPF, CNPJ, e-mail e telefone;
- opcionalmente usa Groq para substituir nomes de pessoas por `[NOME_ANONIMIZADO]`;
- gera um **Claude Pack** com poucos arquivos para anexação direta;
- mantém relatório técnico, JSON de estrutura e auditoria em pasta separada para conferência local.

O projeto **não interpreta decisões**, **não define teses jurídicas**, **não cria critérios decisórios** e **não realiza cálculos**.

---

## Saídas geradas

A saída principal agora é o **Claude Pack**, para reduzir a quantidade de anexos.

```text
outputs/
├── claude/
│   ├── PDF_CRUSHER_CONTEXT.md
│   └── PDF_CRUSHER_MANIFEST.json
└── auditoria/
    ├── processo_higienizado.md
    ├── texto_extraido_bruto.txt
    ├── estrutura_pdf.json
    ├── auditoria_pdf.json
    ├── auditoria_privacidade.json
    └── relatorio_preprocessamento_pdf.md
```

Se o contexto ficar grande demais para um único arquivo, o PDF_Crusher gera volumes:

```text
outputs/claude/
├── PDF_CRUSHER_CONTEXT_001.md
├── PDF_CRUSHER_CONTEXT_002.md
├── PDF_CRUSHER_CONTEXT_003.md
└── PDF_CRUSHER_MANIFEST.json
```

---

## Contexto otimizado para LLM

Em uso normal, anexe ao Claude apenas os arquivos em `outputs/claude/`.

Cada `PDF_CRUSHER_CONTEXT*.md` contém:

- identificação do arquivo original;
- escopo jurídico: direito brasileiro em geral;
- idioma preferencial: português brasileiro;
- resumo técnico do PDF;
- confiança global;
- alertas técnicos;
- auditoria resumida;
- auditoria de privacidade;
- páginas candidatas a decisões, petições/manifestações, provas/documentos, atas/audiências, cálculos e documentos trabalhistas;
- instruções para uso com a skill `pdf-crusher-context-reader`;
- conteúdo extraído e higienizado.

Os arquivos em `outputs/auditoria/` são para conferência local e não precisam ser anexados ao Claude no fluxo comum.

---

## Instalação

```bash
git clone https://github.com/SEU_USUARIO/PDF_Crusher.git
cd PDF_Crusher
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

Depois:

```bash
pip install -r requirements.txt
```

---

## Uso pela interface

```bash
streamlit run app.py
```

A interface permite processar o PDF e baixar diretamente os arquivos mínimos do Claude Pack.

---

## Uso por linha de comando

Sem Groq:

```bash
python cli.py processo.pdf -o outputs
```

Com Groq para anonimizar nomes:

```bash
python cli.py processo.pdf -o outputs --groq --groq-api-key SUA_CHAVE
```

Ou usando variável de ambiente:

```bash
set GROQ_API_KEY=SUA_CHAVE
python cli.py processo.pdf -o outputs --groq
```

---

## Privacidade

A primeira e a última passadas de higienização são locais, por Regex.

A etapa Groq é opcional. Se ativada, o texto já mascarado localmente é enviado à API para substituição contextual de nomes de pessoas.

Use com revisão humana. Este projeto reduz risco, mas não garante anonimização irreversível nem conformidade automática com a LGPD.

---

## Escopo do MVP

Incluído:

- extração por página com `pypdf`;
- extração Markdown com Docling;
- detecção preliminar de páginas candidatas a decisões, petições/manifestações, provas/documentos, audiências, cálculos e documentos trabalhistas;
- busca simples de sumário/índice processual nas páginas finais;
- relatório e JSON técnico;
- Claude Pack com poucos arquivos de contexto em português brasileiro.

Fora do MVP:

- interpretação jurídica;
- análise de mérito;
- cálculo judicial;
- separação física de PDFs por bloco;
- extração de tabelas para XLSX;
- garantia automática de anonimização perfeita.

---

## Skill para Claude

Este repositório inclui uma skill opcional para Claude em:

```text
claude_skill/pdf-crusher-context-reader/SKILL.md
```

A skill serve para ensinar o método fixo de leitura dos arquivos gerados pelo PDF_Crusher, evitando repetir instruções a cada novo processo.

Para uso no Claude, faça upload do arquivo:

```text
pdf-crusher-context-reader-skill.zip
```

Depois anexe os arquivos da pasta `outputs/claude/` e peça:

```text
Use a skill pdf-crusher-context-reader para analisar os arquivos anexos do PDF_Crusher em português brasileiro.
```

A skill agora é geral para o direito brasileiro. O antigo modo trabalhista foi preservado como submodo especializado para liquidação trabalhista, sem afetar o núcleo do PDF_Crusher.


## Deploy no Streamlit Community Cloud

Este projeto inclui dois arquivos para reduzir falhas comuns no deploy com Docling/OpenCV:

- `packages.txt`: instala as bibliotecas Linux que fornecem `libGL.so.1` e `libgthread-2.0.so.0`, necessárias para dependências que usam OpenCV no runtime atual do Streamlit.
- `.streamlit/config.toml`: desativa o file watcher do Streamlit para evitar inspeção excessiva de módulos pesados como `transformers` durante o deploy.

No Streamlit Community Cloud, recomenda-se selecionar Python 3.12 nas configurações avançadas do app. PDFs grandes e OCR continuam sendo mais seguros em execução local.
