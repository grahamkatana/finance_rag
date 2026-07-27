from app.core.llm.base import BaseEmbedder


class VoyageEmbedder(BaseEmbedder):
    """
    Voyage AI embedding provider.
    Embeddings ONLY — no generation.

    Best RAG retrieval quality available in 2026.
    Domain-specific models make a measurable difference:

    voyage-finance-2  → financial documents (SEC filings, reports)
    voyage-law-2      → legal documents (contracts, briefs, statutes)
    voyage-4          → general purpose ($0.06/M tokens)
    voyage-4-lite     → budget option ($0.02/M tokens)
    voyage-4-large    → highest quality ($0.12/M tokens)

    One developer switching to Voyage for legal docs described
    it as "a night and day difference in retrieval quality."
    """

    def __init__(self, api_key: str, model: str = "voyage-4"):
        try:
            import voyageai
            self._client = voyageai.AsyncClient(api_key=api_key)
        except ImportError:
            raise ImportError(
                "voyageai required. Install with: uv add voyageai"
            )
        self.model = model

    async def embed_text(
        self,
        text: str,
    ) -> list[float]:
        result = await self._client.embed(
            texts=[text],
            model=self.model,
            input_type="query",  # query vs document — Voyage uses this for optimization
        )
        return result.embeddings[0]

    async def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        # Voyage supports native batch — one API call
        # input_type="document" for ingestion batches
        result = await self._client.embed(
            texts=texts,
            model=self.model,
            input_type="document",
        )
        return result.embeddings