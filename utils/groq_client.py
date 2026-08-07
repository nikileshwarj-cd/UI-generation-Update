"""
utils/groq_client.py
Thin wrapper around the Groq SDK.
Provides vision and text completion helpers with
graceful error handling and markdown fence stripping.
"""
from __future__ import annotations

import base64
import io
import math
import sys
import time
from pathlib import Path
from typing import Optional

from PIL import Image

from groq import Groq, APIConnectionError, AuthenticationError, RateLimitError
from rich.console import Console

from config import settings
from utils.json_utils import strip_fences

import json
import urllib.request
import urllib.error

console = Console()


class GroqClient:
    """Initialises the LLM SDK (Groq or OpenRouter) and provides chat/vision helpers."""

    def __init__(self) -> None:
        self.provider = settings.provider
        if self.provider == "openrouter":
            self._openrouter_key = settings.openrouter_api_key or settings.api_key
            console.print(f"[green][LLMClient] Using OpenRouter API (Vision: {settings.vision_model} | Code: {settings.code_model})[/green]")
        else:
            self._api_keys = settings.groq_api_keys
            self._current_key_idx = 0
            if not self._api_keys:
                console.print(
                    "[bold red][GroqClient] Neither OPENROUTER_API_KEY nor GROQ_API_KEY is configured.[/bold red]"
                )
                sys.exit(1)
            self._init_client()

    def _init_client(self) -> None:
        if settings.provider == "openrouter":
            return
        current_key = self._api_keys[self._current_key_idx]
        try:
            self._client = Groq(api_key=current_key)
        except Exception as exc:
            console.print(
                f"[bold red][GroqClient] Failed to initialise Groq SDK: {exc}[/bold red]"
            )
            sys.exit(1)

    def _switch_to_next_key(self, reason: str = "RateLimit / Token limit hit") -> bool:
        if settings.provider == "groq" and self._current_key_idx + 1 < len(self._api_keys):
            self._current_key_idx += 1
            console.print(
                f"[bold yellow][GroqClient] {reason}. Switching to fallback API Key #{self._current_key_idx + 1}...[/bold yellow]"
            )
            self._init_client()
            return True
        return False

    # ------------------------------------------------------------------
    # Text Completion
    # ------------------------------------------------------------------

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4000,
    ) -> str:
        """Send a text chat request and return the assistant response."""
        model = model or settings.code_model
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._call(model, messages, temperature, max_tokens)

    # ------------------------------------------------------------------
    # Vision Completion
    # ------------------------------------------------------------------

    # Total TPM budget per request
    _TPM_BUDGET: int = 7500
    _OUTPUT_TOKENS: int = 4000
    _PROMPT_OVERHEAD: int = 500
    _IMAGE_TOKEN_BUDGET: int = _TPM_BUDGET - _OUTPUT_TOKENS - _PROMPT_OVERHEAD
    _BYTES_PER_TOKEN: int = 750

    def _optimize_image(self, image_path: Path) -> tuple[str, str]:
        """
        Load, resize-if-needed, and base64-encode the image so that its
        estimated token count stays within budget.
        Returns (base64_data, mime_type).
        """
        img = Image.open(image_path).convert("RGB")
        orig_w, orig_h = img.size

        scale = 1.0
        while True:
            new_w = max(1, int(orig_w * scale))
            new_h = max(1, int(orig_h * scale))

            resized = img.resize((new_w, new_h), Image.LANCZOS)

            buffer = io.BytesIO()
            resized.save(buffer, format="JPEG", quality=85, optimize=True)
            encoded_bytes = buffer.getvalue()
            b64_data = base64.standard_b64encode(encoded_bytes).decode("utf-8")

            estimated_tokens = math.ceil(len(b64_data) / self._BYTES_PER_TOKEN)

            if estimated_tokens <= self._IMAGE_TOKEN_BUDGET:
                if scale < 1.0:
                    console.print(
                        f"  [cyan][LLMClient] Image optimized: "
                        f"{orig_w}x{orig_h} → {new_w}x{new_h} "
                        f"(~{estimated_tokens} img tokens)[/cyan]"
                    )
                else:
                    console.print(
                        f"  [green][LLMClient] Image OK: "
                        f"{orig_w}x{orig_h} (~{estimated_tokens} img tokens)[/green]"
                    )
                return b64_data, "image/jpeg"

            scale -= 0.10
            if scale <= 0.05:
                console.print(
                    "[yellow][LLMClient] Image was very large; "
                    "reduced to minimum safe size.[/yellow]"
                )
                return b64_data, "image/jpeg"

    def vision(
        self,
        system_prompt: str,
        user_text: str,
        image_path: Path,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Send a vision request with an image."""
        model = model or settings.vision_model
        if max_tokens is None:
            max_tokens = settings.max_tokens_vision

        image_data, mime = self._optimize_image(image_path)

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{image_data}",
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            },
        ]
        return self._call(model, messages, temperature, max_tokens)

    # ------------------------------------------------------------------
    # Internal call dispatcher
    # ------------------------------------------------------------------

    def _call(
        self,
        model: str,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> str:
        if settings.provider == "openrouter":
            try:
                return self._call_openrouter(model, messages, temperature, max_tokens)
            except Exception as e:
                # If OpenRouter fails, automatically failover to Groq with Qwen
                if settings.groq_api_keys:
                    console.print(f"[bold yellow][GroqClient] OpenRouter API failed ({e}). Falling back to Groq and Qwen...[/bold yellow]")
                    has_image = any(isinstance(msg.get("content"), list) for msg in messages)
                    # Use llama vision for images (since Groq doesn't host Qwen vision), and qwen-2.5-coder-32b for code
                    fallback_model = "llama-3.2-11b-vision-preview" if has_image else "qwen-2.5-coder-32b"
                    
                    if not hasattr(self, "_client"):
                        self._api_keys = settings.groq_api_keys
                        self._current_key_idx = 0
                        self._init_client()
                        
                    return self._call_groq(fallback_model, messages, temperature, max_tokens)
                raise
        elif settings.provider == "openai":
            return self._call_openai(model, messages, temperature, max_tokens)
        else:
            return self._call_groq(model, messages, temperature, max_tokens)

    def _call_openai(
        self,
        model: str,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> str:
        api_key = settings.openai_api_key or settings.api_key
        # Strip provider prefix if user passed openai/gpt-4o-mini directly to OpenAI API
        clean_model = model.replace("openai/", "")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": clean_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return self._http_post(url, headers, payload)

    def _call_openrouter(
        self,
        model: str,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> str:
        api_key = settings.openrouter_api_key or settings.api_key
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "AI Frontend Generation Agent",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return self._http_post(url, headers, payload)

    def _http_post(self, url: str, headers: dict, payload: dict) -> str:
        retries = 3
        delay = 4.0
        for attempt in range(1, retries + 1):
            try:
                data_bytes = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=180) as response:
                    res_body = response.read().decode("utf-8")
                    res_json = json.loads(res_body)
                    if "choices" in res_json and len(res_json["choices"]) > 0:
                        content = res_json["choices"][0]["message"]["content"] or ""
                        return strip_fences(content)
                    elif "error" in res_json:
                        err_msg = res_json["error"].get("message", str(res_json["error"]))
                        console.print(f"[bold red][API Error] {err_msg}[/bold red]")
                        if attempt < retries:
                            time.sleep(delay)
                            continue
                        raise RuntimeError(f"API Error: {err_msg}")
            except urllib.error.HTTPError as exc:
                err_text = ""
                try:
                    err_text = exc.read().decode("utf-8")
                except Exception:
                    pass
                console.print(f"[yellow][API Request] HTTP {exc.code}: {exc.reason} - {err_text[:300]}[/yellow]")
                if exc.code == 429 or exc.code >= 500:
                    if attempt < retries:
                        time.sleep(delay)
                        delay *= 2
                        continue
                raise exc
            except Exception as exc:
                if attempt < retries:
                    console.print(f"[yellow][API Request] Network error ({exc}). Retrying {attempt}/{retries}...[/yellow]")
                    time.sleep(delay)
                    delay *= 2
                else:
                    console.print(f"[bold red][API Request] Error: {exc}[/bold red]")
        return ""

    def _call_groq(
        self,
        model: str,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> str:
        retries = 3
        delay = 5.0
        for attempt in range(1, retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content or ""
                return strip_fences(content)

            except AuthenticationError:
                if self._switch_to_next_key("Authentication failed / Token invalid"):
                    continue
                console.print(
                    "[bold red][GroqClient] Authentication failed on all API keys — check your GROQ_API_KEY.[/bold red]"
                )
                sys.exit(1)

            except RateLimitError:
                if self._switch_to_next_key("Rate limit / Token limit hit"):
                    continue
                if attempt < retries:
                    console.print(
                        f"[yellow][GroqClient] Rate limited. Waiting {delay}s before retry {attempt}/{retries}...[/yellow]"
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    console.print("[bold red][GroqClient] Rate limit exceeded on all API keys. Aborting.[/bold red]")
                    raise

            except APIConnectionError as exc:
                if attempt < retries:
                    console.print(
                        f"[yellow][GroqClient] Connection error ({exc}). Retrying {attempt}/{retries}...[/yellow]"
                    )
                    time.sleep(delay)
                else:
                    raise

            except Exception as exc:
                err_msg = str(exc).lower()
                if "rate limit" in err_msg or "quota" in err_msg or "429" in err_msg or "token" in err_msg:
                    if self._switch_to_next_key(f"Error ({exc})"):
                        continue
                console.print(f"[bold red][GroqClient] Unexpected error: {exc}[/bold red]")
                raise

        return ""

