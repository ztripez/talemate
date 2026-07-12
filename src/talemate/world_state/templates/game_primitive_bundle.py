"""Reusable authored Game Primitive bundle templates."""

from typing import Literal

import pydantic

from talemate.game.primitives.containers import (
    AnchorPayload,
    PrimitiveDefinitions,
)

from .base import Template, register


@register("game_primitive_bundle")
class GamePrimitiveBundle(Template):
    """Strictly persist authored definitions and exact canonical anchors only.

    Attributes:
        template_type: Template registry discriminator, always
            ``game_primitive_bundle``.
        bundle_schema_version: Persisted bundle contract version, currently ``1``.
        definitions: Canonically typed authored definition collections.
        anchors: Canonical exact-anchor keys mapped to authored anchor payloads.

    Invariants:
        Unknown fields, coercion, non-finite numbers, undeclared definition or
        primitive groups, and non-canonical anchor keys are rejected. Runtime,
        ledger, draft, and active-adventure state cannot be represented.
    """

    model_config = pydantic.ConfigDict(
        extra="forbid", strict=True, allow_inf_nan=False, revalidate_instances="always"
    )
    template_type: Literal["game_primitive_bundle"] = "game_primitive_bundle"
    bundle_schema_version: Literal[1] = 1
    definitions: PrimitiveDefinitions = pydantic.Field(
        default_factory=PrimitiveDefinitions
    )
    anchors: dict[str, AnchorPayload] = pydantic.Field(default_factory=dict)

    @pydantic.model_validator(mode="after")
    def reject_extension_groups(self) -> "GamePrimitiveBundle":
        """Reject undeclared definition and anchor primitive groups.

        Args:
            self: Fully field-validated bundle to inspect.

        Returns:
            This bundle unchanged when definitions and every anchor payload contain
            only schema-declared groups.

        Raises:
            ValueError: The definitions contain an extension group, or an anchor's
                primitive payload contains an extension group. This keeps runtime
                registry extensions out of the persisted canonical bundle schema.

        """
        if self.definitions.__pydantic_extra__:
            groups = ", ".join(sorted(self.definitions.__pydantic_extra__))
            raise ValueError(f"Bundle contains undeclared definition groups: {groups}")
        for ref, anchor in self.anchors.items():
            if anchor.primitives.__pydantic_extra__:
                groups = ", ".join(sorted(anchor.primitives.__pydantic_extra__))
                raise ValueError(
                    f"Bundle anchor {ref!r} contains undeclared primitive groups: {groups}"
                )
        return self

    @pydantic.field_validator("anchors")
    @classmethod
    def validate_anchors(
        cls, value: dict[str, AnchorPayload]
    ) -> dict[str, AnchorPayload]:
        """Validate exact anchor references and canonical payloads.

        Each key must parse as an exact :class:`AnchorRef` and already equal that
        reference's canonical key. Payloads are validated as ``AnchorPayload``
        instances, and the returned mapping retains only canonical, unique keys.

        Args:
            value: Anchor-reference keys mapped to authored primitive payloads.

        Returns:
            A newly validated mapping of canonical exact-anchor keys to canonical
            anchor payloads.

        Raises:
            ValueError: An anchor reference is invalid or non-canonical, or two
                inputs resolve to the same canonical key.
            pydantic.ValidationError: An anchor reference or payload violates its
                strict model contract.

        """
        from talemate.game.primitives.anchors import AnchorRef

        normalized = {}
        for key, payload in value.items():
            canonical_key = AnchorRef.model_validate(key).key()
            if canonical_key != key:
                raise ValueError(
                    f"Bundle anchor key must be canonical: {key!r} != {canonical_key!r}"
                )
            if canonical_key in normalized:
                raise ValueError(f"Duplicate anchor key: {canonical_key}")
            normalized[canonical_key] = AnchorPayload.model_validate(payload)
        return normalized


__all__ = [
    "GamePrimitiveBundle",
]
