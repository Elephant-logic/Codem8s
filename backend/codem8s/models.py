from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime

class BuildRequest(BaseModel):
    idea: str = Field(min_length=3)
    stack: str = "react-fastapi"
    use_ai: bool = True

class ChangeRequest(BaseModel):
    instruction: str = Field(min_length=3)

class FileSpec(BaseModel):
    path: str
    purpose: str
    status: str = "pending"
    content: str = ""
    errors: List[str] = []
    attempts: int = 0

class ProjectSpec(BaseModel):
    app_name: str
    goal: str
    stack: str
    features: List[str]
    files: Dict[str, str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    change_log: List[str] = []

class BuildState(BaseModel):
    project_id: str
    use_ai: bool = True
    spec: ProjectSpec
    files: Dict[str, FileSpec]
    logs: List[str] = []
    current_file: Optional[str] = None
    status: str = "planned"
