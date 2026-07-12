"""Player recovery policy for loaded scenes."""

import structlog

from talemate import Character, Player, Scene
from talemate.character import activate_character
from talemate.config import Config, get_config
from talemate.config.schema import GamePlayerCharacter

log = structlog.get_logger("talemate.load.player")


async def handle_no_player_character(
    scene: Scene, add_default_character: bool = True, reset: bool = False
) -> None:
    """Recover an existing player or create the configured default player.

    Args:
        scene: Loaded scene requiring an active player character.
        add_default_character: Add the configured default when none is found.
        reset: Search all scene characters for an inactive player during reset.

    Side Effects:
        Activates the existing player, or during reset the first player in
        character data. Otherwise, optionally adds and activates the configured
        default. Logs a warning when no player can be selected.

    Invariants:
        An existing player always takes precedence over reset recovery and the
        configured default.

    """
    existing_player = scene.get_player_character()
    if existing_player:
        await activate_character(scene, existing_player)
        return

    # Reset loads may contain an inactive player that should take precedence.
    if reset:
        for character in scene.character_data.values():
            if character.is_player:
                await activate_character(scene, character)
                return

    player = default_player_character() if add_default_character else None
    if not player:
        log.warning("No player character found")
        return

    await scene.add_actor(player)
    await activate_character(scene, player.character)


def default_player_character() -> Player | None:
    """Build the configured default player from application configuration.

    Returns:
        A new player with the configured name, description, and color, or
        ``None`` when the configured name is empty.

    Side Effects:
        Reads the current application configuration.

    """
    config: Config = get_config()
    default: GamePlayerCharacter = config.game.default_player_character
    if not default.name:
        return None

    return Player(
        Character(
            name=default.name,
            description=default.description,
            greeting_text="",
            color=default.color,
        ),
        None,
    )
