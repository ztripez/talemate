from __future__ import annotations

import json
import os

import talemate.client as client
from talemate.agents.base import Agent, set_processing
from talemate.agents.registry import register
from talemate.agents.memory.rag import MemoryRAGMixin
from talemate.emit import emit
from talemate.prompts import Prompt

from .assistant import AssistantMixin
from .character import CharacterCreatorMixin
from .scenario import ScenarioCreatorMixin

from talemate.agents.base import AgentAction

import talemate.agents.creator.nodes

@register()
class CreatorAgent(
    CharacterCreatorMixin,
    ScenarioCreatorMixin,
    AssistantMixin,
    MemoryRAGMixin,
    Agent,
):
    """
    Creates characters and scenarios and other fun stuff!
    """

    agent_type = "creator"
    verbose_name = "Creator"

    @classmethod
    def init_actions(cls) -> dict[str, AgentAction]:
        actions = {}
        MemoryRAGMixin.add_actions(actions)
        AssistantMixin.add_actions(actions)
        return actions

    def __init__(
        self,
        model_preset=None,
        scene_config=None,
        client: client.ClientBase = None,
        **kwargs,
    ):
        # Use base class constructor for ModelPreset-first pattern
        super().__init__(model_preset=model_preset, scene_config=scene_config, client=client, **kwargs)

    @set_processing
    async def generate_title(self, text: str):
        from talemate.client.instructor_models import CreatorTitleResponse
        
        # Try clean prompt system first
        response = await self.request_with_instructor(
            "generate-title",
            vars={
                "text": text,
            },
            response_model=CreatorTitleResponse,
            kind="create_short",
            max_tokens=getattr(self.client, 'max_token_length', 512),
        )
        
        # Extract title from structured response
        if isinstance(response, CreatorTitleResponse):
            return response.title
        else:
            return response
