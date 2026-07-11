"""Tests for Game Primitives relationship graph."""

from __future__ import annotations

import pytest
from _node_test_helpers import run_node

import talemate.game.engine.nodes.load_definitions  # noqa: F401
from talemate.context import ActiveScene
from talemate.game.engine.nodes.registry import get_node
from talemate.game.primitives.conditions import evaluate_condition_input
from talemate.game.primitives.definitions import MeterPayload
from talemate.game.primitives.effects import apply_effects
from talemate.game.primitives.relationships import (
    RelationshipGraph,
    _dimension_from_payload,
)
from talemate.game.primitives.store import PrimitiveStore
from talemate.tale_mate import Scene


def test_relationship_edge_create_and_directional_state():
    """Relationship anchors are directional and separate for A->B and B->A."""
    scene = Scene()
    graph = RelationshipGraph()

    assert graph.edge(scene, "Alice", "Bob") is None
    created = graph.edge(scene, "Alice", "Bob", create=True)
    assert created is not None
    assert graph.edge(scene, "Alice", "Bob") is not None

    graph.set(scene, "Alice", "Bob", "trust", 2)
    graph.set(scene, "Bob", "Alice", "trust", -1)

    assert graph.edge(scene, "Alice", "Bob") is not None
    assert graph.get(scene, "Alice", "Bob", "trust") == 2
    assert graph.get(scene, "Bob", "Alice", "trust") == -1


def test_relationship_set_adjust_bounds_and_records_ledger():
    """Set and adjust mutate dimensions with bounds and relationship ledger entries."""
    scene = Scene()
    graph = RelationshipGraph()

    set_meter = graph.set(scene, "Model", "Photographer", "trust", 4, min=-5, max=5)
    current, previous = graph.adjust(scene, "Model", "Photographer", "trust", 1)
    entries = PrimitiveStore.for_scene(scene).recent_ledger(2)

    assert isinstance(set_meter, MeterPayload)
    assert isinstance(current, MeterPayload)
    assert previous == 4
    assert current.value == 5
    assert graph.get(scene, "Model", "Photographer", "trust") == 5
    with pytest.raises(ValueError, match="within min and max"):
        graph.adjust(scene, "Model", "Photographer", "trust", 1)
    assert graph.get(scene, "Model", "Photographer", "trust") == 5
    assert [entry["op"] for entry in entries] == [
        "relationship.set",
        "relationship.adjust",
    ]
    assert entries[0]["ref"] == "relationship:Model->Photographer/meters/trust"
    assert entries[0]["input"]["value"] == 4
    assert entries[0]["output"] == {"current": 4}
    assert entries[-1]["anchor"] == "relationship:Model->Photographer"
    assert entries[-1]["input"]["by"] == 1
    assert entries[-1]["output"] == {"previous": 4, "current": 5}


def test_relationship_reads_only_canonical_meter_payloads():
    """Relationship dimensions require canonical bounded meter payloads."""
    scene = Scene()
    graph = RelationshipGraph()
    store = PrimitiveStore.for_scene(scene)
    store.set_primitive(
        "relationship:Model->Photographer/meters/trust",
        {
            "id": "trust",
            "value": 2,
            "min": -5,
            "max": 5,
            "render_policy": "summary",
        },
    )

    assert graph.get(scene, "Model", "Photographer", "trust") == 2
    with pytest.raises(ValueError, match="Field required"):
        store.set_primitive(
            "relationship:Model->Photographer/meters/comfort", {"value": 3}
        )
    with pytest.raises(ValueError, match="within min and max"):
        store.set_primitive(
            "relationship:Model->Photographer/meters/comfort",
            {"id": "comfort", "value": 6, "min": -5, "max": 5},
        )


def test_relationship_payload_reader_rejects_noncanonical_values():
    """Relationship reads reject scalar and value-only persistence shapes."""
    dimension = _dimension_from_payload(
        "trust", {"id": "trust", "value": 2, "min": -5, "max": 5}
    )

    assert dimension is not None
    assert dimension.model_dump(mode="json") == {
        "id": "trust",
        "label": None,
        "min": -5,
        "max": 5,
        "value": 2,
        "render_policy": "hidden",
    }
    with pytest.raises(ValueError, match="valid dictionary|model_type"):
        _dimension_from_payload("trust", 2)
    with pytest.raises(ValueError, match="Field required"):
        _dimension_from_payload("trust", {"value": 2})


def test_relationship_summary_omits_hidden_dimensions_and_raw_numbers():
    """Prompt summaries render prose and skip hidden relationship dimensions."""
    scene = Scene()
    graph = RelationshipGraph()

    graph.set(scene, "Model", "Photographer", "trust", 2, render_policy="summary")
    graph.set(scene, "Model", "Photographer", "comfort", 5, render_policy="hidden")

    summary = graph.summary(scene, "Model", "Photographer")

    assert "beginning to trust" in summary
    assert "comfort" not in summary
    assert "2" not in summary
    assert graph.relevant_for(scene, "Model", "Photographer") == [summary]


def test_relationship_conditions_and_effects_interoperate():
    """Relationship dimensions work with primitive conditions and effects."""
    scene = Scene()
    graph = RelationshipGraph()
    graph.set(scene, "Model", "Photographer", "trust", 2)

    result = apply_effects(
        PrimitiveStore.for_scene(scene),
        {
            "op": "inc",
            "target": "relationship:Model->Photographer/meters/trust",
            "by": 1,
        },
    )
    matches, debug = evaluate_condition_input(
        scene,
        {
            "kind": "relationship",
            "anchor": "relationship:Model->Photographer",
            "dimension": "trust",
            "operator": ">=",
            "value": 3,
        },
    )

    assert result.ok is True
    assert graph.get(scene, "Model", "Photographer", "trust") == 3
    assert matches is True
    assert debug[0]["conditions"][0]["actual"] == 3
    effect_entry = [
        entry
        for entry in PrimitiveStore.for_scene(scene).recent_ledger(5)
        if entry["op"] == "effect.inc"
    ][0]
    assert effect_entry["ref"] == "relationship:Model->Photographer/meters/trust"
    assert effect_entry["output"]["previous"] == 2
    assert effect_entry["output"]["current"] == 3


async def test_relationship_adjust_node_returns_summary():
    """The Adjust node exposes relationship mutation to graph execution."""
    scene = Scene()
    with ActiveScene(scene):
        node_cls = get_node("primitives/relationships/Adjust")
    node = node_cls()

    outputs = await run_node(
        node,
        scene=scene,
        inputs={
            "source": "Model",
            "target": "Photographer",
            "dimension": "trust",
            "by": 2,
        },
    )

    assert outputs["value"] == 2
    assert outputs["previous"] is None
    assert outputs["anchor"] == "relationship:Model->Photographer"
    assert "beginning to trust" in outputs["summary"]
