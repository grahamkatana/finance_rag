from app.core.llm.base import BaseLLM, BaseEmbedder


def get_llm(
    provider: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
) -> BaseLLM:
    """
    Single entry point for all generation providers.

    provider: ollama | openai | groq | deepseek | grok | gemini | mistral
    model:    model name specific to the provider
    api_key:  required for all cloud providers
    base_url: required for ollama, optional override for openai-compatible

    OpenAI-compatible providers (groq, deepseek, grok) share
    the openai provider file — base_url routes them correctly.
    """
    if provider == "ollama":
        from app.core.llm.providers.ollama import OllamaLLM
        return OllamaLLM(
            base_url=base_url or "http://localhost:11434",
            model=model,
        )

    if provider in ("openai", "groq", "deepseek", "grok", "mistral"):
        from app.core.llm.providers.openai import (
            OpenAICompatibleLLM,
            OPENAI_COMPATIBLE_PROVIDERS,
        )
        # Look up known base_url or use provided one
        resolved_url = (
            base_url or
            OPENAI_COMPATIBLE_PROVIDERS.get(provider, {}).get("base_url")
        )
        return OpenAICompatibleLLM(
            api_key=api_key,
            model=model,
            provider=provider,
            base_url=resolved_url,
        )

    if provider == "gemini":
        from app.core.llm.providers.gemini import GeminiLLM
        return GeminiLLM(
            api_key=api_key,
            model=model,
        )

    raise ValueError(
        f"Unknown LLM provider: '{provider}'. "
        f"Valid options: ollama, openai, groq, deepseek, grok, gemini, mistral"
    )


def get_embedder(
    provider: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
) -> BaseEmbedder:
    """
    Single entry point for all embedding providers.

    provider: ollama | openai | groq | gemini | mistral | voyage
    model:    embedding model name specific to the provider

    Note: groq, deepseek, and grok do NOT support embeddings.
    Use a different embed provider when using those for generation.
    """
    if provider == "ollama":
        from app.core.llm.providers.ollama import OllamaEmbedder
        return OllamaEmbedder(
            base_url=base_url or "http://localhost:11434",
            model=model,
        )

    if provider == "openai":
        from app.core.llm.providers.openai import OpenAIEmbedder
        return OpenAIEmbedder(
            api_key=api_key,
            model=model,
            provider="openai",
        )

    if provider == "groq":
        from app.core.llm.providers.openai import OpenAIEmbedder
        return OpenAIEmbedder(
            api_key=api_key,
            model=model,
            provider="groq",
            base_url="https://api.groq.com/openai/v1",
        )

    if provider == "gemini":
        from app.core.llm.providers.gemini import GeminiEmbedder
        return GeminiEmbedder(
            api_key=api_key,
            model=model,
        )

    if provider == "mistral":
        from app.core.llm.providers.mistral import MistralEmbedder
        return MistralEmbedder(
            api_key=api_key,
            model=model,
        )

    if provider == "voyage":
        from app.core.llm.providers.voyage import VoyageEmbedder
        return VoyageEmbedder(
            api_key=api_key,
            model=model,
        )

    raise ValueError(
        f"Unknown embedder provider: '{provider}'. "
        f"Valid options: ollama, openai, groq, gemini, mistral, voyage"
    )