import ollama

from app.core.config import settings


class Embedder:
    def __init__(self):
        self.client = ollama.AsyncClient(host=settings.ollama_base_url)
        self.model = settings.ollama_embed_model

    async def embed_text(self, text: str) -> list[float]:
        """
        Embed a single piece of text into a vector.
        """
        response = await self.client.embed(
            model=self.model,
            input=text,
        )
        return response.embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in one call.
        More efficient than calling embed_text in a loop.
        """
        response = await self.client.embed(
            model=self.model,
            input=texts,
        )
        return response.embeddings