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


class TokenManager:
    @staticmethod
    def estimate_tokens(item) -> int:
        if isinstance(item, str):
            return max(1, len(item) // 4)
        if isinstance(item, dict):
            # If it's a message dict
            content = item.get("content", "")
            if isinstance(content, str):
                return TokenManager.estimate_tokens(content)
            if isinstance(content, list):
                # For vision/multi-modal content, only count text, ignore base64 images
                total = 0
                for block in content:
                    if block.get("type") == "text":
                        total += TokenManager.estimate_tokens(block.get("text", ""))
                # Add ~100 tokens as a baseline for the image itself
                return total + 100
        return 0

    @staticmethod
    def compress_prompt(messages: list, max_input: int) -> list:
        total = sum(TokenManager.estimate_tokens(m) for m in messages)
        if total <= max_input:
            return messages
            
        import re
        
        # 1. Smart compression heuristic
        compressed = []
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                # Remove duplicate logs/warnings if any
                content = re.sub(r"(\[WARN\].*\n)\1+", r"\1", content)
                # Remove extra blank lines to save token overhead
                content = re.sub(r"\n{3,}", "\n\n", content)
                
                # If still too large, compress CSS and React blocks intelligently
                if TokenManager.estimate_tokens(content) > max_input:
                    # Truncate CSS blocks heavily (we rarely need the full CSS to fix React)
                    content = re.sub(r"```css\n(.*?)\n```", lambda match: f"```css\n{match.group(1)[:500]}\n...[CSS COMPRESSED]...\n```" if len(match.group(1)) > 500 else match.group(0), content, flags=re.DOTALL)
                    
                if TokenManager.estimate_tokens(content) > max_input:
                    # Truncate large code blocks while preserving start and end
                    def truncate_code(match):
                        code = match.group(1)
                        if len(code) > 1500:
                            return f"```{match.group(2) or ''}\n{code[:750]}\n...[CODE COMPRESSED]...\n{code[-750:]}\n```"
                        return match.group(0)
                    content = re.sub(r"```([a-zA-Z0-9_-]*)\n(.*?)\n```", truncate_code, content, flags=re.DOTALL)
                    
                # Last resort: generic truncation if STILL too large
                if TokenManager.estimate_tokens(content) > max_input:
                    half = max(500, (max_input // len(messages)) * 2)
                    if len(content) > half * 2:
                        content = content[:half] + "\n\n...[COMPRESSED]...\n\n" + content[-half:]
                        
            elif isinstance(content, list):
                # For vision/multi-modal content, truncate text blocks
                for i, item in enumerate(content):
                    if item.get("type") == "text" and len(item.get("text", "")) > 1000:
                        text_val = item["text"]
                        text_val = re.sub(r"\n{3,}", "\n\n", text_val)
                        half = max(500, (max_input // len(content)) * 2)
                        if len(text_val) > half * 2:
                            content[i]["text"] = text_val[:half] + "\n\n...[COMPRESSED]...\n\n" + text_val[-half:]
            
            compressed.append({**m, "content": content})
        return compressed


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
        # 1. Determine total budget
        is_code = "gpt-oss" in model.lower() or "coder" in model.lower()
        has_image = any(isinstance(msg.get("content"), list) for msg in messages)
        total_budget = settings.max_total_tokens if is_code else 8000
        # 2. Estimate original input tokens
        original_input_tokens = sum(TokenManager.estimate_tokens(m) for m in messages)
        
        # 3. Dynamic Sliding Window Token Allocator
        # We give the input what it needs up to a reasonable cap (max_input_tokens).
        allowed_input = min(original_input_tokens, settings.max_input_tokens)
        
        # The output gets whatever is left from the budget
        allowed_output = total_budget - allowed_input - settings.token_safety_margin
        
        # Ensure the output has an absolute minimum floor (e.g. 1500 tokens) so code doesn't get instantly truncated
        if allowed_output < 1500:
            allowed_output = 1500
            allowed_input = total_budget - allowed_output - settings.token_safety_margin
            
        max_tokens = min(max_tokens, allowed_output)
        
        # 4. Compress if needed
        if original_input_tokens > allowed_input:
            messages = TokenManager.compress_prompt(messages, allowed_input)
            
        # 5. Log metrics
        compressed_input_tokens = sum(TokenManager.estimate_tokens(m) for m in messages)
        console.print(f"[cyan]AI Pipeline: Token Budget | Original: {original_input_tokens} → Compressed: {compressed_input_tokens} → Output: {max_tokens} → Total: {compressed_input_tokens + max_tokens} (Limit: {total_budget})[/cyan]")

        if settings.provider == "openrouter":
            try:
                return self._call_openrouter(model, messages, temperature, max_tokens)
            except Exception as e:
                if settings.groq_api_keys:
                    console.print(f"[bold yellow][GroqClient] OpenRouter API failed ({e}). Falling back to Groq...[/bold yellow]")
                    has_image = any(isinstance(msg.get("content"), list) for msg in messages)
                    fallback_model = settings.fallback_vision_model if has_image else settings.fallback_code_model
                    
                    if not hasattr(self, "_client"):
                        self._api_keys = settings.groq_api_keys
                        self._current_key_idx = 0
                        self._init_client()
                        
                    return self._call_groq_with_retry(fallback_model, messages, temperature, max_tokens)
                raise
        elif settings.provider == "openai":
            return self._call_openai(model, messages, temperature, max_tokens)
        else:
            try:
                return self._call_groq_with_retry(model, messages, temperature, max_tokens)
            except Exception as e:
                if settings.openrouter_api_key:
                    console.print(f"[bold yellow][GroqClient] Groq API failed ({e}). Falling back to OpenRouter...[/bold yellow]")
                    has_image = any(isinstance(msg.get("content"), list) for msg in messages)
                    fallback_model = settings.fallback_vision_model if has_image else settings.fallback_code_model
                    return self._call_openrouter(fallback_model, messages, temperature, max_tokens)
                raise

    def _call_groq_with_retry(
        self,
        model: str,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> str:
        try:
            return self._call_groq(model, messages, temperature, max_tokens)
        except Exception as exc:
            # Handle 413 Rate Limit Exceeded for Groq
            if "413" in str(exc) or "rate_limit_exceeded" in str(exc) or "too large" in str(exc).lower():
                console.print(f"[bold yellow][GroqClient] 413 Rate Limit Exceeded. Retrying with compressed prompt...[/bold yellow]")
                compressed_messages = TokenManager.compress_prompt(messages, settings.max_input_tokens // 2)
                return self._call_groq(model, compressed_messages, temperature, max_tokens // 2)
            raise

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

