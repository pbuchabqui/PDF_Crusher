"""Text splitting without cutting words when possible."""


def split_text(text: str, max_chars: int = 70000) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")

    chunks = []
    remaining = text or ""

    while len(remaining) > max_chars:
        window = remaining[:max_chars]
        cut = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(" "))
        if cut <= 0:
            cut = max_chars
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].lstrip()

    if remaining.strip():
        chunks.append(remaining.strip())

    return chunks
