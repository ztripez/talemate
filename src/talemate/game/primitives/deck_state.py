"""Canonical persisted instance model and state construction for decks."""

from __future__ import annotations

import random

import pydantic

from talemate.game.primitives.anchors import PrimitiveRef
from talemate.game.primitives.deck_schema import DeckDefinition, DeckRuntimeState


class DeckInstancePayload(pydantic.BaseModel):
    """Bind an anchored deck instance to its definition and mutable state.

    Attributes:
        definition: Non-empty identifier of the reusable deck definition.
        runtime: Persisted selection state owned by the anchored instance.

    Invariants:
        ``runtime.definition_id`` equals ``definition``. Unknown fields and
        non-finite numbers are rejected.

    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    definition: str = pydantic.Field(min_length=1)
    runtime: DeckRuntimeState

    @pydantic.model_validator(mode="after")
    def validate_definition_id(self) -> "DeckInstancePayload":
        """Require runtime state to belong to the referenced definition.

        Returns:
            The validated instance payload.

        Raises:
            ValueError: If the runtime definition identifier differs from the
                instance definition identifier.

        """
        if self.runtime.definition_id != self.definition:
            raise ValueError(
                "Deck runtime definition_id "
                f"'{self.runtime.definition_id}' must match definition "
                f"'{self.definition}'"
            )
        return self

    @classmethod
    def create(
        cls, definition: DeckDefinition, ref: PrimitiveRef | str
    ) -> "DeckInstancePayload":
        """Create canonical initial state for an anchored deck instance.

        Args:
            definition: Reusable deck definition bound to the new instance.
            ref: Canonical or parseable primitive reference used as shuffle seed.

        Returns:
            Validated instance payload with empty or initially shuffled state.

        Raises:
            pydantic.ValidationError: If ``ref`` is not a valid primitive
                reference or the resulting payload violates its schema.

        """
        instance_ref = PrimitiveRef.model_validate(ref)
        return cls(
            definition=definition.id,
            runtime=initial_deck_state(definition, instance_ref.key()),
        )


def initial_deck_state(definition: DeckDefinition, seed: str) -> DeckRuntimeState:
    """Build canonical initial runtime state for a deck definition.

    Args:
        definition: Definition whose mode and cards initialize the state.
        seed: Stable instance-specific input for seeded shuffle order.

    Returns:
        New runtime state; draw and physical modes include an initial draw pile.

    Side Effects:
        None; ``definition`` is not modified.

    """
    state = DeckRuntimeState(
        definition_id=definition.id,
        mode=definition.mode,
        seed=seed,
    )
    if definition.mode in {"draw", "physical"}:
        state.draw_pile = shuffled_deck_ids(definition, state)
    return state


def shuffled_deck_ids(
    definition: DeckDefinition,
    state: DeckRuntimeState,
    source: list[str] | None = None,
    *,
    preserve_physical_order: bool = True,
) -> list[str]:
    """Order card identifiers according to a deck's shuffle policy.

    Args:
        definition: Definition providing cards, mode, and shuffle policy.
        state: Runtime state providing the seed and draw count.
        source: Optional identifiers to order instead of all definition cards.
        preserve_physical_order: Keep initial physical decks in authored order.

    Returns:
        A new identifier list in authored, deterministic, or random order.

    Side Effects:
        None; input collections and models are not modified.

    """
    ids = list(source if source is not None else [card.id for card in definition.cards])
    if (
        preserve_physical_order
        and definition.mode == "physical"
        and state.draw_count == 0
    ):
        return ids
    rng = (
        random.Random(f"{state.seed}:{state.draw_count}")
        if definition.shuffle == "seeded"
        else random.Random()
    )
    rng.shuffle(ids)
    return ids
