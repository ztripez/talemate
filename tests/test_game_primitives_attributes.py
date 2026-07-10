"""Tests for Game Primitives primitive attributes."""

from __future__ import annotations

import pytest

from talemate.character import Character
from talemate.game.primitives import AttributeResolver
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.game.primitives.relationships import RelationshipGraph
from talemate.game.primitives.selection import SelectionResult
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


class StubDeckEngine:
    """Deterministic deck engine used by attribute resolver tests."""

    def __init__(self):
        """Create a stub deck engine with a call ledger."""
        self.calls = []

    def draw(self, scene, deck, *, anchor=None, instance_id=None, options=None):
        """Return one fixed card selection and record draw parameters."""
        self.calls.append(
            {
                "scene": scene,
                "deck": deck,
                "anchor": anchor,
                "instance_id": instance_id,
                "options": options,
            }
        )
        return SelectionResult(
            source_type="deck",
            source_id=str(deck),
            result_id="pose-1",
            label="Pose",
            text="Use an over-the-shoulder pose.",
            debug={"mode": "stub"},
        )


class StubRollTableEngine:
    """Deterministic roll table engine used by attribute resolver tests."""

    def __init__(self):
        """Create a stub roll table engine with a call ledger."""
        self.calls = []

    def roll(self, scene, table, *, anchor=None, context=None, apply_effects=False):
        """Return one fixed roll-table selection and record roll parameters."""
        self.calls.append(
            {
                "scene": scene,
                "table": table,
                "anchor": anchor,
                "context": context,
                "apply_effects": apply_effects,
            }
        )
        return SelectionResult(
            source_type="roll_table",
            source_id=str(table),
            result_id="calm",
            label="Calm",
            text="The model reacts calmly.",
            debug={"mode": "stub"},
        )


def test_literal_attribute_resolution():
    """Literal primitive attributes return their stored JSON value."""
    scene = Scene()
    resolver = AttributeResolver()
    resolver.set(
        scene,
        "character:Model/attributes/current_mood",
        {"source": "literal", "render_policy": "prompt", "value": "focused"},
    )

    resolution = resolver.resolve(scene, "character:Model/attributes/current_mood")

    assert resolution.value == "focused"
    assert resolver.render(scene, "character:Model/attributes/current_mood") == (
        "Current Mood: focused"
    )


def test_meter_attribute_resolution_and_summary_rendering():
    """Meter-backed summary attributes avoid raw numeric prompt dumps."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive("character:Model/meters/confidence", {"value": 2})
    resolver = AttributeResolver()
    resolver.set(
        scene,
        "character:Model/attributes/confidence",
        {
            "source": "meter",
            "ref": "character:Model/meters/confidence",
            "render_policy": "summary",
        },
    )

    resolution = resolver.resolve(scene, "character:Model/attributes/confidence")
    rendered = resolver.render(scene, "character:Model/attributes/confidence")

    assert resolution.value == 2
    assert rendered == "Confidence is elevated."
    assert "2" not in rendered


def test_relationship_attribute_resolution_uses_prompt_safe_summary():
    """Relationship-backed attributes render relationship graph prose."""
    scene = Scene()
    graph = RelationshipGraph()
    graph.set(scene, "Model", "Photographer", "trust", 4)
    resolver = AttributeResolver(relationship_graph=graph)
    resolver.set(
        scene,
        "relationship:Model->Photographer/attributes/trust_summary",
        {
            "source": "relationship",
            "ref": "relationship:Model->Photographer/meters/trust",
            "render_policy": "summary",
        },
    )

    resolution = resolver.resolve(
        scene, "relationship:Model->Photographer/attributes/trust_summary"
    )
    rendered = resolver.render(
        scene, "relationship:Model->Photographer/attributes/trust_summary"
    )

    assert resolution.value == 4
    assert rendered == "Model trusts Photographer."
    assert "4" not in rendered


def test_deck_attribute_resolution_uses_injected_deck_engine():
    """Deck-backed attributes resolve a requested selection result field."""
    scene = Scene()
    deck_engine = StubDeckEngine()
    resolver = AttributeResolver(deck_engine=deck_engine)
    resolver.set(
        scene,
        "character:Model/attributes/current_pose",
        {
            "source": "deck",
            "ref": "character:Model/decks/poses",
            "render_policy": "prompt",
            "options": {"result_field": "text", "avoid_recent": 3},
        },
    )

    resolution = resolver.resolve(scene, "character:Model/attributes/current_pose")

    assert resolution.value == "Use an over-the-shoulder pose."
    assert resolution.rendered == "Use an over-the-shoulder pose."
    assert deck_engine.calls[0]["options"]["avoid_recent"] == 3


def test_roll_table_attribute_resolution_uses_injected_roll_engine():
    """Roll-table-backed attributes resolve a requested selection result field."""
    scene = Scene()
    roll_engine = StubRollTableEngine()
    resolver = AttributeResolver(roll_table_engine=roll_engine)
    resolver.set(
        scene,
        "project:studio-session/attributes/reaction",
        {
            "source": "roll_table",
            "ref": "project:studio-session/roll_tables/reaction",
            "render_policy": "hidden",
            "options": {"result_field": "label", "apply_effects": True},
        },
    )

    resolution = resolver.resolve(
        scene,
        "project:studio-session/attributes/reaction",
        context={"turn": 1},
    )

    assert resolution.value == "Calm"
    assert roll_engine.calls[0]["context"] == {"turn": 1}
    assert roll_engine.calls[0]["apply_effects"] is True


def test_hidden_attribute_does_not_render_prompt_text():
    """Hidden attributes resolve internally but render no prompt text."""
    scene = Scene()
    resolver = AttributeResolver()
    resolver.set(
        scene,
        "character:Model/attributes/secret",
        {"source": "literal", "render_policy": "hidden", "value": "do not show"},
    )

    assert resolver.resolve(scene, "character:Model/attributes/secret").value == (
        "do not show"
    )
    assert resolver.render(scene, "character:Model/attributes/secret") == ""


def test_memory_attribute_renders_only_for_memory_audience():
    """Memory-scoped attributes do not leak into prompt rendering."""
    scene = Scene()
    resolver = AttributeResolver()
    resolver.set(
        scene,
        "character:Model/attributes/lasting_truth",
        {"source": "literal", "render_policy": "memory", "value": "trust is earned"},
    )
    resolver.set(
        scene,
        "character:Model/attributes/prompt_fact",
        {"source": "literal", "render_policy": "prompt", "value": "visible"},
    )

    assert resolver.render(scene, "character:Model/attributes/lasting_truth") == ""
    assert (
        resolver.render(
            scene, "character:Model/attributes/lasting_truth", audience="memory"
        )
        == "Lasting Truth: trust is earned"
    )
    assert (
        resolver.render(
            scene, "character:Model/attributes/prompt_fact", audience="memory"
        )
        == ""
    )


def test_invalid_audience_and_missing_selection_field_fail_loudly():
    """Invalid render audiences and absent requested result fields raise errors."""
    scene = Scene()
    resolver = AttributeResolver(deck_engine=StubDeckEngine())
    resolver.set(
        scene,
        "character:Model/attributes/current_pose",
        {
            "source": "deck",
            "ref": "character:Model/decks/poses",
            "render_policy": "prompt",
            "options": {"result_field": "result_id"},
        },
    )
    resolver.set(
        scene,
        "character:Model/attributes/current_pose_label",
        {
            "source": "deck",
            "ref": "character:Model/decks/poses",
            "render_policy": "prompt",
            "options": {"result_field": "text"},
        },
    )

    with pytest.raises(ValueError):
        resolver.render(
            scene, "character:Model/attributes/current_pose", audience="promt"
        )

    empty_text_engine = StubDeckEngine()
    empty_text_engine.draw = lambda *args, **kwargs: SelectionResult(
        source_type="deck", source_id="deck", result_id="card", debug={}
    )
    resolver = AttributeResolver(deck_engine=empty_text_engine)
    with pytest.raises(PrimitiveError, match="field 'text' is absent"):
        resolver.resolve(scene, "character:Model/attributes/current_pose_label")


def test_clock_modifier_and_state_ref_attribute_sources():
    """Clock, modifier, and state-ref sources resolve deterministic values."""
    scene = Scene()
    scene.game_state.variables["story"] = {"phase": "warmup"}
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive("scene:main/clocks/warmup", {"value": 3})
    store.set_definition(
        "modifiers",
        "confidence_bonus",
        {"id": "confidence_bonus", "applies_to": "reaction", "add": 2},
    )
    resolver = AttributeResolver()
    resolver.set(
        scene,
        "scene:main/attributes/warmup_clock",
        {"source": "clock", "ref": "scene:main/clocks/warmup"},
    )
    resolver.set(
        scene,
        "scene:main/attributes/bonus",
        {"source": "modifier", "ref": "confidence_bonus"},
    )
    resolver.set(
        scene,
        "scene:main/attributes/phase",
        {"source": "state_ref", "ref": "story/phase"},
    )

    assert resolver.resolve(scene, "scene:main/attributes/warmup_clock").value == 3
    assert resolver.resolve(scene, "scene:main/attributes/bonus").value == 2
    assert resolver.resolve(scene, "scene:main/attributes/phase").value == "warmup"


def test_failed_conditions_skip_side_effectful_attribute_sources():
    """Inactive attribute conditions avoid invoking deck or roll engines."""
    scene = Scene()
    deck_engine = StubDeckEngine()
    resolver = AttributeResolver(deck_engine=deck_engine)
    resolver.set(
        scene,
        "character:Model/attributes/current_pose",
        {
            "source": "deck",
            "ref": "character:Model/decks/poses",
            "render_policy": "prompt",
            "conditions": [{"conditions": [{"kind": "never"}]}],
        },
    )

    resolution = resolver.resolve(scene, "character:Model/attributes/current_pose")

    assert resolution.value is None
    assert resolution.debug == {"active": False, "reason": "conditions"}
    assert resolver.render(scene, "character:Model/attributes/current_pose") == ""
    assert deck_engine.calls == []


def test_invalid_attribute_refs_produce_clear_errors():
    """Resolver rejects references outside the attributes primitive kind."""
    scene = Scene()
    resolver = AttributeResolver()

    with pytest.raises(ValueError, match="attributes primitive ref"):
        resolver.set(scene, "character:Model/meters/confidence", {"source": "literal"})

    with pytest.raises(PrimitiveError, match="Attribute source not found"):
        resolver.resolve(scene, "character:Model/attributes/missing")


def test_attribute_source_rejects_ignored_fields_and_peek_draw_options():
    """Attribute source validation rejects missing data and ignored options."""
    scene = Scene()
    resolver = AttributeResolver()

    with pytest.raises(ValueError, match="require explicit value"):
        resolver.set(
            scene, "scene:main/attributes/missing_literal", {"source": "literal"}
        )

    with pytest.raises(ValueError, match="cannot define ref"):
        resolver.set(
            scene,
            "scene:main/attributes/literal_ref",
            {"source": "literal", "value": None, "ref": "scene:main/meters/x"},
        )

    with pytest.raises(ValueError, match="cannot define value"):
        resolver.set(
            scene,
            "scene:main/attributes/meter_value",
            {"source": "meter", "ref": "scene:main/meters/x", "value": 1},
        )

    with pytest.raises(ValueError, match="peek mode does not accept draw options"):
        resolver.set(
            scene,
            "scene:main/attributes/peek_pose",
            {
                "source": "deck",
                "ref": "scene:main/decks/poses",
                "options": {"mode": "peek", "result_field": "text"},
            },
        )


def test_visible_null_attribute_render_fails_loudly():
    """Visible literal null attributes cannot masquerade as hidden output."""
    scene = Scene()
    resolver = AttributeResolver()
    resolver.set(
        scene,
        "scene:main/attributes/null_prompt",
        {"source": "literal", "render_policy": "prompt", "value": None},
    )

    with pytest.raises(ValueError, match="cannot be None"):
        resolver.render(scene, "scene:main/attributes/null_prompt")


async def test_primitive_attributes_do_not_write_character_base_attributes():
    """Resolving primitive attributes leaves character base attributes untouched."""
    scene = Scene()
    character = Character(name="Model", base_attributes={"mood": "old"})
    actor = scene.Actor(character, None)
    actor.scene = scene
    scene.actors.append(actor)
    scene.character_data["Model"] = character
    resolver = AttributeResolver()
    resolver.set(
        scene,
        "character:Model/attributes/mood",
        {"source": "literal", "render_policy": "prompt", "value": "focused"},
    )

    resolution = resolver.resolve(scene, "character:Model/attributes/mood")

    assert resolution.value == "focused"
    assert character.base_attributes == {"mood": "old"}
