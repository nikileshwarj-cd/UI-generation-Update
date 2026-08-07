"""
routes/api_routes.py
FastAPI router containing project management endpoints.
Migrated from Flask app_ui.py.
"""
from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from typing import Dict, Any, List

from models.project_model import ProjectCreatePayload, AddStoryPayload, ProjectUpdatePayload
from services.project_manager import (
    list_projects as db_list_projects,
    create_project as db_create_project,
    get_project_details as db_get_project_details,
    add_user_story_to_project as db_add_story,
    delete_project as db_delete_project,
    rename_project as db_rename_project
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

@router.get("")
def get_projects():
    """List projects directly from local SQLite Database (code_gene.db)."""
    return {"projects": db_list_projects()}

@router.post("")
def create_project(payload: ProjectCreatePayload):
    """Create a new project record in local SQLite Database."""
    try:
        res = db_create_project(payload)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}")
def get_project_by_id(project_id: str):
    """Retrieve details for a project from SQLite DB."""
    details = db_get_project_details(project_id)
    if details:
        return details
    raise HTTPException(status_code=404, detail="Project not found")

@router.delete("/{project_id}")
def delete_project_by_id(project_id: str):
    """Delete a project from SQLite DB."""
    success = db_delete_project(project_id)
    if success:
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Project not found")

@router.put("/{project_id}")
def update_project_by_id(project_id: str, payload: ProjectUpdatePayload):
    """Update a project's details in SQLite DB."""
    success = db_rename_project(project_id, payload.projectName)
    if success:
        return {"status": "updated"}
    raise HTTPException(status_code=404, detail="Project not found")

@router.post("/{project_id}/stories")
def add_story_to_project(
    project_id: str,
    userStory: str = Form(...),
    wireframe: UploadFile = File(...)
):
    """Add a new user story incrementally to SQLite DB using FormData."""
    import os
    import shutil
    
    story_text = userStory.strip()
    if not story_text:
        raise HTTPException(status_code=400, detail="User story is required")
        
    if not wireframe:
        raise HTTPException(status_code=400, detail="Wireframe image is mandatory")

    # Save wireframe to disk
    input_dir = "input"
    os.makedirs(input_dir, exist_ok=True)
    file_path = os.path.join(input_dir, wireframe.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(wireframe.file, buffer)

    try:
        payload = AddStoryPayload(userStory=story_text)
        res = db_add_story(project_id, payload, file_path)
        return res
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err))
    except Exception as err:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(err))
