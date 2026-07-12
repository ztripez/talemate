"""Directional relationship authoring request contracts."""

from typing import Annotated, Literal

import pydantic

from talemate.game.primitives.definitions import MeterPayload

from .game_primitives_transport import (
    GamePrimitivesRequestModel,
    GamePrimitivesTransportModel,
)


class UpsertRelationshipDimensionChange(GamePrimitivesTransportModel):
    """Describe creation or replacement of one relationship meter dimension."""

    operation: Literal["upsert_dimension"]
    dimension: MeterPayload


class DeleteRelationshipDimensionChange(GamePrimitivesTransportModel):
    """Describe deletion of one non-empty relationship dimension identifier."""

    operation: Literal["delete_dimension"]
    dimension_id: str = pydantic.Field(min_length=1)


class DeleteRelationshipEdgeChange(GamePrimitivesTransportModel):
    """Describe deletion of an entire directional relationship edge."""

    operation: Literal["delete_edge"]


RelationshipAuthoringChange = Annotated[
    UpsertRelationshipDimensionChange
    | DeleteRelationshipDimensionChange
    | DeleteRelationshipEdgeChange,
    pydantic.Field(discriminator="operation"),
]


class AuthorGamePrimitiveRelationshipPayload(GamePrimitivesRequestModel):
    """Request a revision-guarded change to a directional relationship."""

    action: Literal["author_game_primitive_relationship"]
    expected_revision: str = pydantic.Field(min_length=1)
    source: str = pydantic.Field(min_length=1)
    target: str = pydantic.Field(min_length=1)
    change: RelationshipAuthoringChange

    @pydantic.model_validator(mode="after")
    def validate_relationship(self) -> "AuthorGamePrimitiveRelationshipPayload":
        """Validate relationship participants and dimension identity.

        Returns:
            The validated relationship request.

        Raises:
            ValueError: Participants cannot form an anchor or a dimension ID is empty.

        """
        from talemate.game.primitives.anchors import relationship_anchor

        relationship_anchor(self.source, self.target)
        if (
            isinstance(self.change, UpsertRelationshipDimensionChange)
            and not self.change.dimension.id
        ):
            raise ValueError("Relationship dimension id cannot be empty")
        return self
