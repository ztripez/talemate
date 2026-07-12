"""Anchor, primitive instance, deletion preview, and adjustment requests."""

from typing import Annotated, Literal

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.attributes import AttributeSource
from talemate.game.primitives.deck_state import DeckInstancePayload
from talemate.game.primitives.definitions import ClockPayload, MeterPayload
from talemate.game.primitives.modifiers import RollModifier
from talemate.game.primitives.primitive_payloads import RollTableInstancePayload

from .game_primitives_draft_definition_requests import DraftMutationPayload
from .game_primitives_transport import (
    GamePrimitivesRequestModel,
    GamePrimitivesTransportModel,
)


class AnchorMetadataChange(GamePrimitivesTransportModel):
    """Carry replacement metadata for an anchor.

    Attributes:
        tags: Complete tag list to store on the anchor.
        meta: JSON-compatible metadata map to store on the anchor.

    """

    tags: list[str] = pydantic.Field(default_factory=list)
    meta: dict[str, pydantic.JsonValue] = pydantic.Field(default_factory=dict)


class UpsertGamePrimitiveAnchorPayload(DraftMutationPayload):
    """Stage creation or replacement of an anchor in a draft.

    Attributes:
        action: Wire discriminator for anchor upserts.
        anchor: Canonical anchor reference identifying the draft entry.
        value: Replacement anchor metadata.

    """

    action: Literal["upsert_game_primitive_anchor"]
    anchor: AnchorRef
    value: AnchorMetadataChange


class DeleteGamePrimitiveAnchorPayload(DraftMutationPayload):
    """Stage deletion of an anchor from a draft.

    Attributes:
        action: Wire discriminator for anchor deletion.
        anchor: Canonical reference of the anchor to delete.

    """

    action: Literal["delete_game_primitive_anchor"]
    anchor: AnchorRef


class PreviewDeleteGamePrimitiveAnchorPayload(GamePrimitivesRequestModel):
    """Preview the cascading result of deleting an anchor.

    Attributes:
        action: Wire discriminator for anchor-deletion previews.
        expected_revision: Non-empty root revision required by the preview.
        anchor: Canonical reference of the candidate anchor.

    """

    action: Literal["preview_delete_game_primitive_anchor"]
    expected_revision: str = pydantic.Field(min_length=1)
    anchor: AnchorRef


class MeterPrimitiveChange(GamePrimitivesTransportModel):
    """Carry a meter instance replacement keyed by the ``meters`` kind."""

    kind: Literal["meters"]
    value: MeterPayload


class ClockPrimitiveChange(GamePrimitivesTransportModel):
    """Carry a clock instance replacement keyed by the ``clocks`` kind."""

    kind: Literal["clocks"]
    value: ClockPayload


class DeckPrimitiveChange(GamePrimitivesTransportModel):
    """Carry a deck instance replacement keyed by the ``decks`` kind."""

    kind: Literal["decks"]
    value: DeckInstancePayload


class RollTablePrimitiveChange(GamePrimitivesTransportModel):
    """Carry a roll-table instance replacement keyed by its transport kind."""

    kind: Literal["roll_tables"]
    value: RollTableInstancePayload


class AttributePrimitiveChange(GamePrimitivesTransportModel):
    """Carry an attribute instance replacement keyed by its transport kind."""

    kind: Literal["attributes"]
    value: AttributeSource


class ModifierPrimitiveChange(GamePrimitivesTransportModel):
    """Carry a modifier instance replacement keyed by its transport kind."""

    kind: Literal["modifiers"]
    value: RollModifier


PrimitiveChange = Annotated[
    MeterPrimitiveChange
    | ClockPrimitiveChange
    | DeckPrimitiveChange
    | RollTablePrimitiveChange
    | AttributePrimitiveChange
    | ModifierPrimitiveChange,
    pydantic.Field(discriminator="kind"),
]


class UpsertGamePrimitivePayload(DraftMutationPayload):
    """Stage a typed primitive instance create or replacement.

    The reference kind and identifier must match the typed primitive value.

    Attributes:
        action: Wire discriminator for primitive upserts.
        ref: Canonical reference identifying the primitive instance.
        primitive: Discriminated replacement value.

    """

    action: Literal["upsert_game_primitive"]
    ref: PrimitiveRef
    primitive: PrimitiveChange

    @pydantic.model_validator(mode="after")
    def validate_ref_identity(self) -> "UpsertGamePrimitivePayload":
        """Validate that the reference and replacement identify one primitive.

        Returns:
            The validated request payload.

        Raises:
            ValueError: The kind or value identifier differs from the reference.

        """
        if self.ref.kind != self.primitive.kind:
            raise ValueError(
                f"Primitive ref kind '{self.ref.kind}' does not match "
                f"'{self.primitive.kind}'"
            )
        value_id = getattr(self.primitive.value, "id", None)
        if value_id is not None and value_id != self.ref.id:
            raise ValueError(
                f"Primitive ref id '{self.ref.id}' does not match value id '{value_id}'"
            )
        return self


class DeleteGamePrimitivePayload(DraftMutationPayload):
    """Stage deletion of a primitive instance identified by ``ref``."""

    action: Literal["delete_game_primitive"]
    ref: PrimitiveRef


class PreviewDeleteGamePrimitivePayload(GamePrimitivesRequestModel):
    """Preview the cascading result of deleting a primitive instance."""

    action: Literal["preview_delete_game_primitive"]
    expected_revision: str = pydantic.Field(min_length=1)
    ref: PrimitiveRef


class AdjustGamePrimitivePayload(GamePrimitivesRequestModel):
    """Request a nonzero runtime adjustment to a meter or clock.

    Attributes:
        action: Wire discriminator for runtime adjustment.
        expected_revision: Non-empty revision required before mutation.
        ref: Canonical meter or clock reference.
        delta: Nonzero strict numeric adjustment.

    """

    action: Literal["adjust_game_primitive"]
    expected_revision: str = pydantic.Field(min_length=1)
    ref: PrimitiveRef
    delta: pydantic.StrictInt | pydantic.StrictFloat

    @pydantic.model_validator(mode="after")
    def validate_adjustment(self) -> "AdjustGamePrimitivePayload":
        """Validate the adjustable primitive kind and nonzero delta.

        Returns:
            The validated request payload.

        Raises:
            ValueError: The reference is not a meter or clock, or delta is zero.

        """
        if self.ref.kind not in {"meters", "clocks"}:
            raise ValueError("Runtime adjustment requires a meter or clock ref")
        if self.delta == 0:
            raise ValueError("Runtime adjustment delta cannot be zero")
        return self
