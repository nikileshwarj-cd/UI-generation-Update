"""
models/project_model.py
Pydantic models for API Payloads.
"""
from pydantic import BaseModel
from typing import List, Optional

class ProjectCreatePayload(BaseModel):
    projectName: str
    framework: str = "React"
    language: str = "TypeScript"
    cssStrategy: str = "Tailwind CSS (Utility-first)"
    folderStructure: str = "Feature-based"

class ProjectUpdatePayload(BaseModel):
    projectName: str

class AddStoryPayload(BaseModel):
    userStory: str
