"""
agent/ui_regenerator.py
React UI Regeneration Agent (Refinement Agent)

Refines existing TSX/JSX and CSS code using the UI Validation Report
and wireframe blueprint until high visual similarity is achieved.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from rich.console import Console

from config import settings
from utils.groq_client import GroqClient
from utils.file_manager import FileManager

console = Console()


class UIRegenerator:
    """
    Refines and regenerates code based on visual validation report.
    """

    def __init__(self, groq_client: GroqClient, framework: str = "React") -> None:
        self._client = groq_client
        self.framework = framework
        self._system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = settings.prompts_dir / "ui_regeneration.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return f"You are an expert {self.framework} UI Regeneration Agent. Refine code for pixel-perfect match."

    def regenerate(
        self,
        file_manager: FileManager,
        validation_report: Dict[str, Any],
        project_name: str,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        Refine generated code if visual similarity is below acceptable threshold.
        """
        def emit(msg: str) -> None:
            if progress_cb:
                progress_cb(msg)
            console.print(f"  [cyan]{msg}[/cyan]")

        score = validation_report.get("similarity_score", 100)
        if score >= 98:
            emit(f"UI visual similarity score is high ({score}%) — no refinement needed.")
            return False

        emit(f"UI visual similarity score is {score}% (< 98%). Running {self.framework} UI Regeneration Agent...")

        is_angular = "angular" in self.framework.lower()
        ext = "ts" if is_angular else settings.output_language
        src = file_manager.react_src_dir

        # Find the first non-App, non-main component file to refine
        component_file = None
        for f in src.glob(f"*.{ext}"):
            if f.stem not in ("App", "main"):
                component_file = f
                break
        if component_file is None:
            component_file = src / f"App.{ext}"

        css_name = component_file.stem + ".css"
        css_file = src / css_name

        current_react = component_file.read_text(encoding="utf-8") if component_file.exists() else ""
        current_css = css_file.read_text(encoding="utf-8") if css_file.exists() else ""

        # Build a LEAN prompt — send only the issues, not the full validation report
        issues = validation_report.get("elements", [])
        missing = [e.get("element_name", "") for e in issues if e.get("status") in ("Missing", "Extra", "Misaligned", "Wrong Size", "Wrong Style")]
        issue_summary = ", ".join(missing[:10]) if missing else "general visual mismatch"

        user_prompt = (
            f"Fix the following visual issues in this React {ext.upper()} component: {issue_summary}.\n\n"
            f"Current component ({component_file.name}):\n"
            f"```{ext}\n{current_react[:3000]}\n```\n\n"
            f"Current CSS ({css_name}):\n"
            f"```css\n{current_css[:1500]}\n```\n\n"
            f"Return Block 1 as the fixed {ext.upper()} component and Block 2 as the fixed CSS, "
            "each inside ```code fences```."
        )

        # Use fast small model list — avoid gpt-oss which doesn't return code blocks reliably
        regen_models = [
            m for m in [
                "llama-3.1-8b-instant",   # 20K TPM — best for refinement
                "llama-3.3-70b-versatile", # 12K TPM fallback
                settings.code_model,
            ] if "gpt-oss" not in m
        ]
        regen_models = list(dict.fromkeys(regen_models))  # deduplicate

        raw_output = ""
        for model in regen_models:
            emit(f"  Refinement model: {model}...")
            try:
                raw_output = self._client.chat(
                    system_prompt=self._system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    max_tokens=settings.max_tokens_code,
                )
                if raw_output and raw_output.strip():
                    break
            except Exception as exc:
                emit(f"  [WARN] {model} failed: {exc}. Trying fallback...")
                continue

        if not raw_output or not raw_output.strip():
            emit("[WARN] UI Regeneration: no response from any model.")
            return False

        # --- Extract code from response ---
        code_blocks = re.findall(r"```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)```", raw_output)

        refined_jsx = ""
        refined_css = ""

        if len(code_blocks) >= 2:
            refined_jsx = code_blocks[0].strip()
            refined_css = code_blocks[1].strip()
        elif len(code_blocks) == 1:
            block = code_blocks[0].strip()
            # Detect if it's JSX or CSS by presence of 'export default'
            if "export default" in block or "import React" in block or f"import './{component_file.stem}" in block:
                refined_jsx = block
            else:
                refined_css = block
        else:
            # No fences at all — try to extract by looking for 'import' and 'export default'
            import_idx = raw_output.find("import ")
            export_idx = raw_output.rfind("export default")
            if import_idx != -1 and export_idx != -1:
                refined_jsx = raw_output[import_idx:export_idx + 50].strip()
                emit("  Extracted code without fences (fallback parser).")

        if not refined_jsx and not refined_css:
            emit("[WARN] UI Regeneration response contained no extractable code.")
            return False

        # Auto-repair unclosed quotes on JSX lines
        if refined_jsx:
            lines = refined_jsx.splitlines()
            fixed = []
            for line in lines:
                quotes = line.count('"') - line.count('\\"')
                if quotes % 2 != 0 and ('<' in line or '>' in line or '=' in line):
                    line = line.rstrip() + '"'
                fixed.append(line)
            refined_jsx = "\n".join(fixed)
            file_manager.write_text(component_file, refined_jsx)

        if refined_css:
            file_manager.write_text(css_file, refined_css)

        emit(f"✓ React UI Regeneration complete — updated {component_file.name} & {css_name}.")
        return True
