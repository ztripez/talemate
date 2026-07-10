"""Post-load initialization for explicitly requested scene primitives."""

import structlog
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

import talemate.instance as instance
from talemate import Scene
from talemate.emit import emit

log = structlog.get_logger("talemate.load.initialization")


class PrimitiveBundleInitialization(BaseModel):
    """Primitive bundle fields extracted from a complete scene payload."""

    # This focused boundary receives complete scene data, so unrelated keys are retained.
    model_config = ConfigDict(extra="allow")

    generate_primitive_bundle: StrictBool = Field(
        False,
        description=(
            "Explicit opt-in to generate and commit a primitive scenario bundle; "
            "defaults to false"
        ),
    )
    primitive_bundle_description: StrictStr | None = Field(
        None,
        description=(
            "Optional non-coerced generation premise used before scene text; "
            "defaults to none"
        ),
    )
    intro_instructions: StrictStr | None = Field(
        None,
        description=(
            "Optional non-coerced intro instructions used as the final premise "
            "fallback; defaults to none"
        ),
    )


async def initialize_scene_primitives(
    scene: Scene, scene_data: dict, empty: bool
) -> None:
    """Generate explicitly requested Game Primitives for a new, empty scene.

    Args:
        scene: Scene that receives the committed primitive bundle and generation result.
        scene_data: Complete scene payload containing strict primitive initialization
            fields. Unrelated fields are accepted.
        empty: Whether the scene is being initialized as a new, empty scene. Primitive
            generation is skipped when false.

    Returns:
        None.

    Raises:
        pydantic.ValidationError: If a primitive initialization field has an invalid
            type.
        Exception: If primitive generation raises an unexpected prompt, focal, or
            service error.

    Side Effects:
        Clears the scene's previous primitive initialization result. When generation
        is explicitly enabled for an empty scene, selects the first non-empty premise
        from the requested description, scene description, scene intro, or intro
        instructions; requests and commits a generated bundle; stores its serialized
        result on the scene; and emits an error status for an expected failed result.
    """
    initialization = PrimitiveBundleInitialization.model_validate(scene_data)
    scene.primitive_scenario_bundle_initialization_result = None
    if not empty or not initialization.generate_primitive_bundle:
        return

    description = next(
        (
            premise
            for premise in (
                initialization.primitive_bundle_description,
                scene.description,
                scene.intro,
                initialization.intro_instructions,
            )
            if premise
        ),
        "",
    )
    creator = instance.get_agent("creator")
    result = await creator.generate_primitive_bundle_for_scenario(
        scene=scene,
        description=description,
        characters=list(scene.character_data),
        auto_commit=True,
    )
    result_json = result.model_dump(mode="json")
    scene.primitive_scenario_bundle_initialization_result = result_json

    if not result.ok:
        log.error("generate primitives during load failed", errors=result.errors)
        emit(
            "status",
            message="Primitive scenario initialization failed",
            status="error",
            scene=scene,
            data={"primitive_scenario_bundle_result": result_json},
        )
