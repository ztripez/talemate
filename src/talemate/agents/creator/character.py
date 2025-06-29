from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from talemate.agents.base import set_processing
from talemate.prompts import Prompt

import talemate.game.focal as focal

if TYPE_CHECKING:
    from talemate.tale_mate import Character

log = structlog.get_logger("talemate.agents.creator.character")

DEFAULT_CONTENT_CONTEXT = "a fun and engaging adventure aimed at an adult audience."


class CharacterCreatorMixin:

    @set_processing
    async def determine_content_context_for_character(
        self,
        character: Character,
    ):
        # Try clean prompt system first
        try:
            from talemate.client.instructor_models import CreatorCharacterResponse
            
            response = await self.request_with_instructor(
                "determine-content-context",
                vars={
                    "character": character,
                },
                response_model=CreatorCharacterResponse,
                kind="create_192",
                max_tokens=getattr(self.client, 'max_token_length', 512),
            )
            
            # Extract content from structured response
            if isinstance(response, CreatorCharacterResponse):
                content_context = response.content
            else:
                content_context = response
                
        except Exception as e:
            # Fallback to legacy prompt system
            content_context = await Prompt.request(
                f"creator.determine-content-context",
                self.client,
                "create_192",
                vars={
                    "character": character,
                },
            )
            
        return content_context.split("\n")[0].strip()

    @set_processing
    async def determine_character_dialogue_instructions(
        self,
        character: Character,
        instructions: str = "",
        information: str = "",
    ):
        from talemate.client.instructor_models import CreatorCharacterResponse
        
        response = await self.request_with_instructor(
            "determine-character-dialogue-instructions",
            vars={
                "character": character,
                "scene": self.scene,
                "max_tokens": getattr(self.client, 'max_token_length', 512),
                "instructions": instructions,
                "information": information,
            },
            response_model=CreatorCharacterResponse,
            kind="create_concise",
            max_tokens=getattr(self.client, 'max_token_length', 512),
        )

        # Extract instructions from structured response
        if isinstance(response, CreatorCharacterResponse):
            result = response.content
        else:
            result = response
            
        r = result.strip().split("\n")[0].strip('"').strip()
        return r

    @set_processing
    async def determine_character_attributes(
        self,
        character: Character,
    ):
        # Try clean prompt system first
        try:
            from talemate.client.instructor_models import CreatorCharacterResponse
            
            response = await self.request_with_instructor(
                "determine-character-attributes",
                vars={
                    "character": character,
                },
                response_model=CreatorCharacterResponse,
                kind="analyze_long",
                max_tokens=getattr(self.client, 'max_token_length', 512),
            )
            
            # Extract attributes from structured response
            if isinstance(response, CreatorCharacterResponse):
                attributes = response.content
            else:
                attributes = response
                
        except Exception as e:
            # Fallback to legacy prompt system
            attributes = await Prompt.request(
                f"creator.determine-character-attributes",
                self.client,
                "analyze_long",
                vars={
                    "character": character,
                },
            )
            
        return attributes

    @set_processing
    async def determine_character_name(
        self,
        character_name: str,
        allowed_names: list[str] = None,
        group: bool = False,
        instructions: str = "",
    ) -> str:
        from talemate.client.instructor_models import CreatorCharacterResponse
        
        response = await self.request_with_instructor(
            "determine-character-name",
            vars={
                "scene": self.scene,
                "max_tokens": getattr(self.client, 'max_token_length', 512),
                "character_name": character_name,
                "allowed_names": allowed_names or [],
                "group": group,
                "instructions": instructions,
            },
            response_model=CreatorCharacterResponse,
            kind="analyze_freeform_short",
            max_tokens=getattr(self.client, 'max_token_length', 512),
        )
        
        # Extract name from structured response
        if isinstance(response, CreatorCharacterResponse):
            name = response.content
        else:
            name = response
            
        return name.split('"', 1)[0].strip().strip(".").strip()

    @set_processing
    async def determine_character_description(
        self, 
        character: Character,
        text: str = "",
        instructions: str = "",
        information: str = "",
    ):
        from talemate.client.instructor_models import CreatorCharacterResponse
        
        response = await self.request_with_instructor(
            "determine-character-description",
            vars={
                "character": character,
                "scene": self.scene,
                "text": text,
                "max_tokens": getattr(self.client, 'max_token_length', 512),
                "instructions": instructions,
                "information": information,
            },
            response_model=CreatorCharacterResponse,
            kind="create",
            max_tokens=getattr(self.client, 'max_token_length', 512),
        )
        
        # Extract description from structured response
        if isinstance(response, CreatorCharacterResponse):
            description = response.content
        else:
            description = response
            
        return description.strip()

    @set_processing
    async def determine_character_goals(
        self,
        character: Character,
        goal_instructions: str,
    ):
        # Try clean prompt system first
        try:
            from talemate.client.instructor_models import CreatorCharacterResponse
            
            response = await self.request_with_instructor(
                "determine-character-goals",
                vars={
                    "character": character,
                    "scene": self.scene,
                    "goal_instructions": goal_instructions,
                    "npc_name": character.name,
                    "player_name": self.scene.get_player_character().name,
                    "max_tokens": getattr(self.client, 'max_token_length', 512),
                },
                response_model=CreatorCharacterResponse,
                kind="create",
                max_tokens=getattr(self.client, 'max_token_length', 512),
            )
            
            # Extract goals from structured response
            if isinstance(response, CreatorCharacterResponse):
                goals = response.content
            else:
                goals = response
                
        except Exception as e:
            # Fallback to legacy prompt system
            goals = await Prompt.request(
                f"creator.determine-character-goals",
                self.client,
                "create",
                vars={
                    "character": character,
                    "scene": self.scene,
                    "goal_instructions": goal_instructions,
                    "npc_name": character.name,
                    "player_name": self.scene.get_player_character().name,
                    "max_tokens": getattr(self.client, 'max_token_length', 512),
                },
            )

        log.debug("determine_character_goals", goals=goals, character=character)
        await character.set_detail("goals", goals.strip())

        return goals.strip()