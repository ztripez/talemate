"""Migrations for persisted scene data."""

import uuid

import structlog

log = structlog.get_logger("talemate.load.migrations")


def migrate_character_data(scene_data: dict) -> None:
    """Migrate legacy character collections into ``character_data`` in place.

    Args:
        scene_data: Mutable serialized scene mapping.

    Side Effects:
        When ``character_data`` is absent, creates it and ``active_characters``,
        copies inactive and active characters into it, and records active names.
        Existing ``character_data`` makes the migration a no-op.

    Invariants:
        Inactive characters remain inactive; characters from ``characters`` are
        listed in ``active_characters``.

    """
    if "character_data" in scene_data:
        return

    log.info("Migrating to new character data storage format")
    scene_data["character_data"] = {}
    scene_data["active_characters"] = []

    for character_name, character in scene_data.get("inactive_characters", {}).items():
        scene_data["character_data"][character_name] = character

    for character in scene_data.get("characters", []):
        scene_data["character_data"][character["name"]] = character
        scene_data["active_characters"].append(character["name"])


def migrate_director_chat_state(scene_data: dict) -> None:
    """Migrate legacy singleton director chat state in place.

    Args:
        scene_data: Mutable serialized scene mapping.

    Side Effects:
        Replaces the director's legacy ``chat`` with a ``chats`` mapping and
        ``last_active_chat_id``. Missing IDs are generated, missing creation
        times become zero, and migrated titles become ``Original Chat``.
        Missing director state and already-migrated state are unchanged.

    Invariants:
        A migrated nonempty chat is keyed by its ID and is the last active chat;
        an absent legacy chat produces an empty ``chats`` mapping.

    """
    director_state = scene_data.get("agent_state", {}).get("director", {})
    if not director_state or "chats" in director_state:
        return

    old_chat = director_state.pop("chat", None)
    if old_chat:
        chat_id = old_chat.get("id", str(uuid.uuid4())[:10])
        old_chat["title"] = "Original Chat"
        if "created_at" not in old_chat:
            old_chat["created_at"] = 0
        director_state["chats"] = {chat_id: old_chat}
        director_state["last_active_chat_id"] = chat_id
        log.info(
            "Migrated singleton director chat to multi-chat format", chat_id=chat_id
        )
    else:
        director_state["chats"] = {}
