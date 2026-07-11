"""Adventure and story-scene graph runtime for Game Primitives."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Literal

import pydantic

from talemate.game.primitives.anchors import AnchorRef, PrimitiveRef
from talemate.game.primitives.conditions import (
    PrimitiveConditionGroup,
    conditions_match,
)
from talemate.game.primitives.effects import Effect, EffectResult, apply_effects
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.ledger import LedgerEntry
from talemate.game.primitives.schema import GAME_PRIMITIVES_KEY
from talemate.game.primitives.store import PrimitiveStore

if TYPE_CHECKING:
    from talemate.scene_message import SceneMessage
    from talemate.tale_mate import Scene


class StorySceneDefinition(pydantic.BaseModel):
    """Authored story scene within an adventure graph."""

    model_config = pydantic.ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = pydantic.Field(min_length=1)
    title: str = pydantic.Field(min_length=1)
    description: str | None = None
    location: str | None = None
    intro: str | None = None
    goals: list[str] = pydantic.Field(default_factory=list)
    local_anchors: list[str] = pydantic.Field(default_factory=list)
    entry_effects: list[Effect] = pydantic.Field(default_factory=list)
    exit_effects: list[Effect] = pydantic.Field(default_factory=list)
    render_policy: Literal["hidden", "summary", "prompt"] = "prompt"

    @pydantic.model_validator(mode="after")
    def validate_references(self) -> "StorySceneDefinition":
        """Canonicalize the id and validate local anchor references."""
        self.id = PrimitiveRef.validate_path_segment(self.id)
        self.local_anchors = [
            AnchorRef.parse(value).key() for value in self.local_anchors
        ]
        return self


class TransitionDefinition(pydantic.BaseModel):
    """Authored directed transition between two story scenes."""

    model_config = pydantic.ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = pydantic.Field(min_length=1)
    from_scene: str = pydantic.Field(min_length=1)
    to_scene: str = pydantic.Field(min_length=1)
    label: str = pydantic.Field(min_length=1)
    description: str | None = None
    conditions: list[PrimitiveConditionGroup] = pydantic.Field(default_factory=list)
    carry_anchors: list[str] = pydantic.Field(default_factory=list)
    exit_effects: list[Effect] = pydantic.Field(default_factory=list)
    entry_effects: list[Effect] = pydantic.Field(default_factory=list)
    intro: str | None = None

    @pydantic.model_validator(mode="after")
    def validate_references(self) -> "TransitionDefinition":
        """Canonicalize graph ids and validate carried anchor references."""
        self.id = PrimitiveRef.validate_path_segment(self.id)
        self.from_scene = PrimitiveRef.validate_path_segment(self.from_scene)
        self.to_scene = PrimitiveRef.validate_path_segment(self.to_scene)
        self.carry_anchors = [
            AnchorRef.parse(value).key() for value in self.carry_anchors
        ]
        return self


class AdventureDefinition(pydantic.BaseModel):
    """Validated authored adventure containing scenes and directed transitions."""

    model_config = pydantic.ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = pydantic.Field(min_length=1)
    title: str = pydantic.Field(min_length=1)
    description: str | None = None
    start_scene: str = pydantic.Field(min_length=1)
    scenes: dict[str, StorySceneDefinition] = pydantic.Field(default_factory=dict)
    transitions: dict[str, TransitionDefinition] = pydantic.Field(default_factory=dict)

    @pydantic.model_validator(mode="after")
    def validate_graph(self) -> "AdventureDefinition":
        """Require consistent map keys and valid scene endpoints."""
        self.id = PrimitiveRef.validate_path_segment(self.id)
        self.start_scene = PrimitiveRef.validate_path_segment(self.start_scene)
        if self.start_scene not in self.scenes:
            raise ValueError(
                f"Adventure start scene '{self.start_scene}' does not exist"
            )
        for key, story_scene in self.scenes.items():
            if key != story_scene.id:
                raise ValueError(
                    f"Story scene key '{key}' must match id '{story_scene.id}'"
                )
        for key, transition in self.transitions.items():
            if key != transition.id:
                raise ValueError(
                    f"Transition key '{key}' must match id '{transition.id}'"
                )
            if transition.from_scene not in self.scenes:
                raise ValueError(f"Transition '{key}' source scene does not exist")
            if transition.to_scene not in self.scenes:
                raise ValueError(f"Transition '{key}' destination scene does not exist")
        return self


class TransitionLogEntry(pydantic.BaseModel):
    """Persisted record of one completed story-scene transition."""

    model_config = pydantic.ConfigDict(extra="forbid")

    transition_id: str
    from_scene: str
    to_scene: str
    carry_anchors: list[str] = pydantic.Field(default_factory=list)


class AdventureState(pydantic.BaseModel):
    """Persisted runtime state for the one active adventure."""

    model_config = pydantic.ConfigDict(extra="forbid", str_strip_whitespace=True)

    adventure_id: str = pydantic.Field(min_length=1)
    current_story_scene: str = pydantic.Field(min_length=1)
    visited: list[str] = pydantic.Field(default_factory=list)
    completed: list[str] = pydantic.Field(default_factory=list)
    transition_log: list[TransitionLogEntry] = pydantic.Field(default_factory=list)


class TransitionAvailability(pydantic.BaseModel):
    """Prompt-safe availability result for one outgoing transition."""

    model_config = pydantic.ConfigDict(extra="forbid")

    id: str
    label: str
    to_scene: str
    available: bool
    reasons: list[str] = pydantic.Field(default_factory=list)


class TransitionResult(pydantic.BaseModel):
    """Result of attempting an adventure transition."""

    model_config = pydantic.ConfigDict(extra="forbid")

    ok: bool
    transition_id: str
    from_scene: str | None = None
    to_scene: str | None = None
    intro: str | None = None
    effects: list[EffectResult] = pydantic.Field(default_factory=list)
    error: str | None = None


class AdventureTransitionLedgerInput(pydantic.BaseModel):
    """Validated input payload persisted for an adventure transition ledger event."""

    model_config = pydantic.ConfigDict(extra="forbid")

    adventure_id: str
    transition_id: str
    from_scene: str
    to_scene: str
    carry_anchors: list[str] = pydantic.Field(default_factory=list)


class AdventureMessageContext(pydantic.BaseModel):
    """Adventure identifiers stored inside namespaced scene-message metadata."""

    model_config = pydantic.ConfigDict(extra="forbid")

    adventure_id: str
    story_scene_id: str


class AdventureMessageMetadata(pydantic.BaseModel):
    """Validated Game Primitives metadata attached to a scene message."""

    model_config = pydantic.ConfigDict(extra="forbid")

    game_primitives: AdventureMessageContext


class AdventureEngine:
    """Manage one active adventure inside a Talemate scene's primitive store."""

    def activate(self, scene: "Scene", adventure_id: str) -> AdventureState:
        """Atomically activate an adventure and apply its starting entry effects.

        Raises:
            PrimitiveError: If an adventure is active or a starting effect fails.
        """
        store = PrimitiveStore.for_scene(scene)
        if store.root["runtime"].get("adventure") is not None:
            raise PrimitiveError("An adventure is already active")
        definition = self._definition(store, adventure_id)
        state = AdventureState(
            adventure_id=definition.id,
            current_story_scene=definition.start_scene,
            visited=[definition.start_scene],
        )
        candidate_store = PrimitiveStore(
            copy.deepcopy(store.root), store.max_ledger_length
        )
        batch = apply_effects(
            candidate_store,
            definition.scenes[definition.start_scene].entry_effects,
            reason=f"activate adventure {definition.id}",
        )
        if not batch.ok:
            raise PrimitiveError(
                batch.results[-1].error or "Adventure entry effect failed"
            )
        candidate_store.root["runtime"]["adventure"] = state.model_dump(mode="json")
        store.replace_validated_root(candidate_store.root)
        return state

    def get_state(self, scene: "Scene") -> AdventureState | None:
        """Return validated active adventure state without initializing storage."""
        if GAME_PRIMITIVES_KEY not in scene.game_state.variables:
            return None
        store = PrimitiveStore.for_scene(scene)
        payload = store.root["runtime"].get("adventure")
        return AdventureState.model_validate(payload) if payload is not None else None

    def get_current(self, scene: "Scene") -> StorySceneDefinition | None:
        """Return the active story-scene definition, or ``None`` when inactive."""
        loaded = self._load(scene)
        return loaded[1].scenes[loaded[2].current_story_scene] if loaded else None

    def list_transitions(self, scene: "Scene") -> list[TransitionAvailability]:
        """Return deterministic availability for outgoing transitions."""
        loaded = self._load(scene)
        if loaded is None:
            return []
        _, definition, state = loaded
        return [
            self._availability(scene, transition)
            for transition in definition.transitions.values()
            if transition.from_scene == state.current_story_scene
        ]

    def can_take_transition(
        self, scene: "Scene", transition_id: str
    ) -> TransitionAvailability:
        """Return availability for a named transition from the current scene."""
        loaded = self._load(scene)
        if loaded is None:
            return TransitionAvailability(
                id=transition_id,
                label=transition_id,
                to_scene="",
                available=False,
                reasons=["No active adventure"],
            )
        _, definition, state = loaded
        transition = definition.transitions.get(transition_id)
        if transition is None:
            return TransitionAvailability(
                id=transition_id,
                label=transition_id,
                to_scene="",
                available=False,
                reasons=["Transition does not exist"],
            )
        if transition.from_scene != state.current_story_scene:
            return TransitionAvailability(
                id=transition.id,
                label=transition.label,
                to_scene=transition.to_scene,
                available=False,
                reasons=["Transition is not outgoing from the current story scene"],
            )
        return self._availability(scene, transition)

    def take_transition(
        self, scene: "Scene", transition_id: str, *, render_intro: bool = True
    ) -> TransitionResult:
        """Atomically apply an allowed transition and its ordered effects."""
        loaded = self._load(scene)
        if loaded is None:
            return TransitionResult(
                ok=False, transition_id=transition_id, error="No active adventure"
            )
        store, definition, state = loaded
        transition = definition.transitions.get(transition_id)
        if transition is None:
            availability = TransitionAvailability(
                id=transition_id,
                label=transition_id,
                to_scene="",
                available=False,
                reasons=["Transition does not exist"],
            )
        elif transition.from_scene != state.current_story_scene:
            availability = TransitionAvailability(
                id=transition.id,
                label=transition.label,
                to_scene=transition.to_scene,
                available=False,
                reasons=["Transition is not outgoing from the current story scene"],
            )
        else:
            availability = self._availability(scene, transition)
        if transition is None or not availability.available:
            return TransitionResult(
                ok=False,
                transition_id=transition_id,
                from_scene=state.current_story_scene,
                to_scene=transition.to_scene if transition else None,
                error="; ".join(availability.reasons),
            )

        source = definition.scenes[state.current_story_scene]
        destination = definition.scenes[transition.to_scene]
        candidate_store = PrimitiveStore(
            copy.deepcopy(store.root), store.max_ledger_length
        )
        ordered_effects = [
            *source.exit_effects,
            *transition.exit_effects,
            *transition.entry_effects,
            *destination.entry_effects,
        ]
        batch = apply_effects(
            candidate_store,
            ordered_effects,
            reason=f"adventure transition {transition.id}",
        )
        if not batch.ok:
            return TransitionResult(
                ok=False,
                transition_id=transition.id,
                from_scene=source.id,
                to_scene=destination.id,
                effects=batch.results,
                error=batch.results[-1].error or "Transition effect failed",
            )

        next_state = state.model_copy(deep=True)
        _append_once(next_state.completed, source.id)
        _append_once(next_state.visited, source.id)
        next_state.current_story_scene = destination.id
        _append_once(next_state.visited, destination.id)
        next_state.transition_log.append(
            TransitionLogEntry(
                transition_id=transition.id,
                from_scene=source.id,
                to_scene=destination.id,
                carry_anchors=transition.carry_anchors,
            )
        )
        candidate_store.root["runtime"]["adventure"] = next_state.model_dump(
            mode="json"
        )
        result = TransitionResult(
            ok=True,
            transition_id=transition.id,
            from_scene=source.id,
            to_scene=destination.id,
            intro=(
                transition.intro if transition.intro is not None else destination.intro
            )
            if render_intro
            else None,
            effects=batch.results,
        )
        ledger_input = AdventureTransitionLedgerInput(
            adventure_id=definition.id,
            transition_id=transition.id,
            from_scene=source.id,
            to_scene=destination.id,
            carry_anchors=transition.carry_anchors,
        )
        candidate_store.append_ledger(
            LedgerEntry(
                op="adventure.transition",
                anchor=story_scene_anchor(destination.id).key(),
                input=ledger_input.model_dump(mode="json"),
                output=result.model_dump(mode="json", exclude_none=True),
            )
        )
        store.replace_validated_root(candidate_store.root)
        return result

    def render_current_context(
        self, scene: "Scene", audience: Literal["prompt", "summary"] = "prompt"
    ) -> str:
        """Render prompt-safe current-scene prose and transition availability."""
        return self.render_current_context_with_anchor(scene, audience=audience)[0]

    def render_current_context_with_anchor(
        self, scene: "Scene", audience: Literal["prompt", "summary"] = "prompt"
    ) -> tuple[str, str | None]:
        """Render current context and return its canonical contributing anchor."""
        loaded = self._load(scene)
        if loaded is None:
            return "", None
        _, definition, state = loaded
        story_scene = definition.scenes[state.current_story_scene]
        if story_scene.render_policy == "hidden":
            return "", None
        lines = [
            f"Current adventure: {definition.title}",
            f"Current story scene: {story_scene.title}",
        ]
        if story_scene.description:
            lines.append(story_scene.description)
        if (
            audience == "prompt"
            and story_scene.render_policy == "prompt"
            and story_scene.goals
        ):
            lines.extend(
                ["Scene purpose:", *[f"- {goal}" for goal in story_scene.goals]]
            )
        transitions = self.list_transitions(scene)
        if transitions:
            lines.append("Available transitions:")
            for transition in transitions:
                suffix = "" if transition.available else " (currently unavailable)"
                lines.append(f"- {transition.label}{suffix}")
        return "\n".join(lines), story_scene_anchor(story_scene.id).key()

    def _load(
        self, scene: "Scene"
    ) -> tuple[PrimitiveStore, AdventureDefinition, AdventureState] | None:
        """Load and cross-check active runtime state and its definition."""
        state = self.get_state(scene)
        if state is None:
            return None
        store = PrimitiveStore.for_scene(scene)
        definition = self._definition(store, state.adventure_id)
        if state.current_story_scene not in definition.scenes:
            raise PrimitiveError(
                f"Current story scene '{state.current_story_scene}' does not exist"
            )
        return store, definition, state

    @staticmethod
    def _definition(store: PrimitiveStore, adventure_id: str) -> AdventureDefinition:
        """Load one required adventure definition from the primitive store."""
        payload = store.get_definition("adventures", adventure_id)
        if payload is None:
            raise PrimitiveError(
                f"Adventure definition '{adventure_id}' does not exist"
            )
        return AdventureDefinition.model_validate(payload)

    @staticmethod
    def _availability(
        scene: "Scene", transition: TransitionDefinition
    ) -> TransitionAvailability:
        """Evaluate transition conditions without exposing their internals."""
        available = conditions_match(scene, transition.conditions)
        return TransitionAvailability(
            id=transition.id,
            label=transition.label,
            to_scene=transition.to_scene,
            available=available,
            reasons=[] if available else ["Transition conditions are not met"],
        )


def current_adventure_message_metadata(scene: "Scene") -> dict[str, dict[str, str]]:
    """Return namespaced metadata for messages created in the current story scene."""
    state = AdventureEngine().get_state(scene)
    if state is None:
        return {}
    metadata = AdventureMessageMetadata(
        game_primitives=AdventureMessageContext(
            adventure_id=state.adventure_id,
            story_scene_id=state.current_story_scene,
        )
    )
    return metadata.model_dump(mode="json")


def tag_message_with_current_adventure(scene: "Scene", message: "SceneMessage") -> None:
    """Attach current adventure metadata to a scene message when active."""
    metadata = current_adventure_message_metadata(scene)
    if metadata:
        message.set_meta(**metadata)


def _append_once(values: list[str], value: str) -> None:
    """Append ``value`` only when absent, preserving insertion order."""
    if value not in values:
        values.append(value)


def story_scene_anchor(story_scene_id: str) -> AnchorRef:
    """Return the canonical anchor for a validated story-scene identifier."""
    return AnchorRef(kind="story_scene", id=story_scene_id)
