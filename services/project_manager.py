"""
services/project_manager.py
Project Manager Service using Embedded SQLite Database (code_gene.db).
"""
import json
import uuid
from typing import List, Dict, Any, Optional

from models.project_model import (
    ProjectCreatePayload,
    AddStoryPayload
)
from models.database import (
    SessionLocal,
    ProjectDB,
    UserStoryDB,
    CodeFileDB,
    init_db
)

def list_projects() -> List[Dict[str, Any]]:
    init_db()
    db = SessionLocal()
    try:
        projects_db = db.query(ProjectDB).all()
        result = []
        for p in projects_db:
            stories = [
                {
                    "id": s.story_code,
                    "title": s.title,
                    "component": s.component_name,
                    "dependsOn": json.loads(s.depends_on_json or "[]")
                }
                for s in p.stories
            ]
            result.append({
                "config": {
                    "projectId": p.id,
                    "projectName": p.name,
                    "framework": p.framework,
                    "language": p.language,
                    "cssStrategy": p.css_strategy,
                    "folderStructure": p.folder_structure
                },
                "storyCount": len(stories),
                "stories": stories
            })
        return result
    finally:
        db.close()

def create_project(payload: ProjectCreatePayload) -> Dict[str, Any]:
    init_db()
    db = SessionLocal()
    try:
        count = db.query(ProjectDB).count()
        project_id = f"P{count + 1:03d}"
        clean_name = payload.projectName.strip() or f"Project_{project_id}"

        proj = ProjectDB(
            id=project_id,
            name=clean_name,
            framework=payload.framework,
            language=payload.language,
            css_strategy=payload.cssStrategy,
            folder_structure=payload.folderStructure
        )
        db.add(proj)
        db.commit()

        return {
            "status": "created",
            "config": {
                "projectId": project_id,
                "projectName": clean_name,
                "framework": payload.framework,
                "language": payload.language,
                "cssStrategy": payload.cssStrategy,
                "folderStructure": payload.folderStructure
            }
        }
    finally:
        db.close()

def get_project_details(project_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    db = SessionLocal()
    try:
        p = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
        if not p:
            return None

        stories = [
            {
                "id": s.story_code,
                "title": s.title,
                "component": s.component_name,
                "dependsOn": json.loads(s.depends_on_json or "[]")
            }
            for s in p.stories
        ]

        files = [{"path": f.file_path, "content": f.content} for f in p.files]

        return {
            "config": {
                "projectId": p.id,
                "projectName": p.name,
                "framework": p.framework,
                "language": p.language,
                "cssStrategy": p.css_strategy,
                "folderStructure": p.folder_structure
            },
            "storyGraph": {
                "projectId": p.id,
                "stories": stories
            },
            "filesScanned": files
        }
    finally:
        db.close()

def delete_project(project_id: str) -> bool:
    init_db()
    db = SessionLocal()
    try:
        p = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
        if not p:
            return False
        db.delete(p)
        db.commit()
        return True
    finally:
        db.close()

def rename_project(project_id: str, new_name: str) -> bool:
    init_db()
    db = SessionLocal()
    try:
        p = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
        if not p:
            return False
        p.name = new_name
        db.commit()
        return True
    finally:
        db.close()

def add_user_story_to_project(project_id: str, payload: AddStoryPayload, wireframe_path: str) -> Dict[str, Any]:
    from pathlib import Path
    from utils.groq_client import GroqClient
    from utils.file_manager import FileManager
    from agent.image_analyzer import ImageAnalyzer
    from agent.story_mapper import StoryMapper
    from agent.code_generator import CodeGenerator
    from agent.ui_validator import UIValidator
    from agent.ui_regenerator import UIRegenerator
    
    init_db()
    db = SessionLocal()
    try:
        p = db.query(ProjectDB).filter(ProjectDB.id == project_id).first()
        if not p:
            raise ValueError(f"Project '{project_id}' not found.")

        # --- Dynamic AI Pipeline ---
        groq_client = GroqClient()
        fm = FileManager(project_name=p.name)

        # Stage 1: Analyze Image
        ia = ImageAnalyzer(groq_client)
        spec_path = fm.metadata_dir / "ui_spec.json"
        
        ui_spec = ia.analyze(
            image_path=Path(wireframe_path),
            output_path=spec_path,
            progress_cb=lambda msg: print(f"AI Pipeline: {msg}")
        )
        if not ui_spec:
            raise ValueError("Failed to analyze image and generate UI Spec")

        # Stage 2: Map User Story
        # Create a mock user_stories.json
        existing_stories = p.stories
        next_num = len(existing_stories) + 1
        story_id_code = f"US{next_num:03d}"
        
        user_stories = {
            "stories": [
                {
                    "storyId": story_id_code,
                    "description": payload.userStory
                }
            ]
        }
        stories_path = fm.metadata_dir / "user_stories.json"
        fm.write_text(stories_path, json.dumps(user_stories, indent=2))
        
        sm = StoryMapper(groq_client)
        mapping_path = fm.metadata_dir / "ui_mapping.json"
        mapping_doc = sm.map(
            ui_spec=ui_spec,
            ui_spec_path=spec_path,
            stories_path=stories_path,
            output_path=mapping_path,
            progress_cb=lambda msg: print(f"AI Pipeline: {msg}")
        )
        if not mapping_doc:
            raise ValueError("Failed to map user stories to UI Spec")

        # Stage 3: Generate Code
        cg = CodeGenerator(groq_client, framework=p.framework)
        cg.generate(
            image_path=Path(wireframe_path),
            ui_spec=ui_spec,
            ui_spec_path=spec_path,
            mapping_doc=mapping_doc,
            mapping_path=mapping_path,
            file_manager=fm,
            project_name=p.name,
            css_strategy=p.css_strategy,
            progress_cb=lambda msg: print(f"AI Pipeline: {msg}")
        )
        # Stage 4: Validate
        validator = UIValidator(groq_client, framework=p.framework)
        val_report_path = fm.metadata_dir / "validation.json"
        val_report = validator.validate(
            ground_truth_image=Path(wireframe_path),
            output_path=val_report_path,
            ui_spec_path=spec_path,
            progress_cb=lambda msg: print(f"AI Pipeline: {msg}")
        )
        
        # Stage 5: Regenerate
        regenerator = UIRegenerator(groq_client, framework=p.framework)
        regenerated = regenerator.regenerate(
            file_manager=fm,
            validation_report=val_report,
            project_name=p.name,
            progress_cb=lambda msg: print(f"AI Pipeline: {msg}")
        )
        
        # --- Save Generated Code to Database ---
        new_files = []
        for file_ext in ["*.jsx", "*.tsx", "*.js", "*.ts", "*.css"]:
            for filepath in fm.react_src_dir.rglob(file_ext):
                # Ensure we only add files that were generated during this run
                # Actually, we'll just upsert them. We'll delete existing ones or just add.
                # To be safe, we'll add all files from src and overwrite if necessary.
                rel_path = filepath.relative_to(fm.react_src_dir.parent)
                str_path = str(rel_path).replace("\\", "/")
                
                # Check if it already exists in DB
                existing = db.query(CodeFileDB).filter(CodeFileDB.project_id == p.id, CodeFileDB.file_path == str_path).first()
                if existing:
                    existing.content = filepath.read_text(encoding="utf-8")
                else:
                    db.add(CodeFileDB(
                        id=str(uuid.uuid4()),
                        project_id=p.id,
                        file_path=str_path,
                        content=filepath.read_text(encoding="utf-8")
                    ))
                new_files.append(str_path)

        # Create Story Record
        existing_stories = p.stories
        next_num = len(existing_stories) + 1
        story_id_code = f"US{next_num:03d}"
        
        # We can extract the component from the mapping doc instead of the old static function
        comp_name = "Component"
        if mapping_doc.mappings:
            first_mapping = mapping_doc.mappings[0]
            if isinstance(first_mapping, dict):
                comp_name = first_mapping.get("element_id", "Component")
            elif hasattr(first_mapping, "element_id"):
                comp_name = getattr(first_mapping, "element_id")
        
        story_rec = UserStoryDB(
            id=str(uuid.uuid4()),
            project_id=p.id,
            story_code=story_id_code,
            title=payload.userStory[:40] + ("..." if len(payload.userStory) > 40 else ""),
            description=payload.userStory,
            component_name=comp_name,
            depends_on_json=json.dumps([s.story_code for s in existing_stories])
        )
        db.add(story_rec)
        db.commit()

        # Build Response
        all_stories = [
            {
                "id": s.story_code,
                "title": s.title,
                "component": s.component_name,
                "dependsOn": json.loads(s.depends_on_json or "[]")
            }
            for s in p.stories
        ]

        return {
            "status": "success",
            "storyId": story_id_code,
            "component": comp_name,
            "dependsOn": [s.story_code for s in existing_stories],
            "newFilesGenerated": new_files,
            "storyGraph": {
                "projectId": p.id,
                "stories": all_stories
            }
        }
    finally:
        db.close()

def extract_component_name(user_story: str, fallback_idx: int) -> str:
    text = user_story.lower()
    if "log in" in text or "login" in text or "auth" in text:
        return "Login"
    if "dashboard" in text or "analytics" in text or "overview" in text:
        return "Dashboard"
    if "profile" in text or "user info" in text or "edit account" in text:
        return "Profile"
    if "cart" in text or "checkout" in text:
        return "Checkout"
    if "product" in text or "catalog" in text:
        return "Products"
    return f"Feature{fallback_idx}"
