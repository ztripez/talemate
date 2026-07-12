"""Canonical strict request union and coverage assertion."""

from typing import Annotated, get_args

import pydantic

from talemate.game.primitives.definitions import EDITABLE_DEFINITION_KINDS
from talemate.game.primitives.primitive_payloads import EDITABLE_PRIMITIVE_KINDS

from .game_primitives_adventure_requests import (
    ActivateGamePrimitiveAdventurePayload,
    GetGamePrimitiveEditorMetadataPayload,
    GetGamePrimitivesPayload,
    TakeGamePrimitiveAdventureTransitionPayload,
)
from .game_primitives_anchor_instance_requests import (
    AdjustGamePrimitivePayload,
    DeleteGamePrimitiveAnchorPayload,
    DeleteGamePrimitivePayload,
    PreviewDeleteGamePrimitiveAnchorPayload,
    PreviewDeleteGamePrimitivePayload,
    PrimitiveChange,
    UpsertGamePrimitiveAnchorPayload,
    UpsertGamePrimitivePayload,
)
from .game_primitives_draft_definition_requests import (
    CommitGamePrimitiveDraftPayload,
    CreateGamePrimitiveDraftPayload,
    DefinitionChange,
    DeleteGamePrimitiveDefinitionPayload,
    DeleteGamePrimitiveDraftPayload,
    GetGamePrimitiveDraftPayload,
    ListGamePrimitiveDraftsPayload,
    UpsertGamePrimitiveDefinitionPayload,
    ValidateGamePrimitiveDraftPayload,
)
from .game_primitives_bundle_requests import (
    ApplyGamePrimitiveBundlePayload,
    CaptureGamePrimitiveBundlePayload,
    PreviewGamePrimitiveBundlePayload,
)
from .game_primitives_relationship_requests import (
    AuthorGamePrimitiveRelationshipPayload,
)

GamePrimitivesRequest = Annotated[
    GetGamePrimitivesPayload
    | GetGamePrimitiveEditorMetadataPayload
    | ActivateGamePrimitiveAdventurePayload
    | TakeGamePrimitiveAdventureTransitionPayload
    | ListGamePrimitiveDraftsPayload
    | CreateGamePrimitiveDraftPayload
    | GetGamePrimitiveDraftPayload
    | DeleteGamePrimitiveDraftPayload
    | ValidateGamePrimitiveDraftPayload
    | CommitGamePrimitiveDraftPayload
    | UpsertGamePrimitiveDefinitionPayload
    | DeleteGamePrimitiveDefinitionPayload
    | UpsertGamePrimitiveAnchorPayload
    | DeleteGamePrimitiveAnchorPayload
    | PreviewDeleteGamePrimitiveAnchorPayload
    | UpsertGamePrimitivePayload
    | DeleteGamePrimitivePayload
    | PreviewDeleteGamePrimitivePayload
    | AuthorGamePrimitiveRelationshipPayload
    | AdjustGamePrimitivePayload
    | CaptureGamePrimitiveBundlePayload
    | PreviewGamePrimitiveBundlePayload
    | ApplyGamePrimitiveBundlePayload,
    pydantic.Field(discriminator="action"),
]

# This is intentionally the only request-union adapter.
GAME_PRIMITIVES_REQUEST_ADAPTER = pydantic.TypeAdapter(GamePrimitivesRequest)


def _kind_values(union: object) -> tuple[str, ...]:
    members = get_args(get_args(union)[0])
    return tuple(
        kind
        for member in members
        for kind in get_args(member.model_fields["kind"].annotation)
    )


def assert_game_primitives_transport_kind_coverage(
    definition_snapshot: object,
) -> None:
    """Verify transport unions exactly cover canonical primitive kind registries.

    Args:
        definition_snapshot: Discriminated definition-snapshot union to inspect.

    Returns:
        None.

    Raises:
        RuntimeError: A union contains duplicates, omissions, or unknown kinds.

    """
    from talemate.game.primitives.definitions import DEFINITION_KINDS

    checks = (
        ("definition change", DefinitionChange, EDITABLE_DEFINITION_KINDS),
        ("primitive change", PrimitiveChange, EDITABLE_PRIMITIVE_KINDS),
        ("definition snapshot", definition_snapshot, DEFINITION_KINDS),
    )
    for label, union, expected in checks:
        actual = _kind_values(union)
        if len(actual) != len(set(actual)) or set(actual) != set(expected):
            raise RuntimeError(
                f"Game Primitives {label} kind coverage mismatch: "
                f"expected {sorted(expected)}, got {sorted(actual)}"
            )
