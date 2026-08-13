"""
agent/layout_analyzer.py

Layout Analyzer specifically for complex UIs.
Extracts precise spatial metadata: bounding boxes, gaps, grids, padding, etc.
Outputs a layout_spec.json.
"""
import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from rich.console import Console

from config import settings
from utils.groq_client import GroqClient
from utils.json_utils import parse_json_safe, save_json

console = Console()


class LayoutAnalyzer:
    def __init__(self, groq_client: GroqClient) -> None:
        self._client = groq_client
        self._system_prompt = self._load_prompt()

    def analyze(
        self,
        image_path: Path,
        output_path: Path,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Optional[Dict[str, Any]]:
        def emit(msg: str) -> None:
            if progress_cb:
                progress_cb(msg)
            console.print(f"  [cyan]{msg}[/cyan]")

        emit(f"Running LayoutAnalyzer for complex UI on: {image_path.name}")
        
        user_prompt = (
            "Analyze the layout of this complex UI wireframe.\n"
            "Extract precise page dimensions, component bounding boxes (x, y, w, h), "
            "parent-child hierarchy, padding, gaps, and column/row structures.\n"
            "Return ONLY a compact, valid JSON object detailing the layout specification."
        )

        v_models = [settings.vision_model]
        if settings.provider in ("openrouter", "openai"):
            v_models.extend(["openrouter/free", "qwen/qwen-2.5-vl-72b-instruct:free", "google/gemini-2.0-flash-exp:free"])
        v_models = list(dict.fromkeys([m for m in v_models if m]))

        layout_spec = None
        for v_model in v_models:
            emit(f"Sending to vision model for layout analysis: {v_model}...")
            try:
                raw_response = self._client.vision(
                    system_prompt=self._system_prompt,
                    user_text=user_prompt,
                    image_path=image_path,
                    model=v_model,
                )
                if raw_response and raw_response.strip():
                    data = parse_json_safe(raw_response)
                    if data and isinstance(data, dict):
                        layout_spec = data
                        break
            except Exception as exc:
                emit(f"  [WARN] LayoutAnalyzer vision model '{v_model}' failed: {exc}. Trying fallback...")
                continue

        if layout_spec is None:
            emit("[ERROR] Failed to extract layout specification.")
            return None

        save_json(layout_spec, output_path)
        emit(f"Layout spec saved to {output_path}")
        return layout_spec

    def _load_prompt(self) -> str:
        prompt_path = settings.prompts_dir / "layout_analysis.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return (
            "You are a Layout Analyst. Extract the layout specification of the provided wireframe.\n"
            "Include: \n"
            "- page_dimensions: { width, height }\n"
            "- layout_tree: A hierarchical tree of components.\n"
            "For each component in the tree, provide:\n"
            "  - type, id\n"
            "  - bounding_box: [x, y, width, height]\n"
            "  - style: { padding, gap, display, flexDirection }\n"
            "  - children: []\n"
            "Return ONLY valid JSON."
        )
