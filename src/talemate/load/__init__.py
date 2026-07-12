"""Load, migrate, initialize, and transfer persisted Talemate scene data."""

import json
import os
import uuid
import traceback
from pathlib import Path

import structlog

import talemate.instance as instance
from talemate import Actor, Character, Player, Scene
from talemate.config import get_config, Config
from talemate.context import SceneIsLoading
from talemate.game.state import GameState
from talemate.scene_message import reset_message_id
from talemate.status import LoadingStatus, set_loading
from talemate.world_state import WorldState
from talemate.game.engine.nodes.registry import import_scene_node_definitions
from talemate.scene.intent import SceneIntent
from talemate.history import validate_history
import talemate.agents.tts.voice_library as voice_library
from talemate.changelog import _get_overall_latest_revision
from talemate.shared_context import SharedContext
from talemate.load.archive import load_scene_from_zip
from talemate.load.character_transfer import scene_stub, transfer_character
from talemate.load.history import load_history
from talemate.load.migrations import migrate_character_data, migrate_director_chat_state
from talemate.load.character_card import CharacterCardImportOptions

# Import character card functions
from talemate.load.character_card import (
    ImportSpec,
    identify_import_spec,
    load_scene_from_character_card,
    load_character_from_image,
    load_character_from_json,
)
from talemate.load.initialization import initialize_scene_primitives
from talemate.load.new_scene import (
    SceneInitialization,
    initialize_scene_intro as _initialize_scene_intro,
    new_scene,
)
from talemate.load.player import (
    default_player_character as default_player_character,
    handle_no_player_character,
)
from talemate.load.project import to_project_name

__all__ = [
    "ImportSpec",
    "SceneInitialization",
    "handle_no_player_character",
    "identify_import_spec",
    "load_character_from_image",
    "load_character_from_json",
    "load_scene",
    "load_scene_from_character_card",
    "load_scene_from_data",
    "load_scene_from_zip",
    "migrate_character_data",
    "migrate_director_chat_state",
    "normalize_scene_file_path",
    "scene_stub",
    "transfer_character",
]

log = structlog.get_logger("talemate.load")


def normalize_scene_file_path(file_path: str | os.PathLike[str] | None) -> str:
    """Return a non-empty filesystem scene path or raise a request error.

    Args:
        file_path: String or path-like scene location supplied by a caller.

    Returns:
        Normalized filesystem path string.

    Raises:
        ValueError: If the path is missing, unsupported, empty, or whitespace-only.

    """
    if file_path is None:
        raise ValueError("Scene file path is required")
    try:
        normalized = os.fsdecode(os.fspath(file_path))
    except TypeError as exc:
        raise ValueError("Scene file path must be a string or path-like value") from exc
    if not normalized.strip():
        raise ValueError("Scene file path cannot be empty")
    return normalized


@set_loading("Loading scene...")
async def load_scene(
    scene: Scene,
    file_path: str,
    reset: bool = False,
    add_to_recent: bool = True,
    scene_initialization: SceneInitialization | None = None,
):
    """Load scene data from a validated filesystem path.

    Args:
        scene: Scene instance to populate.
        file_path: String or path-like scene, archive, or character-card location.
        reset: Whether to reset persisted scene state while loading.
        add_to_recent: Whether to add a successful load to recent scenes.
        scene_initialization: Optional settings used when creating a new scene.

    Returns:
        The populated scene instance.

    Raises:
        ValueError: If ``file_path`` is missing or empty.
        TypeError: If scene data cannot be loaded into the expected models.
        OSError: If the source cannot be read.

    Side Effects:
        Reads source files; may create project storage, import archive assets,
        mutate and persist the scene, update recent scenes, and commit memory.

    """
    file_path = normalize_scene_file_path(file_path)

    exc = None
    try:
        with SceneIsLoading(scene):
            if file_path == "$NEW_SCENE$":
                if scene_initialization:
                    scene_data = new_scene(scene_initialization)
                else:
                    scene_data = new_scene()

                # If a project_name was provided, use it as the scene name
                # and normalize it for the project directory.
                # If no project_name, generate one for the directory but
                # leave the scene name/title blank.
                if scene_initialization and scene_initialization.project_name:
                    scene_data["name"] = scene_initialization.project_name
                    scene_data["project_name"] = to_project_name(
                        scene_initialization.project_name
                    )
                else:
                    generated_name = f"new-scene-{uuid.uuid4().hex[:6]}"
                    scene_data["project_name"] = generated_name
                    scene_data["name"] = ""

                scene = await load_scene_from_data(
                    scene, scene_data, reset=True, empty=True
                )

                # Create the scene directory on disk so assets are
                # written to the correct location even before the
                # user manually saves.
                _ = scene.save_dir

                return scene

            ext = os.path.splitext(file_path)[1].lower()

            # Character card import options from scene_initialization
            if (
                scene_initialization
                and scene_initialization.character_card_import_options
            ):
                import_options = scene_initialization.character_card_import_options
            else:
                import_options = CharacterCardImportOptions()

            # an image was uploaded, we don't have the scene data yet
            # go directly to loading a character card
            if ext in [".jpg", ".png", ".jpeg", ".webp"]:
                return await load_scene_from_character_card(
                    scene,
                    file_path,
                    import_options=import_options,
                )

            # a zip file was uploaded, extract and load complete scene
            if ext == ".zip":
                return await load_scene_from_zip(scene, file_path, reset)

            # a json file was uploaded, load the scene data
            with open(file_path, "r") as f:
                scene_data = json.load(f)

            # check if the data is a character card
            # this will also raise an exception if the data is not recognized
            spec = identify_import_spec(scene_data)

            # if it is a character card, load it
            if spec in [
                ImportSpec.chara_card_v1,
                ImportSpec.chara_card_v2,
                ImportSpec.chara_card_v3,
            ]:
                return await load_scene_from_character_card(
                    scene,
                    file_path,
                    import_options=import_options,
                )

            # if it is a talemate scene, load it
            return await load_scene_from_data(scene, scene_data, reset, name=file_path)
    except Exception as e:
        exc = e
        log.error("load_scene", error=traceback.format_exc())
        raise e
    finally:
        if add_to_recent and not exc:
            await scene.add_to_recent_scenes()
        if not exc:
            await scene.commit_to_memory()


async def load_scene_from_data(
    scene,
    scene_data,
    reset: bool = False,
    name: str | None = None,
    empty: bool = False,
) -> Scene:
    """Populate a scene from a mutable serialized scene mapping.

    The mapping is migrated in place before characters, history, assets, memory,
    world state, and optional new-scene primitives are initialized.

    Args:
        scene: Scene instance to populate.
        scene_data: Mutable serialized scene mapping.
        reset: Whether to discard persisted runtime state and history.
        name: Optional source name used to derive the scene filename.
        empty: Whether the mapping represents a new scene requiring initialization.

    Returns:
        The populated scene instance.

    Raises:
        KeyError: If required serialized scene fields are missing.
        pydantic.ValidationError: If serialized model data is invalid.

    Side Effects:
        Mutates ``scene_data`` during migration and populates ``scene``. May read
        shared context and assets, initialize agents and memory, activate actors,
        generate new-scene content, and initialize primitive state.

    """
    loading_status = LoadingStatus(1)
    reset_message_id()
    config: Config = get_config()

    memory = instance.get_agent("memory")

    migrate_character_data(scene_data)
    migrate_director_chat_state(scene_data)

    scene.description = scene_data.get("description", "")
    scene.intro = scene_data.get("intro", "") or scene.description
    scene.name = scene_data.get("name", "Unknown Scene")
    scene.environment = scene_data.get("environment", "scene")
    scene.filename = None
    scene.immutable_save = scene_data.get("immutable_save", False)
    scene.experimental = scene_data.get("experimental", False)
    scene.help = scene_data.get("help", "")
    scene.restore_from = scene_data.get("restore_from", "")
    scene.title = scene_data.get("title", "")
    scene.writing_style_template = scene_data.get("writing_style_template", "")
    scene.agent_persona_templates = scene_data.get("agent_persona_templates", {})
    scene.visual_style_template = scene_data.get("visual_style_template", "")
    scene.nodes_filename = scene_data.get("nodes_filename", "")
    scene.creative_nodes_filename = scene_data.get("creative_nodes_filename", "")
    scene.character_data = {
        name: Character(**character_data)
        for name, character_data in scene_data.get("character_data", {}).items()
    }
    scene.active_characters = scene_data.get("active_characters", [])
    scene.context = scene_data.get("context", "")
    scene.perspective = scene_data.get("perspective", "")
    scene.project_name = scene_data.get("project_name")
    scene.intent_state = SceneIntent(**scene_data.get("intent_state", {}))
    scene.history = load_history(scene_data["history"])
    scene.archived_history = scene_data["archived_history"]
    scene.layered_history = scene_data.get("layered_history", [])

    # load shared context
    shared_context_file = scene_data.get("shared_context", "")
    if shared_context_file:
        log.info(
            "Loading shared context from file", shared_context_file=shared_context_file
        )
        path = Path(scene.shared_context_dir) / shared_context_file
        if not path.exists():
            log.warning(
                "Shared context file not found", shared_context_file=shared_context_file
            )
            scene.shared_context = None
        else:
            scene.shared_context = SharedContext(filepath=path)
            await scene.shared_context.init_from_file()
            await scene.shared_context.update_to_scene(scene)
    else:
        scene.shared_context = None

    import_scene_node_definitions(scene)

    if not reset:
        scene.id = scene_data.get("id", scene.id)
        scene.memory_id = scene_data.get("memory_id", scene.memory_id)
        scene.saved_memory_session_id = scene_data.get("saved_memory_session_id", None)
        scene.memory_session_id = scene_data.get("memory_session_id", None)
        scene.world_state = WorldState(**scene_data.get("world_state", {}))
        scene.game_state = GameState(**scene_data.get("game_state", {}))
        scene.agent_state = scene_data.get("agent_state", {})
        scene.game_state_watch_paths = scene_data.get("game_state_watch_paths", [])
        scene.filename = os.path.basename(
            name or scene.name.lower().replace(" ", "_") + ".json"
        )
        scene.fix_time()
        log.debug("scene time", ts=scene.ts)
    else:
        scene.history = []
        scene.archived_history = []
        scene.layered_history = []
        scene.intent_state.reset()

    scene.assets.cover_image = scene_data.get("assets", {}).get("cover_image", None)
    scene.assets.load_assets(scene_data.get("assets", {}).get("assets", {}))

    # Clean up cover images and message avatars that reference non-existent assets
    scene.assets.cleanup_cover_images()
    scene.assets.cleanup_message_avatars()

    loading_status("Initializing long-term memory...")

    await memory.set_db()
    # await memory.remove_unsaved_memory()

    await scene.world_state_manager.remove_all_empty_pins()

    if not scene.memory_session_id:
        scene.set_new_memory_session_id()

    if not reset:
        await validate_history(scene, commit_to_memory=False)

    # Activate active characters
    # Only activate characters that exist in character_data
    for character_name in scene_data["active_characters"]:
        if character_name not in scene.character_data:
            log.warning(
                "Character not found in character_data, skipping activation",
                character_name=character_name,
                available_characters=list(scene.character_data.keys()),
            )
            continue

        character = scene.character_data[character_name]

        if not character.is_player:
            agent = instance.get_agent("conversation")
            actor = Actor(character=character, agent=agent)
        else:
            actor = Player(character=character, agent=None)
        await scene.add_actor(actor, commit_to_memory=False)

    # if there is no player character, add the default player character
    await handle_no_player_character(
        scene,
        add_default_character=config.game.general.add_default_character,
        reset=reset,
    )

    # the scene has been saved before (since we just loaded it), so we set the saved flag to True
    # as long as the scene has a memory_id.
    scene.saved = "memory_id" in scene_data

    # load the scene voice library
    scene.voice_library = await voice_library.load_scene_voice_library(scene)
    log.debug("scene voice library", voice_library=scene.voice_library)

    scene.rev = _get_overall_latest_revision(scene)
    log.debug("Loaded scene", rev=scene.rev)

    # Initialize intro and title for new scenes
    await _initialize_scene_intro(scene, scene_data, empty)
    await initialize_scene_primitives(scene, scene_data, empty)

    return scene
