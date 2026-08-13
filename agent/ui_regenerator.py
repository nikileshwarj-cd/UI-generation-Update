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
from utils.groq_client import GroqClient, TokenManager
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
        is_complex: bool = False,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        Refine generated code if visual similarity is below acceptable threshold.
        """
        def emit(msg: str) -> None:
            if progress_cb:
                progress_cb(msg)
            else:
                console.print(f"  [cyan]{msg}[/cyan]")

        score = validation_report.get("similarity_score", 100)
        if score >= 98:
            emit(f"UI visual similarity score is high ({score}%) — no refinement needed.")
            return False

        emit(f"UI visual similarity score is {score}% (< 98%). Running {self.framework} UI Regeneration Agent...")

        is_angular = "angular" in self.framework.lower()
        ext = "ts" if is_angular else settings.output_language
        src = file_manager.react_src_dir

        target_files = []

        if is_complex:
            fundamental = validation_report.get("fundamental_layout_failure", False)
            failed_comps = validation_report.get("failed_components", [])
            
            if fundamental:
                emit("  [WARN] Fundamental layout failure detected. Regenerating main layout...")
                target_files.append(src / f"App.{ext}")
            elif failed_comps:
                for comp in failed_comps:
                    cname = comp.get("component_name")
                    if cname:
                        for f in src.rglob(f"*.{ext}"):
                            if f.is_file() and cname.lower() in f.stem.lower():
                                target_files.append((f, comp.get("issues", [])))
                                break
        else:
            issues = validation_report.get("elements", [])
            missing = [e for e in issues if e.get("status") in ("Missing", "Extra", "Misaligned", "Wrong Size", "Wrong Style")]
            for e in missing:
                eid = e.get("element_id")
                if eid:
                    for f in src.rglob(f"*.{ext}"):
                        if f.is_file() and eid in f.read_text(encoding="utf-8") and f not in [t[0] if isinstance(t, tuple) else t for t in target_files]:
                            target_files.append(f)
                            
        if not target_files:
            # Fallback to naive search
            for f in src.rglob(f"*.{ext}"):
                if f.is_file() and f.stem not in ("App", "main"):
                    target_files.append(f)
                    break
        
        if not target_files:
            target_files.append(src / f"App.{ext}")
            
        success = False
        
        # We loop through target files. If it's a tuple, it's (file, issues_list)
        for target in target_files:
            if isinstance(target, tuple):
                component_file = target[0]
                issue_summary = ", ".join(target[1])
            else:
                component_file = target
                missing_names = [e.get("element_name", "") for e in validation_report.get("elements", []) if e.get("status") != "Correct"]
                issue_summary = ", ".join(missing_names[:10]) if missing_names else "general visual mismatch"

            css_name = component_file.stem + ".css"
            css_file = component_file.parent / css_name
            if not css_file.exists():
                css_file = src / css_name # Fallback to root css

            current_react = component_file.read_text(encoding="utf-8") if component_file.exists() else ""
            current_css = css_file.read_text(encoding="utf-8") if css_file.exists() else ""

            user_prompt = (
                f"Fix the following visual issues in this React {ext.upper()} component: {issue_summary}.\n\n"
                f"Current component ({component_file.name}):\n"
                f"```{ext}\n{current_react[:5000]}\n```\n\n"
                f"Current CSS ({css_name}):\n"
                f"```css\n{current_css[:2000]}\n```\n\n"
                f"Return Block 1 as the fixed {ext.upper()} component and Block 2 as the fixed CSS, "
                "each inside ```code fences```."
            )

        est_in = TokenManager.estimate_tokens(user_prompt + self._system_prompt)
        max_out = settings.max_output_tokens
        emit(f"  Original tokens: {est_in}")
        
        # Estimate after compression for logging
        compressed = TokenManager.compress_prompt([{"role": "user", "content": user_prompt}], settings.max_input_tokens)
        comp_in = TokenManager.estimate_tokens(compressed[0]["content"]) + TokenManager.estimate_tokens(self._system_prompt)
        if comp_in < est_in:
            emit(f"  Compressed tokens: {comp_in}")
        emit(f"  Max output: {max_out}")
        emit(f"  Estimated total: {comp_in + max_out}")

        # Use the configured code model first, with fast small models as fallbacks
        regen_models = [
            "openai/gpt-oss-120b",
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile"
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
            from rich.console import Console
            Console().print(f"[red]RAW OUTPUT DUMP:[/red]\n{raw_output}\n")
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
            success = True
            
        return success
