"""Runtime-state compatibility validation for primitive draft candidates."""

from talemate.game.primitives.adventure import (
    AdventureDefinition,
    AdventureState,
    validate_adventure_runtime_compatibility,
)
from talemate.game.primitives.deck_schema import (
    DeckDefinition,
    validate_deck_runtime_compatibility,
)
from talemate.game.primitives.deck_state import DeckInstancePayload
from talemate.game.primitives.schema import PrimitiveRootPayload


class PrimitiveRuntimeValidator:
    """Check persisted runtime state against candidate definitions."""

    def validate(self, root: PrimitiveRootPayload, errors: list[str]) -> None:
        """Append all deck and adventure runtime incompatibilities."""
        self._validate_deck_instances(root, errors)
        self._validate_adventures(root, errors)

    @staticmethod
    def _validate_deck_instances(root: PrimitiveRootPayload, errors: list[str]) -> None:
        definitions = root.definitions["decks"]
        for anchor_key, anchor in root.anchors.items():
            for instance_id, payload in anchor.primitives.get("decks", {}).items():
                ref = f"{anchor_key}/decks/{instance_id}"
                instance = DeckInstancePayload.model_validate(payload)
                definition_payload = definitions.get(instance.definition)
                if definition_payload is None:
                    errors.append(
                        f"Missing deck definition for {ref}: {instance.definition}"
                    )
                    continue
                errors.extend(
                    validate_deck_runtime_compatibility(
                        ref,
                        instance.runtime,
                        DeckDefinition.model_validate(definition_payload),
                    )
                )

    @staticmethod
    def _validate_adventures(root: PrimitiveRootPayload, errors: list[str]) -> None:
        definitions = {
            definition_id: AdventureDefinition.model_validate(payload)
            for definition_id, payload in root.definitions["adventures"].items()
        }
        for definition in definitions.values():
            for story_scene in definition.scenes.values():
                for anchor_key in story_scene.local_anchors:
                    if anchor_key not in root.anchors:
                        errors.append(f"Missing adventure local anchor: {anchor_key}")
            for transition in definition.transitions.values():
                for anchor_key in transition.carry_anchors:
                    if anchor_key not in root.anchors:
                        errors.append(f"Missing adventure carried anchor: {anchor_key}")
        runtime_payload = root.runtime.get("adventure")
        if runtime_payload is None:
            return
        state = AdventureState.model_validate(runtime_payload)
        definition = definitions.get(state.adventure_id)
        if definition is None:
            errors.append(
                f"Active adventure definition not found: {state.adventure_id}"
            )
            return
        errors.extend(validate_adventure_runtime_compatibility(state, definition))
