from app.core.prompts.loader import load_prompt


def build_generation_prompt(query: str, chunks: list[dict]) -> str:
    """
    Build the RAG generation prompt.
    Uses generation_no_context.md when no chunks retrieved.
    Uses generation.md when chunks available.
    """
    if not chunks:
        template = load_prompt("generation_no_context")
        return template.format(query=query)

    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        context_parts.append(
            f"[Source {i}: {chunk['file_name']} chunk {chunk['chunk_index']}]\n"
            f"{chunk['chunk_text']}"
        )
    context = "\n\n".join(context_parts)

    template = load_prompt("generation")
    return template.format(query=query, context=context)


def build_faithfulness_prompt(answer: str, chunks: list[dict]) -> str:
    """Build the eval faithfulness judge prompt."""
    context = "\n\n".join([
        f"[Source: {c['file_name']} chunk {c['chunk_index']}]\n{c['chunk_text']}"
        for c in chunks
    ])
    template = load_prompt("faithfulness")
    return template.format(context=context, answer=answer)


def build_relevance_prompt(query: str, chunks: list[dict]) -> str:
    """Build the eval relevance judge prompt."""
    context = "\n\n".join([
        f"[Source: {c['file_name']} chunk {c['chunk_index']}]\n{c['chunk_text']}"
        for c in chunks
    ])
    template = load_prompt("relevance")
    return template.format(query=query, context=context)