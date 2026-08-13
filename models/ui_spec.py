"""
models/ui_spec.py
Pydantic schemas for Stage 1 output: ui_spec.json
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class UIElement(BaseModel):
    """A single detected UI element on a page."""

    element_id: str = Field(
        ...,
        alias="elementId",
        description="Unique element ID, e.g. UI_EMAIL_001",
    )
    element_type: str = Field(
        default="div",
        alias="elementType",
        description="input | button | text | heading | image | card | nav | form | link | icon | list | table | modal | other",
    )

    @field_validator("element_type", mode="before")
    @classmethod
    def coerce_element_type(cls, v: Any) -> str:
        if v is None or not str(v).strip():
            return "div"
        return str(v).strip()

    label: str = Field(default="", description="Visible text label or placeholder")

    @field_validator("label", mode="before")
    @classmethod
    def coerce_label_str(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)
    placeholder: Optional[str] = Field(default=None)
    html_tag: str = Field(default="div", alias="htmlTag")
    input_type: Optional[str] = Field(
        default=None,
        alias="inputType",
        description="email | password | text | number | checkbox | radio | submit | etc.",
    )
    # Style hints extracted from the image
    color: Optional[str] = Field(default=None, description="Dominant color or hex")
    background_color: Optional[str] = Field(default=None, alias="backgroundColor")
    font_size: Optional[str] = Field(default=None, alias="fontSize")
    font_weight: Optional[str] = Field(default=None, alias="fontWeight")
    border_radius: Optional[str] = Field(default=None, alias="borderRadius")
    width: Optional[str] = Field(default=None)
    height: Optional[str] = Field(default=None)
    position: Optional[str] = Field(
        default=None,
        description="Relative position hint: top-left | center | bottom-right | etc.",
    )
    # Children (for container elements)
    children: List["UIElement"] = Field(default_factory=list)
    # Free-form extra attributes
    attributes: Dict[str, Any] = Field(default_factory=dict)
    description: str = Field(default="", description="Human-readable description")

    model_config = {"populate_by_name": True}

    @field_validator("element_id", mode="before")
    @classmethod
    def validate_element_id(cls, v: Any) -> str:
        if v is None or not str(v).strip():
            import uuid
            return f"UI_EL_{uuid.uuid4().hex[:6].upper()}"
        val = str(v).strip()
        if not val.upper().startswith("UI_"):
            return f"UI_{val.upper().lstrip('_')}"
        return val.upper()


class UISection(BaseModel):
    """A logical section/region within a page (e.g. header, hero, footer)."""

    section_id: str = Field(default="SECTION_001", alias="sectionId")

    @field_validator("section_id", mode="before")
    @classmethod
    def coerce_section_id(cls, v: Any) -> str:
        if v is None or not str(v).strip():
            import uuid
            return f"SECTION_{uuid.uuid4().hex[:6].upper()}"
        return str(v).strip()

    section_type: str = Field(
        default="section",
        alias="sectionType",
        description="header | hero | nav | sidebar | main | footer | modal | other",
    )

    @field_validator("section_type", mode="before")
    @classmethod
    def coerce_section_type(cls, v: Any) -> str:
        if v is None or not str(v).strip():
            return "section"
        return str(v).strip()
    label: str = Field(default="")

    @field_validator("label", mode="before")
    @classmethod
    def coerce_section_label(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)
    layout: str = Field(
        default="column",
        description="row | column | grid | flex | absolute",
    )
    background_color: Optional[str] = Field(default=None, alias="backgroundColor")
    elements: List[UIElement] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class UIPage(BaseModel):
    """A single page / screen in the application."""

    page_id: str = Field(..., alias="pageId", description="e.g. PAGE_LOGIN")
    page_name: str = Field(..., alias="pageName")
    route: str = Field(default="/", description="React Router route path")
    layout: str = Field(
        default="centered",
        description="Overall layout: centered | sidebar | dashboard | fullscreen",
    )
    # Color palette
    primary_color: Optional[str] = Field(default=None, alias="primaryColor")
    secondary_color: Optional[str] = Field(default=None, alias="secondaryColor")
    background_color: Optional[str] = Field(default=None, alias="backgroundColor")
    font_family: Optional[str] = Field(default=None, alias="fontFamily")
    sections: List[UISection] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    def all_elements(self) -> List[Any]:
        """Flatten all elements across all sections, handling both Pydantic models and raw dicts."""
        elements: List[Any] = []
        for section in self.sections:
            sec_elements = section.elements if hasattr(section, 'elements') else (section.get('elements', []) if isinstance(section, dict) else [])
            for el in sec_elements:
                elements.append(el)
                children = el.children if hasattr(el, 'children') else (el.get('children', []) if isinstance(el, dict) else [])
                for child in children:
                    elements.append(child)
        return elements


class UISpec(BaseModel):
    """Top-level output of Stage 1 — Image Analyzer."""

    spec_version: str = Field(default="1.0", alias="specVersion")
    source_image: str = Field(..., alias="sourceImage")
    pages: List[UIPage] = Field(default_factory=list)
    # Global design tokens
    design_tokens: Dict[str, Any] = Field(default_factory=dict, alias="designTokens")
    # Summary of detected elements
    element_summary: Dict[str, int] = Field(
        default_factory=dict, alias="elementSummary"
    )

    model_config = {"populate_by_name": True}

    def all_element_ids(self) -> List[str]:
        ids = []
        for page in self.pages:
            if isinstance(page, dict):
                def extract_ids(obj):
                    if isinstance(obj, dict):
                        if "elementId" in obj: ids.append(obj["elementId"])
                        elif "element_id" in obj: ids.append(obj["element_id"])
                        for v in obj.values(): extract_ids(v)
                    elif isinstance(obj, list):
                        for item in obj: extract_ids(item)
                extract_ids(page)
            else:
                for el in page.all_elements():
                    eid = el.element_id if hasattr(el, "element_id") else (el.get("element_id") or el.get("elementId") if isinstance(el, dict) else None)
                    if eid:
                        ids.append(eid)
        return list(dict.fromkeys(ids))
