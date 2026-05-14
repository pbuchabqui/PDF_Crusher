"""Optional name anonymization through Groq."""

SYSTEM_PROMPT = """Você é um higienizador de dados pessoais para textos jurídicos brasileiros em português brasileiro.
Substitua apenas nomes de pessoas físicas por [NOME_ANONIMIZADO].
Inclua partes, advogados, testemunhas, peritos, magistrados, servidores, delegados, promotores e defensores.
Não altere números de páginas, IDs, valores, datas, formatação Markdown, citações legais ou sentido do texto.
Responda somente com o texto higienizado."""


def anonymize_names(text: str, api_key: str, model: str = "llama-3.3-70b-versatile") -> str:
    try:
        from groq import Groq
    except ModuleNotFoundError as exc:
        raise RuntimeError("Groq não está instalado. Instale com `pip install groq` para usar anonimização por IA.") from exc

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )
    return response.choices[0].message.content or ""
