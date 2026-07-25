from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    chunk_index: int
    char_start: int
    char_end: int


class Chunker:
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str) -> list[Chunk]:
        """
        Split text into overlapping chunks by character count.
        """
        # 1. Clean the text first
        text = self._clean(text)

        chunks = []
        start = 0
        index = 0

        while start < len(text):
            end = start + self.chunk_size

            # 2. Don't cut mid-sentence
            if end < len(text):
                boundary = self._find_sentence_boundary(text, end)
                end = boundary

            chunk_text = text[start:end].strip()

            # 3. Skip empty chunks
            if chunk_text:
                chunks.append(Chunk(
                    text=chunk_text,
                    chunk_index=index,
                    char_start=start,
                    char_end=end,
                ))
                index += 1

            # 4. Move forward with overlap
            start = end - self.chunk_overlap

        return chunks

    def _clean(self, text: str) -> str:
        """
        Remove noise common in PDF extracted text.
        """
        import re
        # Collapse multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Collapse multiple spaces
        text = re.sub(r' {2,}', ' ', text)
        # Remove page numbers (common in 10-K PDFs)
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        return text.strip()

    def _find_sentence_boundary(self, text: str, pos: int) -> int:
        """
        Walk backwards from pos to find the nearest
        sentence ending (.  !  ?) so we don't cut mid-sentence.
        """
        search_window = text[max(0, pos - 100): pos]
        for i, char in enumerate(reversed(search_window)):
            if char in ".!?":
                return pos - i
        # No boundary found — cut at word boundary instead
        space_pos = text.rfind(" ", max(0, pos - 50), pos)
        return space_pos if space_pos != -1 else pos