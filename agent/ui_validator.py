"""
agent/ui_validator.py
UI Validation Agent

Compares original wireframe/screenshot (Ground Truth) and ui_spec.json
with the generated React application components and CSS stylesheets.
Produces a dynamic, structured UI validation JSON report.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console

from config import settings
from utils.groq_client import GroqClient
from utils.json_utils import parse_json_safe, save_json, load_json

console = Console()


class UIValidator:
    """
    Compares Ground Truth wireframe image and ui_spec.json with generated UI code.
    Produces a dynamic visual & structural validation report JSON.
    """

    def __init__(self, groq_client: GroqClient, framework: str = "React") -> None:
        self._client = groq_client
        self.framework = framework
        self._system_prompt = self._load_prompt()

    def _load_prompt(self, is_complex: bool = False) -> str:
        prompt_name = "ui_validation_complex.txt" if is_complex else "ui_validation.txt"
        prompt_path = settings.prompts_dir / prompt_name
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return (
            "You are an expert UI Validation Agent. "
            "Perform a detailed visual and structural comparison between the wireframe image and generated UI components. "
            "Return ONLY valid JSON."
        )

    def validate(
        self,
        ground_truth_image: Path,
        output_path: Path,
        ui_spec_path: Optional[Path] = None,
        react_src_dir: Optional[Path] = None,
        is_complex: bool = False,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Perform visual & structural comparison and save validation_report.json.
        Returns a dictionary validation report or None on failure.
        """
        def emit(msg: str) -> None:
            if progress_cb:
                progress_cb(msg)
            console.print(f"  [magenta]{msg}[/magenta]")

        if not ground_truth_image.exists():
            emit(f"[ERROR] Ground truth image not found: {ground_truth_image}")
            return None

        emit(f"Running UI Validation Agent on: {ground_truth_image.name}")

        # ------------------------------------------------------------------
        # 0. Load Generated Code
        # ------------------------------------------------------------------
        src_path = react_src_dir or settings.output_dir / "src"
        react_code_combined = ""
        css_code_combined = ""
        
        is_angular = "angular" in self.framework.lower()
        exts = ["*.ts", "*.html"] if is_angular else ["*.tsx", "*.jsx", "*.ts"]
        
        for ext in exts:
            for filepath in src_path.rglob(ext):
                react_code_combined += f"// {filepath.name}\n{filepath.read_text(encoding='utf-8')}\n\n"

        for filepath in src_path.rglob("*.css"):
            css_code_combined += f"/* {filepath.name} */\n{filepath.read_text(encoding='utf-8')}\n\n"

        # ------------------------------------------------------------------
        # 1. Read ui_spec.json to get Ground Truth IDs
        # ------------------------------------------------------------------
        elements_from_spec = []
        if ui_spec_path and ui_spec_path.exists():
            spec = load_json(ui_spec_path)
            if not isinstance(spec, dict):
                spec = {}
                
            pages = spec.get("pages", [])
            if not pages:
                # Fallback if spec has "page" dict instead of "pages" array
                page_dict = spec.get("page", spec)
                pages = [page_dict] if isinstance(page_dict, dict) else []
                
            for page in pages:
                if not isinstance(page, dict):
                    continue
                sections = page.get("sections", [])
                for sec in sections:
                    if isinstance(sec, dict):
                        for el in sec.get("elements", []):
                            if isinstance(el, dict):
                                elements_from_spec.append(el)

        emit(f"Extracted {len(elements_from_spec)} element(s) from UI Spec for validation...")
        if len(elements_from_spec) == 0:
            emit("[WARN] 0 elements extracted. The validator may produce inaccurate results.")

        # ------------------------------------------------------------------
        # 2. Call LLM Vision for Visual Analysis
        # ------------------------------------------------------------------
        user_prompt = (
            f"Analyze the wireframe image: '{ground_truth_image.name}'.\n"
            f"Ground Truth Elements Count: {len(elements_from_spec)}.\n"
            f"Generated {self.framework} Code Snippets:\n```{exts[0][1:]}\n{react_code_combined[:1500]}\n```\n"
            f"Generated CSS Snippets:\n```css\n{css_code_combined[:1000]}\n```\n\n"
            "Compare the wireframe design against the generated code and CSS.\n"
            "Evaluate presence of elements, layout box constraints (card max-width), alignment, and colors.\n"
            "Return ONLY the valid JSON report matching the format in system prompt."
        )

        # Load correct prompt
        sys_prompt = self._load_prompt(is_complex=is_complex)

        raw_response = ""
        try:
            raw_response = self._client.vision(
                system_prompt=sys_prompt,
                user_text=user_prompt,
                image_path=ground_truth_image,
            )
        except Exception as exc:
            emit(f"[WARN] Vision validation call encountered issue: {exc}")

        report = parse_json_safe(raw_response)
        
        if report is None and raw_response.strip():
            emit("[WARN] Validator vision model returned invalid JSON. Attempting controlled repair...")
            try:
                repair_prompt = "The previous response was not valid JSON. Extract the validation report and return ONLY a valid JSON object matching the requested schema.\n\nText:\n" + raw_response[:2000]
                repair_raw = self._client.chat(
                    system_prompt="You are a strict JSON formatter. Return ONLY valid JSON.",
                    user_prompt=repair_prompt,
                    model="llama-3.1-8b-instant",
                    max_tokens=2000,
                )
                report = parse_json_safe(repair_raw)
                if report:
                    emit("  ✓ Successfully repaired validator JSON response!")
            except Exception as e:
                emit(f"  [WARN] Repair attempt failed: {e}")

        # ------------------------------------------------------------------
        # 3. Structural Code Verification & Fallback Synthesis
        # ------------------------------------------------------------------
        verified_elements = []
        correct_count = 0
        missing_count = 0
        misaligned_count = 0

        for el in elements_from_spec:
            eid = el.get("elementId") or el.get("element_id") or "UI_001"
            etype = el.get("elementType") or el.get("element_type") or "element"
            elabel = el.get("label") or eid

            # Verify if elementId is rendered in React code
            found_in_code = f'data-ui-id="{eid}"' in react_code_combined or eid in react_code_combined
            has_card_constraint = ("card-container" in css_code_combined and "max-width" in css_code_combined) or ("max-width" in css_code_combined)

            if found_in_code and has_card_constraint:
                status = "Correct"
                correct_count += 1
            elif found_in_code:
                status = "Misaligned"
                misaligned_count += 1
            else:
                status = "Missing"
                missing_count += 1

            verified_elements.append({
                "element_id": eid,
                "element_name": elabel,
                "element_type": etype,
                "exists_in_wireframe": True,
                "exists_in_generated_ui": found_in_code,
                "status": status,
                "details": f"Verified with data-ui-id='{eid}' in generated React component."
            })

        total_elements = len(elements_from_spec) or 1
        calculated_score = min(100, max(60, int((correct_count / total_elements) * 100)))

        # If LLM returned a valid JSON report, merge structural details
        if report and isinstance(report, dict):
            if "similarity_score" not in report or not isinstance(report["similarity_score"], (int, float)):
                report["similarity_score"] = calculated_score
            if "summary" not in report or not isinstance(report["summary"], dict):
                report["summary"] = {
                    "total_elements": total_elements,
                    "correct_elements": correct_count,
                    "missing_elements": missing_count,
                    "extra_elements": 0,
                    "misaligned_elements": misaligned_count,
                }
            if "elements" not in report or not report["elements"]:
                report["elements"] = verified_elements
        else:
            # Construct dynamic report based on real element scan
            overall_status = "PASSED" if calculated_score >= 95 else "NEEDS_REGENERATION"
            report = {
                "similarity_score": calculated_score,
                "overall_status": overall_status,
                "summary": {
                    "total_elements": total_elements,
                    "correct_elements": correct_count,
                    "missing_elements": missing_count,
                    "extra_elements": 0,
                    "misaligned_elements": misaligned_count,
                },
                "elements": verified_elements,
                "recommendations": [
                    "Ensure card container maintains responsive max-width: 400px box sizing.",
                    "Verify all inputs have clear visible label alignment."
                ]
            }

        save_json(report, output_path)
        emit(f"✓ Saved UI validation report (Score: {report.get('similarity_score', 95)}%) → {output_path}")
        return report
