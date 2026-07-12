"""Character and character-asset transfer between scenes."""

import json
import os

import structlog

import talemate.instance as instance
from talemate import Actor, Character, Player, Scene
from talemate.character import deactivate_character
from talemate.load.migrations import migrate_character_data
from talemate.scene_assets import AssetTransfer

log = structlog.get_logger("talemate.load.character_transfer")


def scene_stub(scene_path: str, scene_data: dict | None = None) -> Scene:
    """Create a minimal scene configured to resolve a source scene's assets.

    The source JSON is read only when ``scene_data`` is omitted.

    Args:
        scene_path: Path whose filename and parent identify the source scene.
        scene_data: Parsed source scene data, or ``None`` to read ``scene_path``.

    Returns:
        A scene with only its filename, name, and project name configured.

    Raises:
        OSError: ``scene_path`` cannot be read when data is not supplied.
        json.JSONDecodeError: The source file is not valid JSON.

    """
    if scene_data is None:
        with open(scene_path) as scene_file:
            scene_data = json.load(scene_file)

    scene = Scene()
    scene.filename = os.path.basename(scene_path)
    scene.name = scene_data.get("name")
    scene.project_name = os.path.basename(os.path.dirname(scene_path))
    return scene


async def _transfer_asset(
    scene: Scene, source_scene: Scene, source_asset_id: str
) -> str | None:
    transfer = AssetTransfer(
        source_scene_path=os.path.join(source_scene.save_dir, source_scene.filename),
        asset_id=source_asset_id,
    )
    if not await scene.assets.transfer_asset(transfer):
        return None
    if not scene.assets.validate_asset_id(source_asset_id):
        log.warning(
            "_transfer_asset",
            message="Asset ID validation failed after transfer",
            asset_id=source_asset_id,
        )
        return None
    return source_asset_id


async def transfer_character_cover_image(
    scene: Scene, source_scene: Scene, character: Character, source_asset_id: str
) -> str | None:
    """Copy and assign a character cover image.

    Args:
        scene: Destination scene.
        source_scene: Scene used to locate the source asset.
        character: Destination character whose cover image is updated.
        source_asset_id: Source asset identifier to copy and assign.

    Returns:
        ``source_asset_id`` after a validated transfer, otherwise ``None``.

    Side Effects:
        Copies the asset into ``scene`` and updates the character's cover image
        only when transfer and validation succeed.

    """
    asset_id = await _transfer_asset(scene, source_scene, source_asset_id)
    if not asset_id:
        return None
    await scene.assets.set_character_cover_image(
        character, source_asset_id, override=True
    )
    return source_asset_id


async def transfer_character_avatar_assets(
    scene: Scene, source_scene: Scene, character: Character
) -> None:
    """Copy a character's default and current avatar assets.

    Args:
        scene: Destination scene.
        source_scene: Scene used to locate source assets.
        character: Destination character whose avatar references are updated.

    Side Effects:
        Copies each referenced avatar asset into ``scene``. Each reference is
        reassigned after a successful transfer or cleared when transfer or
        validation fails.

    """
    if character.avatar:
        asset_id = await _transfer_asset(scene, source_scene, character.avatar)
        if asset_id:
            await scene.assets.set_character_avatar(character, asset_id, override=True)
        else:
            character.avatar = None
            log.debug(
                "transfer_character_avatar_assets",
                message="Cleared avatar - asset not found in source",
                character=character.name,
            )

    if character.current_avatar:
        asset_id = await _transfer_asset(scene, source_scene, character.current_avatar)
        if asset_id:
            await scene.assets.set_character_current_avatar(
                character, asset_id, override=True
            )
        else:
            character.current_avatar = None
            log.debug(
                "transfer_character_avatar_assets",
                message="Cleared current_avatar - asset not found in source",
                character=character.name,
            )


async def transfer_character(
    scene: Scene,
    scene_json_path: str,
    character_name: str,
    defer_asset_transfer: bool = False,
) -> Scene:
    """Load a named character from another scene and add it as an inactive actor.

    Asset transfer may be deferred for callers that manage it separately.

    Args:
        scene: Destination scene.
        scene_json_path: Path to the serialized source scene.
        character_name: Exact key of the character to transfer.
        defer_asset_transfer: Leave cover and avatar assets uncopied when true.

    Returns:
        The destination ``scene`` after adding and deactivating the character.

    Raises:
        OSError: The source scene cannot be read or an asset cannot be copied.
        json.JSONDecodeError: The source scene is not valid JSON.
        ValueError: The source scene has no character named ``character_name``.

    Side Effects:
        Migrates the parsed source data, optionally copies character assets,
        adds an actor to ``scene``, and deactivates the transferred character.

    """
    with open(scene_json_path) as scene_file:
        scene_data = json.load(scene_file)
    migrate_character_data(scene_data)

    character_data = scene_data.get("character_data", {}).get(character_name)
    if not character_data:
        raise ValueError(
            f"Character '{character_name}' not found in the scene file "
            f"'{scene_json_path}'"
        )

    character = Character(**character_data)
    original_cover_image = character.cover_image
    has_avatar_assets = character.avatar or character.current_avatar
    if (original_cover_image or has_avatar_assets) and not defer_asset_transfer:
        source_scene = scene_stub(scene_json_path, scene_data)
        if original_cover_image:
            await transfer_character_cover_image(
                scene, source_scene, character, original_cover_image
            )
        if has_avatar_assets:
            await transfer_character_avatar_assets(scene, source_scene, character)

    agent = instance.get_agent("conversation")
    actor = (
        Actor(character, agent) if not character.is_player else Player(character, None)
    )
    await scene.add_actor(actor)
    await deactivate_character(scene, character.name)
    return scene
