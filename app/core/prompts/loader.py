from pathlib import Path
from functools import lru_cache

PROMPTS_DIR = Path("storage/prompts")


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """
    Load a prompt template from storage/prompts/{name}.md
    Cached after first read — file reads happen once per process.

    To reload prompts without restart: call load_prompt.cache_clear()
    """
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {path}\n"
            f"Create it at {path} to fix this."
        )
    return path.read_text(encoding="utf-8").strip()