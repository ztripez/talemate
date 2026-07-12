"""Anchor and primitive reference models for Game Primitives."""

from __future__ import annotations

from typing import Literal

import pydantic

from talemate.game.primitives.constants import ANCHOR_KINDS
from talemate.game.primitives.exceptions import InvalidAnchorRef, InvalidPrimitiveRef

#: Supported owner categories for an ``AnchorRef``.
AnchorKind = Literal[*ANCHOR_KINDS]


class AnchorRef(pydantic.BaseModel):
    """Stable address for a context that owns primitive instances.

    An anchor identifies the owner of runtime primitive data, such as the main
    scene, a character, an object, or a directional relationship between two
    participants. The canonical string form is ``<kind>:<id>``. Relationship
    anchors use ``<source>-><target>`` as the identifier segment.

    Attributes:
        kind: Anchor owner category, limited to the values in ``AnchorKind``.
        id: Non-empty owner identifier. The identifier is stripped of
            surrounding whitespace and must not contain ``/``.
    """

    model_config = pydantic.ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: AnchorKind
    id: str = pydantic.Field(min_length=1)

    @pydantic.model_validator(mode="before")
    @classmethod
    def parse_string_value(cls, value: object) -> object:
        """Convert ``<kind>:<id>`` text into model input data.

        Args:
            value: Raw model input, either a mapping or an anchor reference
                string.

        Returns:
            Mapping data consumed by Pydantic field validation.

        Raises:
            ValueError: If a string input is empty or has invalid separator
                syntax.
        """
        if not isinstance(value, str):
            return value

        value = value.strip()
        if not value:
            raise ValueError("Anchor reference cannot be empty")
        if value.count(":") != 1:
            raise ValueError("Anchor reference must contain exactly one ':' separator")

        kind, anchor_id = value.split(":", 1)
        return {"kind": kind.strip(), "id": anchor_id}

    @pydantic.field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Validate an anchor id after whitespace normalization.

        Args:
            value: Anchor id segment from ``<kind>:<id>``.

        Returns:
            The stripped anchor id.

        Raises:
            ValueError: If the id is empty after trimming or contains ``/``.
        """
        value = value.strip()
        if not value:
            raise ValueError("Anchor id cannot be empty")
        if "/" in value or ":" in value:
            raise ValueError("Anchor id cannot contain '/' or ':'")
        return value

    @pydantic.model_validator(mode="after")
    def validate_relationship_id(self) -> "AnchorRef":
        """Validate relationship anchor participant syntax.

        Returns:
            The validated anchor reference.

        Raises:
            ValueError: If a relationship id does not use exactly one non-empty
                ``source->target`` pair.
        """
        if self.kind != "relationship":
            return self

        participants = self.id.split("->")
        if len(participants) != 2:
            raise ValueError(
                "Relationship anchor id must use '<source>-><target>' syntax"
            )

        source, target = (part.strip() for part in participants)
        if not source or not target:
            raise ValueError("Relationship anchor participants cannot be empty")
        self.id = f"{source}->{target}"
        return self

    @classmethod
    def parse(cls, value: str) -> "AnchorRef":
        """Parse an anchor reference from ``<kind>:<id>`` text.

        Args:
            value: Anchor reference string to parse.

        Returns:
            Parsed and validated anchor reference.

        Raises:
            InvalidAnchorRef: If the value is not a valid anchor reference.
        """
        try:
            return cls.model_validate(value)
        except (pydantic.ValidationError, ValueError) as exc:
            raise InvalidAnchorRef(str(exc)) from exc

    def key(self) -> str:
        """Return the stable storage key for this anchor reference.

        Returns:
            Canonical ``<kind>:<id>`` anchor string.
        """
        return f"{self.kind}:{self.id}"

    def __str__(self) -> str:
        """Return the stable string form of this anchor reference.

        Returns:
            Canonical ``<kind>:<id>`` anchor string.
        """
        return self.key()


class PrimitiveRef(pydantic.BaseModel):
    """Stable address for one primitive payload attached to an anchor.

    A primitive reference identifies a JSON-compatible runtime payload under the
    canonical ``<anchor>/<kind>/<id>`` path, such as
    ``character:Alice/meters/confidence``.

    Attributes:
        anchor: Anchor reference that owns the primitive instance.
        kind: Non-empty primitive collection name, such as ``meters`` or
            ``clocks``. The kind is stripped of surrounding whitespace and must
            not contain ``/``.
        id: Non-empty primitive identifier within the primitive collection. The
            identifier is stripped of surrounding whitespace and must not
            contain ``/``.
    """

    model_config = pydantic.ConfigDict(extra="forbid", str_strip_whitespace=True)

    anchor: AnchorRef
    kind: str = pydantic.Field(min_length=1)
    id: str = pydantic.Field(min_length=1)

    @pydantic.model_validator(mode="before")
    @classmethod
    def parse_string_value(cls, value: object) -> object:
        """Convert ``<anchor>/<kind>/<id>`` text into model input data.

        Args:
            value: Raw model input, either a mapping or a primitive reference
                string.

        Returns:
            Mapping data consumed by Pydantic field validation.

        Raises:
            ValueError: If a string input does not have exactly three path
                segments.
        """
        if not isinstance(value, str):
            return value

        value = value.strip()
        parts = value.split("/")
        if len(parts) != 3:
            raise ValueError(
                "Primitive reference must have '<anchor>/<kind>/<id>' syntax"
            )

        anchor_text, primitive_kind, primitive_id = parts
        return {"anchor": anchor_text, "kind": primitive_kind, "id": primitive_id}

    @pydantic.field_validator("kind", "id")
    @classmethod
    def validate_path_segment(cls, value: str) -> str:
        """Validate a primitive path segment.

        Args:
            value: Primitive kind or primitive id segment.

        Returns:
            The stripped path segment.

        Raises:
            ValueError: If the segment is empty after trimming or contains
                ``/``.
        """
        value = value.strip()
        if not value:
            raise ValueError("Primitive path segment cannot be empty")
        if "/" in value:
            raise ValueError("Primitive path segment cannot contain '/'")
        return value

    @classmethod
    def parse(cls, value: str) -> "PrimitiveRef":
        """Parse a primitive reference from ``<anchor>/<kind>/<id>`` text.

        Args:
            value: Primitive reference string to parse.

        Returns:
            Parsed and validated primitive reference.

        Raises:
            InvalidPrimitiveRef: If the value is not a valid primitive reference.
        """
        try:
            return cls.model_validate(value)
        except (pydantic.ValidationError, ValueError) as exc:
            raise InvalidPrimitiveRef(str(exc)) from exc

    def key(self) -> str:
        """Return the stable storage key for this primitive reference.

        Returns:
            Canonical ``<anchor>/<kind>/<id>`` primitive string.
        """
        return f"{self.anchor.key()}/{self.kind}/{self.id}"

    def __str__(self) -> str:
        """Return the stable string form of this primitive reference.

        Returns:
            Canonical ``<anchor>/<kind>/<id>`` primitive string.
        """
        return self.key()


def scene_anchor() -> AnchorRef:
    """Return the canonical main scene anchor.

    Returns:
        Anchor reference for ``scene:main``.
    """
    return AnchorRef(kind="scene", id="main")


def character_anchor(name: str) -> AnchorRef:
    """Return a character anchor for the provided character name.

    Args:
        name: Character identifier. The value must be non-empty after trimming
            whitespace and must not contain ``/``.

    Returns:
        Anchor reference with kind ``character`` and the normalized character
        identifier.

    Raises:
        pydantic.ValidationError: If ``name`` violates anchor validation rules.
    """
    return AnchorRef(kind="character", id=name)


def object_anchor(identifier: str) -> AnchorRef:
    """Return an object anchor for the provided object identifier.

    Args:
        identifier: Object identifier. The value must be non-empty after
            trimming whitespace and must not contain ``/``.

    Returns:
        Anchor reference with kind ``object`` and the normalized object
        identifier.

    Raises:
        pydantic.ValidationError: If ``identifier`` violates anchor validation
            rules.
    """
    return AnchorRef(kind="object", id=identifier)


def relationship_anchor(source: str, target: str) -> AnchorRef:
    """Return a directional relationship anchor from source to target.

    Args:
        source: Source participant identifier.
        target: Target participant identifier.

    Returns:
        Directional relationship anchor reference from ``source`` to ``target``.

    Raises:
        pydantic.ValidationError: If either participant is empty or the combined
            relationship id violates anchor validation rules.
    """
    return AnchorRef(kind="relationship", id=f"{source}->{target}")


def relationship_participants(anchor: AnchorRef | str) -> tuple[str, str]:
    """Return source and target participant ids from a relationship anchor.

    Args:
        anchor: Relationship anchor model or canonical relationship anchor string.

    Returns:
        Tuple containing the source participant id and target participant id.

    Raises:
        InvalidAnchorRef: If ``anchor`` is a string that cannot be parsed.
        ValueError: If ``anchor`` is not a relationship anchor.
    """
    anchor_ref = AnchorRef.parse(anchor) if isinstance(anchor, str) else anchor
    if anchor_ref.kind != "relationship":
        raise ValueError("relationship_participants requires relationship anchor")
    return tuple(anchor_ref.id.split("->", 1))
