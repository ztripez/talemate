"""New-scene configuration and serialized construction."""

import pydantic
import structlog

import talemate.instance as instance
from talemate import Scene
from talemate.load.character_card import CharacterCardImportOptions
from talemate.scene.intent import SceneIntent

log = structlog.get_logger("talemate.load.new_scene")


class SceneInitialization(pydantic.BaseModel):
    """Validate optional content and primitive-generation inputs for a new scene.

    Attributes:
        project_name: Persistent project identifier.
        content_classification: Classification exposed as scene context.
        agent_persona_templates: Persona template names keyed by agent name.
        writing_style_template: Writing-style template name.
        shared_context: Context shared by scene agents.
        active_characters: Names of characters active at initialization.
        character_data: Serialized characters keyed by name.
        intro_instructions: Instructions used to generate an intro.
        intro: Explicit intro text, taking precedence over generation instructions.
        assets: Serialized initial asset metadata.
        intent_state: Initial scene intent.
        character_card_import_options: Character-card import configuration.
        generate_primitive_bundle: Whether primitive generation is requested;
            accepts booleans without coercion.
        primitive_bundle_description: Primitive-generation description; accepts
            strings without coercion.
        context: Read-only alias for ``content_classification``.

    """

    project_name: str | None = None
    content_classification: str | None = None
    agent_persona_templates: dict[str, str | None] | None = None
    writing_style_template: str | None = None
    shared_context: str | None = None
    active_characters: list[str] | None = None
    character_data: dict | None = None
    intro_instructions: str | None = None
    intro: str | None = None
    assets: dict | None = None
    intent_state: SceneIntent | None = None
    character_card_import_options: CharacterCardImportOptions | None = None
    # Generation must be explicit; these strict fields must not coerce API input.
    generate_primitive_bundle: pydantic.StrictBool = pydantic.Field(False)
    primitive_bundle_description: pydantic.StrictStr | None = pydantic.Field(None)

    @pydantic.computed_field(description="Content classification")
    @property
    def context(self) -> str | None:
        """Return the content classification used as scene context."""
        return self.content_classification


async def initialize_scene_intro(scene: Scene, scene_data: dict, empty: bool) -> None:
    """Apply or generate intro and title content for an empty new scene.

    Args:
        scene: Scene whose intro and title may be initialized.
        scene_data: Initialization mapping containing ``intro`` or
            ``intro_instructions``.
        empty: Whether the scene is eligible for intro initialization.

    Side Effects:
        For an empty scene, assigns explicit intro text or generates it from
        instructions, then generates a title only when none exists. Generation
        failures are logged and suppressed; a false ``empty`` is a no-op.

    """
    try:
        if not empty:
            return

        has_intro_content = False
        if scene_data.get("intro"):
            scene.intro = scene_data["intro"]
            has_intro_content = True
        elif scene_data.get("intro_instructions"):
            creator = instance.get_agent("creator")
            scene.intro = await creator.contextual_generate_from_args(
                context="scene intro:scene intro",
                instructions=scene_data.get("intro_instructions", ""),
                length=312,
                uid="load.new_scene_intro",
            )
            has_intro_content = True

        if not scene.title and has_intro_content:
            creator = instance.get_agent("creator")
            scene.title = await creator.generate_scene_title()
    except Exception as exc:
        # Intro generation has historically been best-effort during scene creation.
        log.error("generate intro during load", error=exc)


def new_scene(scene_initialization: SceneInitialization | None = None) -> dict:
    """Create the serialized baseline for a new scene.

    Args:
        scene_initialization: Validated overrides, excluding fields set to
            ``None``.

    Returns:
        A new mutable scene mapping with empty history and character collections.

    Invariants:
        The baseline environment is ``scene`` and its collection values are new
        objects on every call.

    """
    scene_data = {
        "description": "",
        "name": "New scenario",
        "environment": "scene",
        "history": [],
        "archived_history": [],
        "character_data": {},
        "active_characters": [],
    }
    if scene_initialization:
        scene_data.update(scene_initialization.model_dump(exclude_none=True))
    return scene_data
