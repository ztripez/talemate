"""FOCAL callbacks for schema-validated primitive draft authoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

import talemate.game.focal as focal
from talemate.game.primitives.authoring.schema import (
    CreateAnchorRequest,
    CreateAttributeSourceRequest,
    CreateClockRequest,
    CreateDeckRequest,
    CreateMeterRequest,
    CreateModifierRequest,
    CreateRelationshipRequest,
    CreateRollTableRequest,
    DraftRequest,
)
from talemate.game.primitives.authoring.tools import PrimitiveAuthoringService
from talemate.game.primitives.store import PrimitiveStore

if TYPE_CHECKING:
    from talemate.tale_mate import Scene


@dataclass(frozen=True, slots=True)
class _Operation:
    name: str
    request_model: type[BaseModel]
    service_method: str
    arguments: tuple[tuple[str, str], ...]
    multiple: bool = True
    pass_draft_id: bool = False


_OPERATIONS = (
    _Operation(
        "create_anchor",
        CreateAnchorRequest,
        "create_anchor",
        (("kind", "str"), ("id", "str"), ("tags", "list"), ("meta", "dict")),
    ),
    _Operation(
        "create_meter",
        CreateMeterRequest,
        "create_meter",
        (
            ("anchor", "str"),
            ("id", "str"),
            ("label", "str"),
            ("min", "float"),
            ("max", "float"),
            ("value", "float"),
            ("render_policy", "str"),
        ),
    ),
    _Operation(
        "create_clock",
        CreateClockRequest,
        "create_clock",
        (
            ("anchor", "str"),
            ("id", "str"),
            ("label", "str"),
            ("max", "int"),
            ("value", "int"),
            ("render_policy", "str"),
        ),
    ),
    _Operation(
        "create_deck",
        CreateDeckRequest,
        "create_deck",
        (
            ("id", "str"),
            ("name", "str"),
            ("mode", "str"),
            ("cards", "list"),
            ("anchor", "str"),
            ("instance_id", "str"),
        ),
    ),
    _Operation(
        "create_roll_table",
        CreateRollTableRequest,
        "create_roll_table",
        (
            ("id", "str"),
            ("name", "str"),
            ("mode", "str"),
            ("rows", "list"),
            ("dice", "str"),
            ("anchor", "str"),
            ("instance_id", "str"),
        ),
    ),
    _Operation(
        "create_relationship_model",
        CreateRelationshipRequest,
        "create_relationship",
        (
            ("source", "str"),
            ("target", "str"),
            ("dimensions", "list"),
            ("tags", "list"),
        ),
    ),
    _Operation(
        "create_modifier",
        CreateModifierRequest,
        "create_modifier",
        (
            ("id", "str"),
            ("label", "str"),
            ("applies_to", "str"),
            ("when", "list"),
            ("operation", "dict"),
            ("explanation", "str"),
        ),
    ),
    _Operation(
        "create_attribute_source",
        CreateAttributeSourceRequest,
        "create_attribute_source",
        (
            ("anchor", "str"),
            ("id", "str"),
            ("source", "str"),
            ("render_policy", "str"),
            ("ref", "str"),
            ("value", "any"),
            ("options", "dict"),
        ),
    ),
    _Operation(
        "validate_draft",
        DraftRequest,
        "validate_draft",
        (),
        multiple=False,
        pass_draft_id=True,
    ),
    _Operation(
        "commit_draft",
        DraftRequest,
        "commit_draft",
        (),
        multiple=False,
        pass_draft_id=True,
    ),
)


class PrimitiveAuthoringFocal:
    """Build FOCAL function callbacks backed by primitive draft authoring.

    Attributes:
        service: Authoring service invoked by every generated callback.

    """

    def __init__(self, service: PrimitiveAuthoringService | None = None):
        """Initialize a FOCAL callback factory.

        Args:
            service: Authoring service to invoke, or ``None`` to create an
                independent service instance.

        """
        self.service = service or PrimitiveAuthoringService()

    def callbacks(self, scene: "Scene", draft_id: str) -> list[focal.Callback]:
        """Build primitive authoring callbacks bound to one scene draft.

        Args:
            scene: Scene read and mutated by callback operations.
            draft_id: Identifier injected into every callback request.

        Returns:
            FOCAL callback descriptors for staging anchors, primitives, and
            definitions and for validating or committing the bound draft.

        Side Effects:
            Invoking a returned callback validates its arguments and may mutate
            the bound scene's persisted primitive draft or committed primitive
            root. Constructing the callback list does not mutate scene state.

        """
        return [self._callback(operation, scene, draft_id) for operation in _OPERATIONS]

    def _callback(
        self, operation: _Operation, scene: "Scene", draft_id: str
    ) -> focal.Callback:
        """Bind one declared authoring operation to a scene draft.

        The returned dispatcher validates FOCAL arguments with the operation's
        request model, invokes its service method, and serializes the result for
        JSON transport. Lifecycle operations pass only the validated draft ID;
        mutation operations pass the complete validated request.

        Args:
            operation: Callback contract defining the exposed name, validation,
                service dispatch, argument metadata, and repetition policy.
            scene: Scene read and mutated by the authoring service.
            draft_id: Draft identifier injected before request validation.

        Returns:
            A callback descriptor bound to the supplied scene and draft.

        Raises:
            AttributeError: If the declared service method does not exist.

        Side Effects:
            Invoking the callback may mutate the bound scene's draft or committed
            primitive state. Building the descriptor does not mutate scene state.

        """

        async def dispatch(**arguments: Any) -> dict[str, Any]:
            expected_revision = PrimitiveStore.read_snapshot_for_scene(
                scene
            ).revision_token()
            request = operation.request_model.model_validate(
                {
                    "draft_id": draft_id,
                    "expected_revision": expected_revision,
                    **arguments,
                }
            )
            service_argument = request.draft_id if operation.pass_draft_id else request
            method = getattr(self.service, operation.service_method)
            result = (
                method(
                    scene,
                    service_argument,
                    expected_revision=request.expected_revision,
                )
                if operation.pass_draft_id
                else method(scene, service_argument)
            )
            return result.model_dump(mode="json")

        dispatch.__name__ = operation.name
        return focal.Callback(
            name=operation.name,
            arguments=[
                focal.Argument(name=name, type=argument_type)
                for name, argument_type in operation.arguments
            ],
            fn=dispatch,
            multiple=operation.multiple,
        )


__all__ = ["PrimitiveAuthoringFocal"]
