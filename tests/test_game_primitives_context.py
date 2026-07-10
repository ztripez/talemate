"""Tests for prompt-safe Game Primitives relevant-context rendering."""

from __future__ import annotations

from talemate.character import Character
from talemate.game.primitives.attributes import AttributeResolver
from talemate.game.primitives.context import PrimitiveContextRenderer
from talemate.game.primitives.decks import DeckEngine
from talemate.game.primitives.relationships import RelationshipGraph
from talemate.game.primitives.schema import GAME_PRIMITIVES_KEY
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


def _add_character(scene: Scene, name: str, *, is_player: bool = False) -> Character:
    """Attach a character to a scene without invoking agent-backed setup."""
    character = Character(name=name, is_player=is_player)
    actor_cls = scene.Player if is_player else scene.Actor
    actor = actor_cls(character, None)
    actor.scene = scene
    scene.actors.append(actor)
    scene.character_data[name] = character
    return character


def test_scene_without_primitive_state_remains_untouched():
    """Rendering a scene without primitives returns empty context without mutation."""
    scene = Scene()

    result = PrimitiveContextRenderer().render_relevant_context(scene)

    assert result.content == ""
    assert result.anchors == []
    assert result.refs == []
    assert GAME_PRIMITIVES_KEY not in scene.game_state.variables


def test_hidden_prompt_and_summary_attribute_rendering():
    """Context rendering respects hidden, direct, and summarized policies."""
    scene = Scene()
    resolver = AttributeResolver()
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive("scene:main/meters/danger", {"value": 2})
    resolver.set(
        scene,
        "scene:main/attributes/secret",
        {"source": "literal", "render_policy": "hidden", "value": "classified"},
    )
    resolver.set(
        scene,
        "scene:main/attributes/weather",
        {"source": "literal", "render_policy": "prompt", "value": "Rainy"},
    )
    resolver.set(
        scene,
        "scene:main/attributes/danger",
        {
            "source": "meter",
            "ref": "scene:main/meters/danger",
            "render_policy": "summary",
        },
    )

    result = PrimitiveContextRenderer().render_relevant_context(scene)

    assert "Weather: Rainy" in result.content
    assert "Danger is elevated." in result.content
    assert "classified" not in result.content
    assert "danger = 2" not in result.content
    assert "Scene context:" in result.content


def test_conversation_relationship_is_directional_and_relevant():
    """Conversation context includes only the speaker-to-target relationship edge."""
    scene = Scene()
    _add_character(scene, "Model")
    _add_character(scene, "Photographer", is_player=True)
    graph = RelationshipGraph()
    graph.set(scene, "Model", "Photographer", "trust", 3)
    graph.set(scene, "Photographer", "Model", "trust", -3)

    result = PrimitiveContextRenderer(relationship_graph=graph).render_relevant_context(
        scene,
        audience="conversation",
        character="Model",
        target_character="Photographer",
    )

    assert "Model trusts Photographer." in result.content
    assert "Photographer distrusts Model." not in result.content
    assert result.anchors == ["relationship:Model->Photographer"]


def test_narrator_includes_relationships_only_between_active_characters():
    """Narrator context excludes relationship edges involving inactive characters."""
    scene = Scene()
    _add_character(scene, "Alice")
    _add_character(scene, "Bob")
    graph = RelationshipGraph()
    graph.set(scene, "Alice", "Bob", "trust", 3)
    graph.set(scene, "Alice", "Carol", "trust", 3)

    result = PrimitiveContextRenderer(relationship_graph=graph).render_relevant_context(
        scene, audience="narrator"
    )

    assert "Alice trusts Bob." in result.content
    assert "Alice trusts Carol." not in result.content


def test_deck_backed_attribute_and_runtime_internals_never_render():
    """Prompt rendering skips mutating deck attributes and all deck runtime internals."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "decks",
        "poses",
        {
            "id": "poses",
            "name": "Poses",
            "mode": "physical",
            "cards": [{"id": "first", "label": "First", "text": "First pose."}],
        },
    )
    AttributeResolver().set(
        scene,
        "scene:main/attributes/current_pose",
        {
            "source": "deck",
            "ref": "poses",
            "render_policy": "prompt",
            "options": {"result_field": "text"},
        },
    )
    DeckEngine().peek(scene, "poses")

    result = PrimitiveContextRenderer().render_relevant_context(
        scene, include_debug=True
    )

    assert result.content == ""
    assert "draw_pile" not in result.content
    assert "discard" not in result.content
    assert "draw_count" not in result.content
    assert result.debug.skipped_unsafe_attributes == [
        "scene:main/attributes/current_pose"
    ]
    assert not any(entry["op"] == "deck.draw" for entry in store.recent_ledger())


def test_modifier_and_primitive_runtime_state_refs_never_render():
    """Modifier values and primitive runtime paths cannot bypass prompt safeguards."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "modifiers",
        "bonus",
        {"id": "bonus", "applies_to": "reaction", "add": 4},
    )
    resolver = AttributeResolver()
    resolver.set(
        scene,
        "scene:main/attributes/bonus",
        {
            "source": "modifier",
            "ref": "bonus",
            "render_policy": "prompt",
        },
    )
    resolver.set(
        scene,
        "scene:main/attributes/runtime_version",
        {
            "source": "state_ref",
            "ref": "game_primitives/version",
            "render_policy": "prompt",
        },
    )

    result = PrimitiveContextRenderer().render_relevant_context(
        scene, include_debug=True
    )

    assert result.content == ""
    assert result.debug.skipped_unsafe_attributes == [
        "scene:main/attributes/bonus",
        "scene:main/attributes/runtime_version",
    ]


def test_roll_table_backed_attribute_never_rolls_or_renders():
    """Prompt rendering skips roll-table attributes and creates no roll ledger entry."""
    scene = Scene()
    store = PrimitiveStore.for_scene(scene)
    store.set_definition(
        "roll_tables",
        "reaction",
        {
            "id": "reaction",
            "name": "Reaction",
            "mode": "weighted",
            "rows": [{"id": "calm", "label": "Calm", "weight": 1}],
        },
    )
    AttributeResolver().set(
        scene,
        "scene:main/attributes/reaction",
        {
            "source": "roll_table",
            "ref": "reaction",
            "render_policy": "prompt",
            "options": {"result_field": "label"},
        },
    )

    result = PrimitiveContextRenderer().render_relevant_context(
        scene, include_debug=True
    )

    assert result.content == ""
    assert result.debug.skipped_unsafe_attributes == ["scene:main/attributes/reaction"]
    assert not any(entry["op"] == "roll_table.roll" for entry in store.recent_ledger())


def test_creator_context_excludes_scene_runtime_attributes():
    """Creator context renders focused character data without scene runtime state."""
    scene = Scene()
    resolver = AttributeResolver()
    resolver.set(
        scene,
        "scene:main/attributes/danger",
        {"source": "literal", "render_policy": "prompt", "value": "Immediate"},
    )
    resolver.set(
        scene,
        "character:Model/attributes/pose",
        {"source": "literal", "render_policy": "prompt", "value": "Relaxed"},
    )

    result = PrimitiveContextRenderer().render_relevant_context(
        scene, audience="creator", character="Model"
    )

    assert "Pose: Relaxed" in result.content
    assert "Immediate" not in result.content
    assert result.anchors == ["character:Model"]


def test_existing_project_and_scene_objects_are_relevant():
    """Existing project and in-scene object anchors contribute prompt attributes."""
    scene = Scene()
    scene.project_name = "studio-session"
    scene.world_state.items["Camera"] = {"state": "ready"}
    resolver = AttributeResolver()
    resolver.set(
        scene,
        "project:studio-session/attributes/phase",
        {"source": "literal", "render_policy": "prompt", "value": "Warmup"},
    )
    resolver.set(
        scene,
        "object:Camera/attributes/film",
        {"source": "literal", "render_policy": "prompt", "value": "Loaded"},
    )

    result = PrimitiveContextRenderer().render_relevant_context(
        scene, audience="narrator"
    )

    assert "Project context — studio-session:" in result.content
    assert "Object context — Camera:" in result.content
    assert "Phase: Warmup" in result.content
    assert "Film: Loaded" in result.content
