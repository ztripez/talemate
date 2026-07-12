"""Conversion of persisted history into scene messages."""

from talemate.scene_message import (
    MESSAGES,
    CharacterMessage,
    DirectorMessage,
    NarratorMessage,
    ReinforcementMessage,
    SceneMessage,
)


def load_history(history: list) -> list[SceneMessage]:
    """Convert supported serialized history entries to scene messages.

    Args:
        history: Entries represented as legacy strings or current dictionaries.

    Returns:
        Messages in input order. Entries of any other type are omitted.

    Raises:
        TypeError: A supported dictionary cannot initialize its message class.

    Side Effects:
        Removes migration-only keys from dictionary entries in ``history`` and
        may migrate source or message text into message metadata.

    """
    loaded = []
    for entry in history:
        if isinstance(entry, str):
            loaded.append(_prepare_legacy_history(entry))
        elif isinstance(entry, dict):
            loaded.append(_prepare_history(entry))
    return loaded


def _prepare_history(entry: dict) -> SceneMessage:
    typ = entry.pop("typ", "scene_message")
    entry.pop("id", None)
    if entry.get("source") == "":
        entry.pop("source")

    message = MESSAGES.get(typ, SceneMessage)(**entry)
    if isinstance(message, (NarratorMessage, ReinforcementMessage)):
        return message.migrate_source_to_meta()
    if isinstance(message, DirectorMessage):
        return message.migrate_message_to_meta()
    return message


def _prepare_legacy_history(entry: str) -> SceneMessage:
    if entry.startswith("*"):
        cls = NarratorMessage
    elif entry.startswith("Director instructs"):
        cls = DirectorMessage
    else:
        cls = CharacterMessage
    return cls(entry)
