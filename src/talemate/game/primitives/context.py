"""Render deterministic game state as prose safe for language-model prompts.

The renderer selects relevant anchored attributes and relationship summaries while
excluding hidden values, mutating sources, and raw mechanical runtime state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pydantic

from talemate.game.primitives.anchors import (
    AnchorRef,
    PrimitiveRef,
    relationship_participants,
)
from talemate.game.primitives.attributes import AttributeResolver
from talemate.game.primitives.adventure import AdventureEngine
from talemate.game.primitives.relationships import RelationshipGraph
from talemate.game.primitives.schema import GAME_PRIMITIVES_KEY
from talemate.game.primitives.store import PrimitiveStore

if TYPE_CHECKING:
    from talemate.tale_mate import Scene

#: Prompt-building audience used to choose relevant primitive anchors.
ContextAudience = Literal["conversation", "narrator", "creator"]

_PROMPT_SAFE_ATTRIBUTE_SOURCES = {
    "literal",
    "meter",
    "clock",
    "relationship",
}


class PrimitiveRenderedContext(pydantic.BaseModel):
    """Prompt-safe rendered context assembled from relevant primitive anchors.

    Attributes:
        title: Stable title used by the generated dynamic instruction.
        content: Prompt-safe prose content, or an empty string when nothing renders.
        anchors: Canonical anchor keys that contributed rendered content.
        refs: Canonical primitive refs that contributed rendered attribute content.
        debug: Optional validated relevance and omission metadata.
    """

    model_config = pydantic.ConfigDict(extra="forbid", allow_inf_nan=False)

    title: str = "Game Primitives - Relevant State"
    content: str
    anchors: list[str] = pydantic.Field(default_factory=list)
    refs: list[str] = pydantic.Field(default_factory=list)
    debug: "PrimitiveContextDebug | None" = None


class PrimitiveContextDebug(pydantic.BaseModel):
    """Safe diagnostic metadata for primitive context relevance decisions.

    Attributes:
        audience: Prompt-building audience used for anchor collection.
        candidate_anchors: Ordered anchors considered by the renderer.
        skipped_unsafe_attributes: Attribute refs omitted because their sources are
            mutating or expose unrestricted mechanical state.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    audience: ContextAudience
    candidate_anchors: list[str] = pydantic.Field(default_factory=list)
    skipped_unsafe_attributes: list[str] = pydantic.Field(default_factory=list)


class PrimitiveContextRequest(pydantic.BaseModel):
    """Validated request for rendering relevant primitive prompt context.

    Attributes:
        audience: Prompt-building audience used for relevance collection.
        character: Optional speaking or focused character name.
        target_character: Optional conversation target character name.
        include_debug: Whether safe relevance diagnostics should be returned.
    """

    model_config = pydantic.ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True
    )

    audience: ContextAudience = "conversation"
    character: str | None = pydantic.Field(default=None, min_length=1)
    target_character: str | None = pydantic.Field(default=None, min_length=1)
    include_debug: pydantic.StrictBool = False


class PrimitiveContextRenderer:
    """Render deterministic primitive context without exposing mechanical internals.

    The renderer selects existing anchors relevant to the requested audience and
    renders only policy-aware attributes and relationship summaries. Definitions,
    ledger data, deck runtime state, roll debug data, and generic raw primitive
    payloads are never serialized into prompt content.
    """

    def __init__(
        self,
        attribute_resolver: AttributeResolver | None = None,
        relationship_graph: RelationshipGraph | None = None,
    ):
        """Create a context renderer with optional primitive services.

        Args:
            attribute_resolver: Resolver used for prompt-safe attribute rendering.
            relationship_graph: Graph used for prompt-safe relationship summaries.
        """
        self.attribute_resolver = attribute_resolver or AttributeResolver()
        self.relationship_graph = relationship_graph or RelationshipGraph()

    def render_relevant_context(
        self,
        scene: "Scene",
        *,
        audience: ContextAudience = "conversation",
        character: str | None = None,
        target_character: str | None = None,
        include_debug: bool = False,
    ) -> PrimitiveRenderedContext:
        """Render prompt-safe primitive context relevant to an agent request.

        Args:
            scene: Talemate scene containing optional Game Primitives state.
            audience: Prompt-building audience used for relevance collection.
            character: Optional speaking or focused character name.
            target_character: Optional explicit conversation target character name.
            include_debug: Whether safe relevance diagnostics should be included.

        Returns:
            Rendered context with stable title, prose content, contributing anchors,
            contributing refs, and optional safe diagnostics.

        Raises:
            pydantic.ValidationError: If request fields or persisted attribute
                payloads are invalid.
            PrimitiveError: If relevant persisted primitive state is invalid.
            ValueError: If a visible attribute cannot be rendered safely.
        """
        request = PrimitiveContextRequest.model_validate(
            {
                "audience": audience,
                "character": character,
                "target_character": target_character,
                "include_debug": include_debug,
            }
        )
        if GAME_PRIMITIVES_KEY not in scene.game_state.variables:
            return PrimitiveRenderedContext(content="")

        store = PrimitiveStore.for_scene(scene)
        available = set(store.iter_anchor_keys())
        candidates = self._relevant_anchors(scene, request, available)
        sections: list[str] = []
        rendered_anchors: list[str] = []
        rendered_refs: list[str] = []
        skipped_sources: list[str] = []

        if request.audience != "creator":
            adventure_context, story_scene_anchor = (
                AdventureEngine().render_current_context_with_anchor(scene)
            )
            if adventure_context and story_scene_anchor is not None:
                sections.append(adventure_context)
                rendered_anchors.append(story_scene_anchor)

        for anchor_key in candidates:
            lines, refs, skipped = self._render_anchor(scene, store, anchor_key)
            skipped_sources.extend(skipped)
            if not lines:
                continue
            sections.append(_render_section(anchor_key, lines))
            rendered_anchors.append(anchor_key)
            rendered_refs.extend(refs)

        debug: PrimitiveContextDebug | None = None
        if request.include_debug:
            debug = PrimitiveContextDebug(
                audience=request.audience,
                candidate_anchors=candidates,
                skipped_unsafe_attributes=skipped_sources,
            )
        return PrimitiveRenderedContext(
            content="\n\n".join(sections),
            anchors=rendered_anchors,
            refs=rendered_refs,
            debug=debug,
        )

    def _relevant_anchors(
        self,
        scene: "Scene",
        request: PrimitiveContextRequest,
        available: set[str],
    ) -> list[str]:
        """Return deterministic candidate anchors for a validated render request."""
        active_names = sorted(scene.character_names)
        if request.audience == "conversation":
            anchors = _conversation_anchors(scene, request, active_names, available)
        elif request.audience == "narrator":
            anchors = _narrator_anchors(active_names, available)
        else:
            anchors = _creator_anchors(request)
        if request.audience != "creator":
            _append_unique(anchors, "scene:main", first=True)
            _append_environment_anchors(anchors, scene, available)
        return anchors

    def _render_anchor(
        self, scene: "Scene", store: PrimitiveStore, anchor_key: str
    ) -> tuple[list[str], list[str], list[str]]:
        """Render safe attribute and relationship lines for one anchor."""
        lines: list[str] = []
        refs: list[str] = []
        skipped: list[str] = []
        for attribute_id in sorted(store.iter_primitives(anchor_key, "attributes")):
            ref = PrimitiveRef(
                anchor=AnchorRef.parse(anchor_key), kind="attributes", id=attribute_id
            )
            source = self.attribute_resolver.get(scene, ref)
            if source.source not in _PROMPT_SAFE_ATTRIBUTE_SOURCES:
                skipped.append(ref.key())
                continue
            rendered = self.attribute_resolver.render(scene, ref, audience="prompt")
            if rendered:
                lines.append(rendered)
                refs.append(ref.key())

        anchor = AnchorRef.parse(anchor_key)
        if anchor.kind == "relationship":
            source, target = relationship_participants(anchor)
            summary = self.relationship_graph.summary(scene, source, target)
            if summary:
                lines.append(summary)
        return lines, refs, skipped


def _likely_target(scene: "Scene", speaker: str, active_names: list[str]) -> str | None:
    """Return a conservative likely conversation target, or ``None``."""
    last_player_message = scene.last_player_message()
    if last_player_message is not None:
        candidate = last_player_message.character_name
        if candidate in active_names and candidate != speaker:
            return candidate
    player = scene.get_explicit_player_character()
    if player is not None and player.name in active_names and player.name != speaker:
        return player.name
    others = [name for name in active_names if name != speaker]
    return others[0] if len(others) == 1 else None


def _conversation_anchors(
    scene: "Scene",
    request: PrimitiveContextRequest,
    active_names: list[str],
    available: set[str],
) -> list[str]:
    """Return speaker, target, and directional relationship anchors."""
    if not request.character:
        return []
    anchors = [f"character:{request.character}"]
    target = request.target_character or _likely_target(
        scene, request.character, active_names
    )
    if target:
        _append_unique(anchors, f"character:{target}")
        relationship_key = f"relationship:{request.character}->{target}"
        if relationship_key in available:
            _append_unique(anchors, relationship_key)
    return anchors


def _narrator_anchors(active_names: list[str], available: set[str]) -> list[str]:
    """Return narrator-relevant active character and relationship anchors."""
    anchors = [f"character:{name}" for name in active_names]
    active_set = set(active_names)
    for anchor_key in sorted(available):
        anchor = AnchorRef.parse(anchor_key)
        if anchor.kind != "relationship":
            continue
        source, target = relationship_participants(anchor)
        if source in active_set and target in active_set:
            _append_unique(anchors, anchor_key)
    return anchors


def _creator_anchors(request: PrimitiveContextRequest) -> list[str]:
    """Return creator-relevant focused character anchors."""
    return [f"character:{request.character}"] if request.character else []


def _append_environment_anchors(
    anchors: list[str], scene: "Scene", available: set[str]
) -> None:
    """Append existing project and in-scene object anchors."""
    project_key = f"project:{scene.project_name}"
    if project_key in available:
        _append_unique(anchors, project_key)
    for object_name in sorted(scene.world_state.items):
        object_key = f"object:{object_name}"
        if object_key in available:
            _append_unique(anchors, object_key)


def _append_unique(values: list[str], value: str, *, first: bool = False) -> None:
    """Append a string only when it is not already present."""
    if value in values:
        return
    if first:
        values.insert(0, value)
    else:
        values.append(value)


def _render_section(anchor_key: str, lines: list[str]) -> str:
    """Render one anchor section without exposing raw primitive values."""
    anchor = AnchorRef.parse(anchor_key)
    title = {
        "scene": "Scene context",
        "character": f"Character context — {anchor.id}",
        "relationship": "Relationship context",
        "object": f"Object context — {anchor.id}",
        "project": f"Project context — {anchor.id}",
    }.get(anchor.kind, f"{anchor.kind.replace('_', ' ').title()} context — {anchor.id}")
    return "\n".join([f"{title}:", *[f"- {line}" for line in lines]])
