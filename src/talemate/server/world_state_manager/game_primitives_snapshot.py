"""Detached Game Primitives editor snapshot projection."""

from __future__ import annotations

from typing import Any

from talemate.game.primitives.adventure import AdventureDefinition, AdventureEngine
from talemate.game.primitives.anchors import (
    AnchorRef,
    PrimitiveRef,
    relationship_participants,
)
from talemate.game.primitives.constants import CURRENT_VERSION, GAME_PRIMITIVES_KEY
from talemate.game.primitives.constants import (
    ANCHOR_KINDS,
    CONDITION_KINDS,
    DEFINITION_EDITOR_KINDS,
    DEFINITION_KINDS,
    EDITABLE_DEFINITION_KINDS,
    EDITABLE_PRIMITIVE_KINDS,
    EFFECT_KINDS,
    PRIMITIVE_EDITOR_KINDS,
    PRIMITIVE_KINDS,
)
from talemate.game.primitives.render import RENDER_POLICIES
from talemate.game.primitives.definitions import MeterPayload
from talemate.game.primitives.draft_schema import DraftValidation
from talemate.game.primitives.exceptions import PrimitiveError, PrimitiveStoreError
from talemate.game.primitives.ledger import LedgerEntry
from talemate.game.primitives.relationships import RelationshipGraph
from talemate.game.primitives.store import PrimitiveStore
from talemate.game.primitives.store_snapshot import PrimitiveStoreSnapshot

from .game_primitives_snapshot_projections import (
    DEFINITION_SNAPSHOT_ADAPTER,
    AdventureStateSnapshot,
    AnchorSnapshot,
    CurrentAdventureSnapshot,
    DraftSnapshot,
    GamePrimitivesSnapshot,
    GamePrimitiveEditorMetadata,
    RelationshipSnapshot,
    StorySceneSnapshot,
)

#: Maximum number of newest ledger records exposed by an editor snapshot.
RECENT_LEDGER_LIMIT = 50


def _primitive_count(anchor: dict[str, Any]) -> int:
    return sum(len(values) for values in anchor["primitives"].values())


def _definition_title(definition_id: str, details: dict[str, Any]) -> str:
    for field in ("title", "name", "label"):
        value = details.get(field)
        if isinstance(value, str) and value:
            return value
    return definition_id


def _build_adventure_snapshot(
    scene: Any, store: PrimitiveStoreSnapshot
) -> CurrentAdventureSnapshot | None:
    engine = AdventureEngine()
    state = engine.get_state(scene, store=store)
    if state is None:
        return None
    definition_payload = store.get_definition("adventures", state.adventure_id)
    if definition_payload is None:
        raise PrimitiveError(
            f"Adventure definition '{state.adventure_id}' does not exist"
        )
    definition = AdventureDefinition.model_validate(definition_payload)
    story_scene = engine.get_current(scene, store=store)
    if story_scene is None:
        raise PrimitiveError(
            f"Adventure '{state.adventure_id}' could not resolve current story scene "
            f"'{state.current_story_scene}'"
        )
    return CurrentAdventureSnapshot(
        id=definition.id,
        title=definition.title,
        description=definition.description,
        current_story_scene=StorySceneSnapshot.model_validate(
            story_scene.model_dump(
                mode="json",
                include={
                    "id",
                    "title",
                    "description",
                    "location",
                    "intro",
                    "goals",
                    "local_anchors",
                    "render_policy",
                },
            )
        ),
        state=AdventureStateSnapshot(
            visited=state.visited,
            completed=state.completed,
            transition_log=state.transition_log,
        ),
        transitions=sorted(
            engine.list_transitions(scene, store=store), key=lambda item: item.id
        ),
    )


def build_game_primitives_snapshot(scene: Any) -> GamePrimitivesSnapshot:
    """Build a deterministic detached editor snapshot without scene mutation.

    Args:
        scene: Scene whose canonical primitive state is projected for inspection.

    Returns:
        A strict snapshot containing sorted definition, anchor, draft, and available
        transition catalogs; aggregate counts; the active adventure; up to 50 recent
        ledger records; and a revision of the complete canonical root.

    Raises:
        PrimitiveStoreError: If persisted primitive state is malformed or an anchor
            disappears from the detached snapshot during projection.
        PrimitiveError: If active adventure state cannot resolve its definition or
            current story scene.
        pydantic.ValidationError: If any persisted or projected typed payload is
            invalid.

    Side Effects:
        None. The returned models are detached, authored list order is preserved
        except for explicitly sorted catalogs, and an absent primitive root remains
        absent rather than being initialized.

    """
    initialized = GAME_PRIMITIVES_KEY in scene.game_state.variables
    store = PrimitiveStore.read_snapshot_for_scene(scene)

    definitions = []
    definition_counts = {}
    for kind in sorted(store.iter_definition_kinds()):
        collection = store.iter_definitions(kind)
        definition_counts[kind] = len(collection)
        for definition_id in sorted(collection):
            details = collection[definition_id]
            definitions.append(
                DEFINITION_SNAPSHOT_ADAPTER.validate_python(
                    {
                        "kind": kind,
                        "id": definition_id,
                        "title": _definition_title(definition_id, details),
                        "details": details,
                    }
                )
            )

    anchors = []
    relationships = []
    character_names = set(scene.all_character_names)
    relationship_graph = RelationshipGraph()
    for ref in sorted(store.iter_anchor_keys()):
        anchor_ref = AnchorRef.parse(ref)
        anchor = store.get_anchor(anchor_ref)
        if anchor is None:  # pragma: no cover
            raise PrimitiveStoreError(f"Snapshot anchor disappeared: {ref}")
        counts = {
            kind: len(values) for kind, values in sorted(anchor["primitives"].items())
        }
        anchors.append(
            AnchorSnapshot(
                ref=ref,
                kind=anchor_ref.kind,
                id=anchor_ref.id,
                tags=sorted(anchor["tags"]),
                meta=anchor["meta"],
                primitives=anchor["primitives"],
                primitive_counts=counts,
                primitive_count=sum(counts.values()),
                primitive_refs=sorted(
                    PrimitiveRef(anchor=anchor_ref, kind=kind, id=primitive_id).key()
                    for kind, values in anchor["primitives"].items()
                    for primitive_id in values
                ),
            )
        )
        if anchor_ref.kind == "relationship":
            source, target = relationship_participants(anchor_ref)
            missing = [name for name in (source, target) if name not in character_names]
            if missing:
                raise PrimitiveError(
                    f"Relationship anchor '{ref}' references missing character(s): "
                    + ", ".join(missing)
                )
            dimensions = [
                MeterPayload.model_validate(payload)
                for _, payload in sorted(
                    store.iter_primitives(anchor_ref, "meters").items()
                )
            ]
            relationships.append(
                RelationshipSnapshot(
                    anchor=ref,
                    source=source,
                    target=target,
                    summary=relationship_graph.summary(
                        scene, source, target, store=store
                    ),
                    dimensions=dimensions,
                )
            )

    drafts = []
    for draft_id, draft in sorted(store.iter_drafts().items()):
        drafts.append(
            DraftSnapshot(
                id=draft_id,
                status=draft["status"],
                created_by=draft["created_by"],
                definition_counts={
                    kind: len(values)
                    for kind, values in sorted(draft["definitions"].items())
                },
                anchor_count=len(draft["anchors"]),
                primitive_count=sum(
                    _primitive_count(anchor) for anchor in draft["anchors"].values()
                ),
                validation=DraftValidation.model_validate(draft["validation"]),
            )
        )

    return GamePrimitivesSnapshot(
        initialized=initialized,
        version=CURRENT_VERSION if initialized else None,
        revision=store.revision_token(),
        editor_metadata=get_game_primitive_editor_metadata(),
        definition_counts=definition_counts,
        definitions=definitions,
        anchor_count=len(anchors),
        primitive_count=sum(anchor.primitive_count for anchor in anchors),
        anchors=anchors,
        active_characters=sorted(scene.character_names),
        relationships=relationships,
        drafts=drafts,
        current_adventure=_build_adventure_snapshot(scene, store),
        recent_ledger=[
            LedgerEntry.model_validate(entry)
            for entry in store.recent_ledger(RECENT_LEDGER_LIMIT)
        ],
    )


def get_game_primitive_editor_metadata() -> GamePrimitiveEditorMetadata:
    """Project canonical backend registries into editor metadata."""
    return GamePrimitiveEditorMetadata(
        definition_kinds=list(DEFINITION_KINDS),
        editable_definition_kinds=list(EDITABLE_DEFINITION_KINDS),
        primitive_kinds=list(PRIMITIVE_KINDS),
        editable_primitive_kinds=list(EDITABLE_PRIMITIVE_KINDS),
        definition_editor_kinds=list(DEFINITION_EDITOR_KINDS),
        primitive_editor_kinds=list(PRIMITIVE_EDITOR_KINDS),
        anchor_kinds=list(ANCHOR_KINDS),
        condition_kinds=list(CONDITION_KINDS),
        effect_kinds=list(EFFECT_KINDS),
        render_policies=list(RENDER_POLICIES),
    )


__all__ = [
    "GamePrimitivesSnapshot",
    "build_game_primitives_snapshot",
    "get_game_primitive_editor_metadata",
]
