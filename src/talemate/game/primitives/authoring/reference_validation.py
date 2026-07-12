"""Cross-reference and destination validation for primitive candidates."""

import pydantic

from talemate.game.primitives.adventure import AdventureDefinition
from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.attribute_sources import (
    DeckAttributeOptions,
    RollTableAttributeOptions,
)
from talemate.game.primitives.attributes import AttributeSource
from talemate.game.primitives.conditions import (
    PrimitiveCondition,
    PrimitiveConditionGroup,
)
from talemate.game.primitives.deck_schema import DeckDefinition
from talemate.game.primitives.modifiers import RollModifier
from talemate.game.primitives.primitive_payloads import RollTableInstancePayload
from talemate.game.primitives.roll_tables import RollTableDefinition
from talemate.game.primitives.schema import PrimitiveRootPayload


class PrimitiveReferenceValidator:
    """Validate all candidate references, warnings, and forbidden destinations."""

    def validate(
        self, root: PrimitiveRootPayload, errors: list[str], warnings: list[str]
    ) -> None:
        """Append complete cross-reference findings for a candidate root."""
        self._validate_attribute_refs(root, errors, warnings)
        self._validate_instance_definition_refs(root, errors)
        self._validate_modifier_targets(root, errors)
        self._validate_condition_refs(root, errors)
        self._validate_forbidden_destinations(root, errors)

    def _validate_attribute_refs(
        self, root: PrimitiveRootPayload, errors: list[str], warnings: list[str]
    ) -> None:
        definitions = root.definitions
        handlers = {
            "deck": lambda ref: self._validate_definition_ref(
                definitions["decks"], ref, "deck", errors
            ),
            "roll_table": lambda ref: self._validate_definition_ref(
                definitions["roll_tables"], ref, "roll table", errors
            ),
            "meter": lambda ref: self._validate_primitive_ref(
                root, ref, "meters", errors
            ),
            "clock": lambda ref: self._validate_primitive_ref(
                root, ref, "clocks", errors
            ),
            "modifier": lambda ref: self._validate_modifier_ref(root, ref, errors),
            "relationship": lambda ref: self._validate_relationship_ref(
                root, ref, errors
            ),
        }
        for anchor_key, anchor in root.anchors.items():
            for attribute_id, payload in anchor.primitives.get(
                "attributes", {}
            ).items():
                source = AttributeSource.model_validate(payload)
                if source.render_policy == "prompt" and source.source in {
                    "deck",
                    "roll_table",
                }:
                    warnings.append(
                        f"{anchor_key}/attributes/{attribute_id} uses a mutating prompt source"
                    )
                self._validate_source_warnings(
                    root, anchor_key, attribute_id, source, warnings
                )
                handler = handlers.get(source.source)
                if handler is not None:
                    handler(source.ref)

    @staticmethod
    def _validate_instance_definition_refs(
        root: PrimitiveRootPayload, errors: list[str]
    ) -> None:
        definitions = root.definitions["roll_tables"]
        for anchor_key, anchor in root.anchors.items():
            for instance_id, payload in anchor.primitives.get(
                "roll_tables", {}
            ).items():
                instance = RollTableInstancePayload.model_validate(payload)
                if instance.definition not in definitions:
                    errors.append(
                        "Missing roll table definition for "
                        f"{anchor_key}/roll_tables/{instance_id}: "
                        f"{instance.definition}"
                    )

    def _validate_modifier_targets(
        self, root: PrimitiveRootPayload, errors: list[str]
    ) -> None:
        for payload in root.definitions["modifiers"].values():
            modifier = RollModifier.model_validate(payload)
            if "/" in modifier.applies_to:
                self._validate_primitive_ref(
                    root, modifier.applies_to, "roll_tables", errors
                )
            elif modifier.applies_to not in root.definitions["roll_tables"]:
                errors.append(f"Missing modifier target: {modifier.applies_to}")
        for payload in root.definitions["roll_tables"].values():
            table = RollTableDefinition.model_validate(payload)
            for modifier_ref in table.modifiers:
                self._validate_modifier_ref(root, modifier_ref, errors)

    def _validate_condition_refs(
        self, root: PrimitiveRootPayload, errors: list[str]
    ) -> None:
        groups: list[PrimitiveConditionGroup] = []
        for anchor in root.anchors.values():
            for payload in anchor.primitives.get("attributes", {}).values():
                groups.extend(AttributeSource.model_validate(payload).conditions)
        for payload in root.definitions["modifiers"].values():
            groups.extend(RollModifier.model_validate(payload).when)
        for payload in root.definitions["decks"].values():
            for card in DeckDefinition.model_validate(payload).cards:
                groups.extend(card.conditions)
        for payload in root.definitions["roll_tables"].values():
            for row in RollTableDefinition.model_validate(payload).rows:
                groups.extend(row.conditions)
        for payload in root.definitions["adventures"].values():
            for transition in AdventureDefinition.model_validate(
                payload
            ).transitions.values():
                groups.extend(transition.conditions)
        handlers = {
            "primitive": lambda condition: self._validate_primitive_condition(
                root, condition, errors
            ),
            "meter": lambda condition: self._validate_anchored_condition(
                root, condition, "meters", errors
            ),
            "clock_complete": lambda condition: self._validate_anchored_condition(
                root, condition, "clocks", errors
            ),
            "relationship": lambda condition: self._validate_anchored_condition(
                root, condition, "meters", errors, relationship=True
            ),
            "anchor_has_tag": lambda condition: self._validate_tag_condition(
                root, condition, errors
            ),
            "anchor_missing_tag": lambda condition: self._validate_tag_condition(
                root, condition, errors
            ),
        }
        for group in groups:
            for condition in group.conditions:
                handler = handlers.get(condition.kind)
                if handler is not None:
                    handler(condition)

    def _validate_primitive_condition(
        self,
        root: PrimitiveRootPayload,
        condition: PrimitiveCondition,
        errors: list[str],
    ) -> None:
        ref = PrimitiveRef.parse(condition.path)
        self._validate_primitive_ref(root, ref.key(), ref.kind, errors)

    def _validate_anchored_condition(
        self,
        root: PrimitiveRootPayload,
        condition: PrimitiveCondition,
        kind: str,
        errors: list[str],
        *,
        relationship: bool = False,
    ) -> None:
        ref = self._condition_ref(condition, kind)
        self._validate_primitive_ref(root, ref, kind, errors, relationship=relationship)

    @staticmethod
    def _validate_tag_condition(
        root: PrimitiveRootPayload,
        condition: PrimitiveCondition,
        errors: list[str],
    ) -> None:
        anchor = AnchorRef.parse(condition.anchor)
        if anchor.key() not in root.anchors:
            errors.append(f"Missing anchor for tag condition: {anchor.key()}")

    @staticmethod
    def _condition_ref(condition: PrimitiveCondition, kind: str) -> str:
        if condition.path:
            return PrimitiveRef.parse(condition.path).key()
        return PrimitiveRef(
            anchor=AnchorRef.parse(condition.anchor),
            kind=kind,
            id=condition.dimension,
        ).key()

    def _validate_source_warnings(
        self,
        root: PrimitiveRootPayload,
        anchor_key: str,
        attribute_id: str,
        source: AttributeSource,
        warnings: list[str],
    ) -> None:
        source_path = f"{anchor_key}/attributes/{attribute_id}"
        if (
            source.render_policy in {"prompt", "summary"}
            and source.source == "literal"
            and source.value is None
        ):
            warnings.append(f"{source_path} lacks guaranteed renderable text")
        if source.source == "deck" and source.ref in root.definitions["decks"]:
            deck = DeckDefinition.model_validate(root.definitions["decks"][source.ref])
            options = DeckAttributeOptions.model_validate(source.options)
            if options.avoid_recent is not None and options.avoid_recent >= len(
                deck.cards
            ):
                warnings.append(
                    f"{source_path} avoid_recent is greater than or equal to card count"
                )
            if source.render_policy in {"prompt", "summary"} and (
                options.result_field not in {"text", "label"}
                or (
                    options.result_field == "text"
                    and any(not card.text for card in deck.cards)
                )
            ):
                warnings.append(f"{source_path} lacks guaranteed renderable text")
        elif (
            source.source == "roll_table"
            and source.ref in root.definitions["roll_tables"]
        ):
            table = RollTableDefinition.model_validate(
                root.definitions["roll_tables"][source.ref]
            )
            options = RollTableAttributeOptions.model_validate(source.options)
            if source.render_policy in {"prompt", "summary"} and (
                options.result_field not in {"text", "label"}
                or (
                    options.result_field == "text"
                    and any(not row.text for row in table.rows)
                )
            ):
                warnings.append(f"{source_path} lacks guaranteed renderable text")

    @staticmethod
    def _validate_forbidden_destinations(
        root: PrimitiveRootPayload, errors: list[str]
    ) -> None:
        def visit(value, field: str | None = None) -> None:
            if (
                field in {"destination", "target", "ref", "path", "applies_to"}
                and isinstance(value, str)
                and "base_attributes" in value
            ):
                errors.append(
                    "Primitive destination/ref cannot target Character.base_attributes: "
                    + value
                )
            elif isinstance(value, dict):
                for key, nested in value.items():
                    visit(nested, key)
            elif isinstance(value, list):
                for nested in value:
                    visit(nested, field)
            elif isinstance(value, pydantic.BaseModel):
                visit(value.model_dump(mode="python"), field)

        visit(root.definitions)
        visit(root.anchors)

    def _validate_modifier_ref(
        self, root: PrimitiveRootPayload, ref_text: str | None, errors: list[str]
    ) -> None:
        if ref_text is None:
            return
        if "/" in ref_text:
            self._validate_primitive_ref(root, ref_text, "modifiers", errors)
        elif ref_text not in root.definitions["modifiers"]:
            errors.append(f"Missing modifier: {ref_text}")

    @staticmethod
    def _validate_definition_ref(
        definitions: dict,
        ref_text: str | None,
        category: str,
        errors: list[str],
    ) -> None:
        if ref_text not in definitions:
            errors.append(f"Missing {category} definition: {ref_text}")

    def _validate_relationship_ref(
        self, root: PrimitiveRootPayload, ref_text: str | None, errors: list[str]
    ) -> None:
        if ref_text is None:
            return
        if "/" in ref_text:
            self._validate_primitive_ref(
                root, ref_text, "meters", errors, relationship=True
            )
            return
        anchor = AnchorRef.parse(ref_text)
        if anchor.kind != "relationship" or anchor.key() not in root.anchors:
            errors.append(f"Missing relationship: {ref_text}")

    @staticmethod
    def _validate_primitive_ref(
        root: PrimitiveRootPayload,
        ref_text: str | None,
        expected_kind: str,
        errors: list[str],
        *,
        relationship: bool = False,
    ) -> None:
        if ref_text is None:
            return
        ref = PrimitiveRef.parse(ref_text)
        anchor = root.anchors.get(ref.anchor.key())
        if (
            ref.kind != expected_kind
            or (relationship and ref.anchor.kind != "relationship")
            or anchor is None
            or ref.id not in anchor.primitives.get(expected_kind, {})
        ):
            errors.append(f"Missing {expected_kind[:-1]} primitive: {ref_text}")
