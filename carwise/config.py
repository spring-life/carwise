from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data"
    storage_dir: Path = PROJECT_ROOT / "storage"
    llm_provider: str = os.getenv("CARWISE_LLM_PROVIDER", "ollama")
    ollama_base_url: str = os.getenv("CARWISE_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_chat_model: str = os.getenv("CARWISE_OLLAMA_CHAT_MODEL", "qwen2.5:3b")
    ollama_embed_model: str = os.getenv("CARWISE_OLLAMA_EMBED_MODEL", "quentinz/bge-small-zh-v1.5")
    deepseek_api_key: str | None = os.getenv("CARWISE_DEEPSEEK_API_KEY")
    deepseek_model: str = os.getenv("CARWISE_DEEPSEEK_MODEL", "deepseek-chat")

