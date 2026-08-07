"""
agent/image_analyzer.py
Stage 1 — Image Analyzer

Sends the reference UI screenshot to the Groq vision model and
produces ui_spec.json with every detected UI element having a unique elementId.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from rich.console import Console

from config import settings
from models import UISpec
from utils.groq_client import GroqClient
from utils.json_utils import parse_json_safe, save_json, validate_model

console = Console()


class ImageAnalyzer:
    """
    Stage 1: Analyzes a UI screenshot with a vision model.
    Output: ui_spec.json
    """

    def __init__(self, groq_client: GroqClient) -> None:
        self._client = groq_client
        self._system_prompt = self._load_prompt()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        image_path: Path,
        output_path: Path,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Optional[UISpec]:
        """
        Analyze the reference image and save ui_spec.json.
        Returns a validated UISpec or None on failure.
        """
        def emit(msg: str) -> None:
            if progress_cb:
                progress_cb(msg)
            console.print(f"  [cyan]{msg}[/cyan]")

        emit(f"Loading image: {image_path.name}")
        if not image_path.exists():
            emit(f"[ERROR] Image not found: {image_path}")
            return None

        user_prompt = (
            f"Analyze this UI screenshot: '{image_path.name}'.\n"
            "Return ONLY the complete valid JSON specification as described in the system prompt.\n"
            "IMPORTANT: Respond DIRECTLY with the JSON object. Do NOT output long thinking blocks or prose explanations.\n"
            "Be thorough and concise — capture all structural containers and visible elements."
        )

        v_models = [settings.vision_model]
        if settings.provider in ("openrouter", "openai"):
            v_models.extend(["openrouter/free", "qwen/qwen-2.5-vl-72b-instruct:free", "meta-llama/llama-3.2-11b-vision-instruct:free", "google/gemini-2.0-flash-exp:free"])
        v_models = list(dict.fromkeys([m for m in v_models if m]))

        raw_response = ""
        spec = None
        for v_model in v_models:
            emit(f"Sending to vision model: {v_model}...")
            try:
                raw_response = self._client.vision(
                    system_prompt=self._system_prompt,
                    user_text=user_prompt,
                    image_path=image_path,
                    model=v_model,
                )
                if raw_response and raw_response.strip():
                    emit(f"Parsing response from {v_model}...")
                    spec = self._parse_response(raw_response, image_path.name)
                    if spec is not None:
                        break
                    else:
                        emit(f"  [WARN] Vision model '{v_model}' returned invalid JSON. Trying fallback...")
            except Exception as exc:
                emit(f"  [WARN] Vision model '{v_model}' failed: {exc}. Trying fallback...")
                continue

        if spec is None:
            emit("[ERROR] Failed to parse UI spec from any vision model response.")
            return None

        # Patch sourceImage
        spec_dict = spec.model_dump(by_alias=True)
        spec_dict["sourceImage"] = image_path.name

        emit("Validating element IDs...")
        self._validate_element_ids(spec)

        emit(f"Saving ui_spec.json → {output_path}")
        save_json(spec, output_path)

        total = len(spec.all_element_ids())
        emit(f"Stage 1 complete — {len(spec.pages)} page(s), {total} element(s) detected.")
        return spec

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_prompt(self) -> str:
        prompt_path = settings.prompts_dir / "image_analysis.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        console.print("[yellow][ImageAnalyzer] Prompt file not found, using inline fallback.[/yellow]")
        return (
            "You are a UI analyst. Analyze the screenshot and return a JSON UI specification. "
            "Assign every element a unique elementId starting with 'UI_'. "
            "Return ONLY valid JSON, no markdown fences."
        )

    def _parse_response(
        self, raw: str, source_image: str
    ) -> Optional[UISpec]:
        """Try to parse the raw LLM response into a UISpec, with retries."""
        for attempt in range(1, settings.max_json_retries + 1):
            data = parse_json_safe(raw)
            if data is None:
                console.print(
                    f"[yellow]  Attempt {attempt}: Could not parse JSON. Length: {len(raw)}[/yellow]"
                )
                console.print(f"--- START ---\n{raw[:200]}\n--- END ---\n{raw[-200:]}")
                if attempt < settings.max_json_retries:
                    time.sleep(2)
                continue

            # Inject defaults for required fields if missing
            data.setdefault("sourceImage", source_image)
            data.setdefault("specVersion", "1.0")
            data.setdefault("pages", [])
            data.setdefault("designTokens", {})
            data.setdefault("elementSummary", {})

            spec = validate_model(data, UISpec)
            if spec is not None:
                return spec

        return None

    def _validate_element_ids(self, spec: UISpec) -> None:
        """Warn about duplicate or malformed element IDs."""
        ids: list[str] = spec.all_element_ids()
        seen: set[str] = set()
        for eid in ids:
            if eid in seen:
                console.print(f"[yellow]  [WARN] Duplicate elementId: {eid}[/yellow]")
            seen.add(eid)
        console.print(f"  [dim]Element IDs: {', '.join(ids[:8])}{'...' if len(ids) > 8 else ''}[/dim]")
