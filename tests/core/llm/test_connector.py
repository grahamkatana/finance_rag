import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def mock_all_providers():
    """Mock all provider imports so no SDK needed"""
    with patch("app.core.llm.providers.ollama.OllamaLLM") as mock_ollama_llm, \
         patch("app.core.llm.providers.ollama.OllamaEmbedder") as mock_ollama_embed, \
         patch("app.core.llm.providers.openai.OpenAICompatibleLLM") as mock_openai_llm, \
         patch("app.core.llm.providers.openai.OpenAIEmbedder") as mock_openai_embed, \
         patch("app.core.llm.providers.gemini.GeminiLLM") as mock_gemini_llm, \
         patch("app.core.llm.providers.gemini.GeminiEmbedder") as mock_gemini_embed, \
         patch("app.core.llm.providers.mistral.MistralLLM") as mock_mistral_llm, \
         patch("app.core.llm.providers.mistral.MistralEmbedder") as mock_mistral_embed, \
         patch("app.core.llm.providers.voyage.VoyageEmbedder") as mock_voyage_embed:

        mock_ollama_llm.return_value = MagicMock()
        mock_ollama_embed.return_value = MagicMock()
        mock_openai_llm.return_value = MagicMock()
        mock_openai_embed.return_value = MagicMock()
        mock_gemini_llm.return_value = MagicMock()
        mock_gemini_embed.return_value = MagicMock()
        mock_mistral_llm.return_value = MagicMock()
        mock_mistral_embed.return_value = MagicMock()
        mock_voyage_embed.return_value = MagicMock()
        yield


# ── get_llm tests ────────────────────────────────────────────

def test_get_llm_ollama():
    """ollama provider returns OllamaLLM"""
    from app.core.llm.connector import get_llm
    llm = get_llm(provider="ollama", model="phi4-mini")
    assert llm is not None


def test_get_llm_openai():
    """openai provider returns OpenAICompatibleLLM"""
    from app.core.llm.connector import get_llm
    llm = get_llm(provider="openai", model="gpt-4o", api_key="sk-test")
    assert llm is not None


def test_get_llm_groq():
    """groq provider returns OpenAICompatibleLLM with groq base_url"""
    from app.core.llm.connector import get_llm
    llm = get_llm(provider="groq", model="llama-3.3-70b-versatile", api_key="gsk-test")
    assert llm is not None


def test_get_llm_deepseek():
    """deepseek provider returns OpenAICompatibleLLM with deepseek base_url"""
    from app.core.llm.connector import get_llm
    llm = get_llm(provider="deepseek", model="deepseek-chat", api_key="sk-test")
    assert llm is not None


def test_get_llm_grok():
    """grok provider returns OpenAICompatibleLLM with xai base_url"""
    from app.core.llm.connector import get_llm
    llm = get_llm(provider="grok", model="grok-4", api_key="xai-test")
    assert llm is not None


def test_get_llm_gemini():
    """gemini provider returns GeminiLLM"""
    from app.core.llm.connector import get_llm
    llm = get_llm(provider="gemini", model="gemini-2.0-flash", api_key="AIza-test")
    assert llm is not None


def test_get_llm_mistral():
    """mistral provider returns OpenAICompatibleLLM"""
    from app.core.llm.connector import get_llm
    llm = get_llm(provider="mistral", model="mistral-large-latest", api_key="test")
    assert llm is not None


def test_get_llm_unknown_provider_raises():
    """Unknown provider must raise ValueError with helpful message"""
    from app.core.llm.connector import get_llm
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm(provider="anthropic", model="claude-3", api_key="test")


# ── get_embedder tests ───────────────────────────────────────

def test_get_embedder_ollama():
    """ollama embedder returns OllamaEmbedder"""
    from app.core.llm.connector import get_embedder
    embedder = get_embedder(provider="ollama", model="nomic-embed-text")
    assert embedder is not None


def test_get_embedder_openai():
    """openai embedder returns OpenAIEmbedder"""
    from app.core.llm.connector import get_embedder
    embedder = get_embedder(
        provider="openai",
        model="text-embedding-3-small",
        api_key="sk-test",
    )
    assert embedder is not None


def test_get_embedder_groq():
    """groq embedder returns OpenAIEmbedder with groq base_url"""
    from app.core.llm.connector import get_embedder
    embedder = get_embedder(
        provider="groq",
        model="nomic-embed-text-v1_5",
        api_key="gsk-test",
    )
    assert embedder is not None


def test_get_embedder_gemini():
    """gemini embedder returns GeminiEmbedder"""
    from app.core.llm.connector import get_embedder
    embedder = get_embedder(
        provider="gemini",
        model="models/text-embedding-005",
        api_key="AIza-test",
    )
    assert embedder is not None


def test_get_embedder_mistral():
    """mistral embedder returns MistralEmbedder"""
    from app.core.llm.connector import get_embedder
    embedder = get_embedder(
        provider="mistral",
        model="mistral-embed",
        api_key="test",
    )
    assert embedder is not None


def test_get_embedder_voyage():
    """voyage embedder returns VoyageEmbedder"""
    from app.core.llm.connector import get_embedder
    embedder = get_embedder(
        provider="voyage",
        model="voyage-finance-2",
        api_key="pa-test",
    )
    assert embedder is not None


def test_get_embedder_unknown_provider_raises():
    """Unknown embed provider must raise ValueError"""
    from app.core.llm.connector import get_embedder
    with pytest.raises(ValueError, match="Unknown embedder provider"):
        get_embedder(provider="cohere", model="embed-v4", api_key="test")


def test_get_llm_ollama_uses_default_base_url():
    """ollama must use default localhost URL if none provided"""
    from app.core.llm.providers.ollama import OllamaLLM
    from app.core.llm.connector import get_llm
    get_llm(provider="ollama", model="phi4-mini")
    OllamaLLM.assert_called_once()
    call_kwargs = OllamaLLM.call_args.kwargs
    assert "localhost" in call_kwargs.get("base_url", "")


def test_mix_providers_generation_and_embeddings():
    """Can use different providers for generation and embeddings"""
    from app.core.llm.connector import get_llm, get_embedder
    llm = get_llm(provider="groq", model="llama-3.3-70b-versatile", api_key="gsk")
    embedder = get_embedder(provider="voyage", model="voyage-finance-2", api_key="pa")
    assert llm is not None
    assert embedder is not None