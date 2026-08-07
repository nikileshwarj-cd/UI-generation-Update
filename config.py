# ============================================================
# config.py — Centralised configuration loader
# All settings come from .env / environment variables.
# ============================================================

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (the directory containing config.py)
_ROOT = Path(__file__).parent
load_dotenv(_ROOT / ".env", override=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require(key: str) -> str:
    """Read a required env var; exit with a clear message if missing."""
    val = os.getenv(key, "").strip()
    if not val:
        print(
            f"\n[CONFIG ERROR] Environment variable '{key}' is not set.\n"
            f"  → Copy .env.example to .env and fill in your values.\n",
            file=sys.stderr,
        )
        sys.exit(1)
    return val


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _get_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    # API Keys
    openrouter_api_key: str = field(default_factory=lambda: _get("OPENROUTER_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _get("OPENAI_API_KEY"))
    groq_api_key: str = field(default_factory=lambda: _get("GROQ_API_KEY"))

    @property
    def api_key(self) -> str:
        key = self.openrouter_api_key or self.openai_api_key or self.groq_api_key or _get("OPENROUTER_API_KEY") or _get("OPENAI_API_KEY") or _get("GROQ_API_KEY")
        if not key:
            print(
                "\n[CONFIG ERROR] No API key found (OPENROUTER_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY).\n"
                "  → Copy .env.example to .env and set your API key.\n",
                file=sys.stderr,
            )
            sys.exit(1)
        return key

    @property
    def provider(self) -> str:
        forced = _get("LLM_PROVIDER").lower()
        if forced in ("openrouter", "openai", "groq"):
            return forced
        if self.openrouter_api_key or "/" in self.vision_model or "/" in self.code_model:
            return "openrouter"
        if self.openai_api_key:
            return "openai"
        return "groq"

    @property
    def groq_api_keys(self) -> list[str]:
        raw_keys = _get("GROQ_API_KEYS")
        if raw_keys:
            keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
            if keys:
                return keys

        keys = []
        primary = _get("GROQ_API_KEY") or self.groq_api_key
        if primary:
            keys.append(primary)

        for var_name in ("GROQ_API_KEY_FALLBACK", "GROQ_API_KEY_SECONDARY", "GROQ_API_KEY_2", "GROQ_API_KEY_3"):
            val = _get(var_name)
            if val and val not in keys:
                keys.append(val)

        return keys if keys else ([self.groq_api_key] if self.groq_api_key else [])

    # Models — loaded lazily so tests can override env before import
    vision_model: str = field(
        default_factory=lambda: _get(
            "VISION_MODEL", "openrouter/free"
        )
    )
    code_model: str = field(
        default_factory=lambda: _get("CODE_MODEL", "openai/gpt-4o-mini")
    )

    # Output
    output_language: str = field(
        default_factory=lambda: _get("OUTPUT_LANGUAGE", "tsx").lower()
    )
    output_dir: Path = field(
        default_factory=lambda: _ROOT / _get("OUTPUT_DIR", "output")
    )

    # Web UI
    ui_host: str = field(default_factory=lambda: _get("UI_HOST", "127.0.0.1"))
    ui_port: int = field(default_factory=lambda: _get_int("UI_PORT", 5000))
    ui_debug: bool = field(default_factory=lambda: _get_bool("UI_DEBUG", False))

    # Agent behaviour
    max_json_retries: int = field(
        default_factory=lambda: _get_int("MAX_JSON_RETRIES", 3)
    )

    # Token budgets — tune these to match your LLM plan
    max_tokens_code: int = field(
        default_factory=lambda: _get_int("MAX_TOKENS_CODE", 6000)
    )
    max_tokens_vision: int = field(
        default_factory=lambda: _get_int("MAX_TOKENS_VISION", 4000)
    )

    # Paths
    project_root: Path = field(default_factory=lambda: _ROOT)
    input_dir: Path = field(default_factory=lambda: _ROOT / "input")
    prompts_dir: Path = field(default_factory=lambda: _ROOT / "prompts")

    def __post_init__(self) -> None:
        # Validate output language/framework
        if self.output_language not in ("tsx", "jsx", "angular"):
            print(
                f"[CONFIG WARNING] OUTPUT_LANGUAGE='{self.output_language}' is not "
                f"recognised. Defaulting to 'tsx'.",
                file=sys.stderr,
            )
            self.output_language = "tsx"

        # Ensure core directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.input_dir / "images").mkdir(parents=True, exist_ok=True)
        (self.input_dir / "user_stories").mkdir(parents=True, exist_ok=True)

    def reload(self) -> None:
        """Reload configuration from .env file."""
        load_dotenv(_ROOT / ".env", override=True)
        self.openrouter_api_key = _get("OPENROUTER_API_KEY")
        self.openai_api_key = _get("OPENAI_API_KEY")
        self.groq_api_key = _get("GROQ_API_KEY")
        self.vision_model = _get("VISION_MODEL", "openrouter/free")
        self.code_model = _get("CODE_MODEL", "openai/gpt-4o-mini")
        self.max_tokens_code = _get_int("MAX_TOKENS_CODE", 6000)
        self.max_tokens_vision = _get_int("MAX_TOKENS_VISION", 4000)

    @property
    def file_extension(self) -> str:
        """Return the file extension for React components (tsx or jsx)."""
        return self.output_language  # 'tsx' or 'jsx'

    @property
    def is_typescript(self) -> bool:
        return self.output_language == "tsx"

    def __repr__(self) -> str:
        return (
            f"Settings("
            f"vision_model={self.vision_model!r}, "
            f"code_model={self.code_model!r}, "
            f"output_language={self.output_language!r}, "
            f"output_dir={self.output_dir}, "
            f"ui_port={self.ui_port}"
            f")"
        )


# ---------------------------------------------------------------------------
# Singleton — import this everywhere
# ---------------------------------------------------------------------------

settings = Settings()
