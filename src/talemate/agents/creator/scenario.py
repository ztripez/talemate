from talemate.agents.base import set_processing
from talemate.prompts import Prompt


class ScenarioCreatorMixin:
    """
    Adds scenario creation functionality to the creator agent
    """

    @set_processing
    async def determine_scenario_description(self, text: str):
        # Try clean prompt system first
        try:
            from talemate.client.instructor_models import CreatorCharacterResponse
            
            response = await self.request_with_instructor(
                "determine-scenario-description",
                vars={
                    "text": text,
                },
                response_model=CreatorCharacterResponse,
                kind="analyze_long",
                max_tokens=getattr(self.client, 'max_token_length', 512),
            )
            
            # Extract description from structured response
            if isinstance(response, CreatorCharacterResponse):
                description = response.content
            else:
                description = response
                
        except Exception as e:
            # Fallback to legacy prompt system
            description = await Prompt.request(
                f"creator.determine-scenario-description",
                self.client,
                "analyze_long",
                vars={
                    "text": text,
                },
            )
            
        return description.strip()

    @set_processing
    async def determine_content_context_for_description(
        self,
        description: str,
    ):
        # Try clean prompt system first
        try:
            from talemate.client.instructor_models import CreatorCharacterResponse
            
            response = await self.request_with_instructor(
                "determine-content-context",
                vars={
                    "description": description,
                },
                response_model=CreatorCharacterResponse,
                kind="create_short",
                max_tokens=getattr(self.client, 'max_token_length', 512),
            )
            
            # Extract content context from structured response
            if isinstance(response, CreatorCharacterResponse):
                content_context = response.content
            else:
                content_context = response
                
        except Exception as e:
            # Fallback to legacy prompt system
            content_context = await Prompt.request(
                f"creator.determine-content-context",
                self.client,
                "create_short",
                vars={
                    "description": description,
                },
            )
            
        return content_context.lstrip().split("\n")[0].strip('"').strip()
