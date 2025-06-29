"""
Pydantic models for structured LLM responses using instructor.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class NarratorResponse(BaseModel):
    """Structured response from narrator agent."""
    narration: str = Field(description="The main narrative text")
    scene_elements: Optional[List[str]] = Field(default=None, description="Key scene elements described")
    mood: Optional[str] = Field(default=None, description="Overall mood or atmosphere")
    characters_involved: Optional[List[str]] = Field(default=None, description="Characters mentioned or involved")