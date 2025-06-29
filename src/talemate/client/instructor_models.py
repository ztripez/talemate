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


class DirectorGuidanceResponse(BaseModel):
    """Structured response for director guidance to actors or narrator."""
    guidance: str = Field(description="The guidance text for actors or narrator")
    focus_areas: Optional[List[str]] = Field(default=None, description="Key areas the actor/narrator should focus on")
    tone: Optional[str] = Field(default=None, description="Suggested tone or mood for the response")
    character_insights: Optional[List[str]] = Field(default=None, description="Relevant character background or motivations")


class DirectorChoicesResponse(BaseModel):
    """Structured response for player action choices."""
    choices: List[str] = Field(description="List of actionable choices for the player", min_items=1)
    context: Optional[str] = Field(default=None, description="Context or reasoning behind these choices")
    urgency: Optional[str] = Field(default=None, description="How urgent or time-sensitive these choices are")


class DirectorSceneAnalysisResponse(BaseModel):
    """Structured response for scene analysis and direction."""
    scene_assessment: str = Field(description="Analysis of the current scene state")
    recommended_direction: str = Field(description="Recommended direction for the scene")
    key_elements: Optional[List[str]] = Field(default=None, description="Key elements to focus on")
    pacing: Optional[str] = Field(default=None, description="Recommended pacing for the scene")


class CreatorCharacterResponse(BaseModel):
    """Structured response for character creation tasks."""
    content: str = Field(description="The main generated content (name, description, etc.)")
    character_traits: Optional[List[str]] = Field(default=None, description="Key character traits identified")
    content_type: Optional[str] = Field(default=None, description="Type of content (name, description, dialogue_instructions, etc.)")
    
    
class CreatorContextualResponse(BaseModel):
    """Structured response for contextual content generation."""
    content: str = Field(description="The generated content")
    content_type: str = Field(description="Type of content generated")
    context_category: Optional[str] = Field(default=None, description="Category of the context (character, scene, world, etc.)")
    length_category: Optional[str] = Field(default=None, description="Length category (short, medium, long)")
    
    
class CreatorAutocompleteResponse(BaseModel):
    """Structured response for autocomplete suggestions."""
    suggestion: str = Field(description="The autocomplete suggestion")
    suggestion_type: str = Field(description="Type of suggestion (dialogue, narrative)")
    confidence: Optional[float] = Field(default=None, description="Confidence in the suggestion (0.0-1.0)")
    alternative_suggestions: Optional[List[str]] = Field(default=None, description="Alternative suggestions")


class CreatorListResponse(BaseModel):
    """Structured response for list generation."""
    items: List[str] = Field(description="Generated list items", min_items=1)
    list_type: Optional[str] = Field(default=None, description="Type of list generated")
    total_items: Optional[int] = Field(default=None, description="Total number of items in the list")


class CreatorTitleResponse(BaseModel):
    """Structured response for title generation."""
    title: str = Field(description="The generated title")
    title_type: Optional[str] = Field(default=None, description="Type of title (scene, story, character, etc.)")
    alternative_titles: Optional[List[str]] = Field(default=None, description="Alternative title suggestions")


class WorldStateResponse(BaseModel):
    """Structured response for world state tracking."""
    characters: Dict[str, Dict[str, str]] = Field(
        description="Characters with their emotions and current activities",
        default_factory=dict
    )
    items: Optional[Dict[str, Dict[str, str]]] = Field(
        default=None,
        description="Items and their current states"
    )
    location: Optional[str] = Field(
        default=None,
        description="Current location description"
    )
    
    
class WorldStateAnalysisResponse(BaseModel):
    """Structured response for text analysis and questions."""
    answer: str = Field(description="The analysis result or answer to the question")
    confidence: Optional[float] = Field(default=None, description="Confidence in the answer (0.0-1.0)")
    supporting_evidence: Optional[List[str]] = Field(default=None, description="Evidence supporting the answer")
    
    
class WorldStateQueryResponse(BaseModel):
    """Structured response for generating RAG queries."""
    queries: List[str] = Field(description="List of search queries for memory/context", min_items=1)
    query_types: Optional[List[str]] = Field(default=None, description="Types of queries (character, event, location, etc.)")
    
    
class WorldStateCharacterIdentificationResponse(BaseModel):
    """Structured response for character identification."""
    characters: List[Dict[str, str]] = Field(
        description="List of identified characters with names and descriptions",
        min_items=0
    )
    
    
class WorldStateCharacterSheetResponse(BaseModel):
    """Structured response for character sheet extraction."""
    attributes: Dict[str, str] = Field(
        description="Character attributes as key-value pairs",
        default_factory=dict
    )
    character_name: str = Field(description="Name of the character")
    
    
class WorldStateReinforcementResponse(BaseModel):
    """Structured response for state reinforcement updates."""
    answer: str = Field(description="The reinforcement answer or value")
    reinforcement_type: Optional[str] = Field(default=None, description="Type of reinforcement (question/attribute)")
    confidence: Optional[str] = Field(default=None, description="Confidence level in the answer")
    
    
class WorldStatePinConditionResponse(BaseModel):
    """Structured response for pin condition checks."""
    conditions: Dict[str, Dict[str, bool]] = Field(
        description="Pin conditions with their updated states",
        default_factory=dict
    )