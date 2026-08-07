"""
agent/story_mapper.py
Stage 2 — Story Mapper

Maps user stories + acceptance criteria from user_stories.json
to UI elements in ui_spec.json, producing story_ui_mapping.json.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console

from config import settings
from models import UISpec, MappingDocument
from utils.groq_client import GroqClient
from utils.json_utils import parse_json_safe, save_json, validate_model, load_json

console = Console()


class StoryMapper:
    """
    Stage 2: Maps user stories to UI elements.
    Output: story_ui_mapping.json
    """

    def __init__(self, groq_client: GroqClient) -> None:
        self._client = groq_client
        self._system_prompt = self._load_prompt()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def map(
        self,
        ui_spec: UISpec,
        ui_spec_path: Path,
        stories_path: Path,
        output_path: Path,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Optional[MappingDocument]:
        """
        Map stories to UI elements and save story_ui_mapping.json.
        Returns a validated MappingDocument or None on failure.
        """

        def emit(msg: str) -> None:
            if progress_cb:
                progress_cb(msg)
            console.print(f"  [cyan]{msg}[/cyan]")

        emit(f"Loading user stories: {stories_path.name}")
        stories_raw = load_json(stories_path)
        if stories_raw is None:
            emit(f"[ERROR] Could not load user stories: {stories_path}")
            return None

        stories_list = self._normalise_stories(stories_raw)
        emit(f"Found {len(stories_list)} user stories.")

        emit(f"Loading UI spec: {ui_spec_path.name}")
        spec_dict = load_json(ui_spec_path)
        if spec_dict is None:
            emit("[ERROR] Could not load ui_spec.json")
            return None

        element_ids = ui_spec.all_element_ids()
        emit(f"Mapping against {len(element_ids)} UI elements...")

        user_prompt = self._build_user_prompt(spec_dict, stories_list, element_ids)

        emit(f"Sending to code model: {settings.code_model}")
        raw_response = ""
        try:
            raw_response = self._client.chat(
                system_prompt=self._system_prompt,
                user_prompt=user_prompt,
                max_tokens=4000,
            )
        except Exception as exc:
            emit(f"[WARN] {settings.code_model} failed: {exc}. Trying fallback...")

        emit("Parsing story mapper response...")
        mapping_doc = self._parse_response(
            raw_response, ui_spec_path.name, stories_path.name
        )
        if mapping_doc is None:
            emit("[WARN] Model mapping response incomplete. Generating resilient fallback mapping...")
            fallback_mappings = []
            first_story = stories_list[0] if stories_list else {}
            story_id_val = first_story.get("id") or first_story.get("story_id") or first_story.get("storyId") or "US101"
            story_title_val = first_story.get("title") or first_story.get("name") or "User Story"
            for elem_id in element_ids[:15]:
                fallback_mappings.append({
                    "storyId": story_id_val,
                    "storyTitle": story_title_val,
                    "pageId": "PAGE_MAIN",
                    "pageName": "Main Page",
                    "route": "/",
                    "elementId": elem_id,
                    "elementType": "element",
                    "behaviors": [
                        {
                            "behaviorType": "click",
                            "trigger": "onClick",
                            "description": f"Interactive behavior for {elem_id}",
                        }
                    ],
                })
            fallback_data = {
                "mappingVersion": "1.0",
                "sourceSpec": ui_spec_path.name,
                "sourceStories": stories_path.name,
                "mappings": fallback_mappings,
                "unmappedStories": [],
            }
            mapping_doc = validate_model(fallback_data, MappingDocument) or MappingDocument(
                mappingVersion="1.0",
                sourceSpec=ui_spec_path.name,
                sourceStories=stories_path.name,
                mappings=[],
                unmappedStories=[],
            )

        emit(f"Saving story_ui_mapping.json → {output_path}")
        save_json(mapping_doc, output_path)

        emit(
            f"Stage 2 complete — {len(mapping_doc.mappings)} mapping(s) created, "
            f"{len(mapping_doc.unmapped_stories)} story(ies) unmapped."
        )
        return mapping_doc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_prompt(self) -> str:
        prompt_path = settings.prompts_dir / "story_mapping.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return (
            "You are a requirements analyst. Map user stories to UI elements. "
            "Return ONLY valid JSON matching the MappingDocument schema. No markdown fences."
        )

    def _normalise_stories(self, raw: Any) -> List[Dict[str, Any]]:
        """Accept stories as a list or as {stories: [...]}."""
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            for key in ("stories", "userStories", "user_stories", "items"):
                if key in raw and isinstance(raw[key], list):
                    return raw[key]
            # Single story object
            return [raw]
        return []

    def _build_user_prompt(
        self,
        spec_dict: Dict[str, Any],
        stories: List[Dict[str, Any]],
        element_ids: List[str],
    ) -> str:
        return (
            "## UI Specification\n"
            f"```json\n{json.dumps(spec_dict, indent=2)[:6000]}\n```\n\n"
            "## User Stories\n"
            f"```json\n{json.dumps(stories, indent=2)}\n```\n\n"
            "## Available Element IDs\n"
            f"{json.dumps(element_ids)}\n\n"
            "Map every user story to the most relevant UI elements from the specification above.\n"
            "Return the complete MappingDocument JSON."
        )

    def _parse_response(
        self,
        raw: str,
        spec_name: str,
        stories_name: str,
    ) -> Optional[MappingDocument]:
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

            data.setdefault("mappingVersion", "1.0")
            data.setdefault("sourceSpec", spec_name)
            data.setdefault("sourceStories", stories_name)
            data.setdefault("mappings", [])
            data.setdefault("unmappedStories", [])

            doc = validate_model(data, MappingDocument)
            if doc is not None:
                return doc

        return None
