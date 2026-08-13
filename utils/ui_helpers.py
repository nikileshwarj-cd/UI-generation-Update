from typing import Dict, Any

def is_complex_ui(page_dict: Dict[str, Any]) -> bool:
    """
    Heuristic to detect complex UIs based on structural markers.
    """
    complex_keywords = {"dashboard", "sidebar", "chart", "graph", "table", "grid"}
    element_count = 0
    section_count = 0
    has_complex_elements = False

    def traverse(el):
        nonlocal element_count, has_complex_elements
        element_count += 1
        if isinstance(el, dict):
            etype = el.get("elementType", "").lower()
            eid = el.get("elementId", "").lower()
            if any(kw in etype or kw in eid for kw in complex_keywords):
                has_complex_elements = True
            
            children = el.get("children", [])
            if isinstance(children, list):
                for child in children:
                    traverse(child)

    sections = page_dict.get("sections", [])
    if isinstance(sections, list):
        section_count = len(sections)
        for sec in sections:
            elements = sec.get("elements", [])
            if isinstance(elements, list):
                for el in elements:
                    traverse(el)
    else:
        elements = page_dict.get("elements", [])
        if isinstance(elements, list):
            for el in elements:
                traverse(el)

    if has_complex_elements or section_count > 2 or element_count >= 6:
        return True
    return False
