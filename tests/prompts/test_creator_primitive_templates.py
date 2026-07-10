"""Tests for creator Game Primitive planning and authoring templates."""

from unittest.mock import Mock

from talemate.prompts.base import Prompt


def test_primitive_plan_renders_context_shape_and_extraction_metadata(mock_client):
    prompt = Prompt.get(
        "creator.primitive-plan",
        vars={
            "scenario": "A photographer directs a model during a studio session.",
            "characters": ["Model", "Photographer"],
            "max_tokens": 4096,
        },
    )
    prompt.client = mock_client

    rendered = prompt.render()

    assert "photographer directs a model" in rendered
    assert "Model, Photographer" in rendered
    assert all(
        field in rendered
        for field in (
            "needed",
            "rationale",
            "anchors",
            "systems",
            "prompt_visible",
            "hidden",
            "warnings",
        )
    )
    assert "Every field above must be present." in rendered
    assert "all five list fields as empty lists" in rendered
    assert "advisory" in rendered.lower()
    assert "<PRIMITIVE_PLAN>" in rendered
    extractor = prompt._template_extractors["response"]
    assert extractor.left == "<PRIMITIVE_PLAN>"
    assert extractor.right == "</PRIMITIVE_PLAN>"
    assert extractor.parse_data is True


def test_primitive_plan_renders_yaml_example(mock_client):
    mock_client.data_format = "yaml"

    prompt = Prompt.get(
        "creator.primitive-plan",
        vars={"scenario": "A quiet conversation.", "characters": []},
    )
    prompt.client = mock_client
    rendered = prompt.render()

    assert "```yaml" in rendered
    assert "needed: true" in rendered


def test_primitive_authoring_renders_context_rules_and_callback_instructions(
    mock_client,
):
    callback_names = (
        "create_anchor",
        "create_meter",
        "create_clock",
        "create_deck",
        "create_roll_table",
        "create_relationship_model",
        "create_modifier",
        "create_attribute_source",
    )
    focal = Mock()
    focal.render_instructions.return_value = "FOCAL CALLBACK PROTOCOL"
    for name in callback_names:
        getattr(focal.callbacks, name).render.return_value = f"CALLBACK {name}"

    prompt = Prompt.get(
        "creator.primitive-authoring",
        vars={
            "scenario": "A photographer directs a model during a studio session.",
            "characters": ["Model", "Photographer"],
            "plan": {
                "needed": True,
                "systems": [{"kind": "deck", "id": "pose_deck"}],
            },
            "safety_rules": [
                "Do not expose private mechanics.",
                "Do not create visual-generation primitives.",
                "Do not put mechanics into character base attributes.",
            ],
            "focal": focal,
        },
    )
    prompt.client = mock_client
    rendered = prompt.render()

    assert "photographer directs a model" in rendered
    assert "Model, Photographer" in rendered
    assert '"pose_deck"' in rendered
    assert "Do not expose private mechanics." in rendered
    assert "FOCAL CALLBACK PROTOCOL" in rendered
    assert "Prefer generic systems over genre-specific hardcoding." in rendered
    assert "Do not create visual-generation primitives." in rendered
    assert "Do not put mechanics into character base attributes." in rendered
    assert "prompt-visible context prose-like" in rendered
    assert "enough deck cards and roll-table rows" in rendered
    assert "Do not validate the draft and do not commit the draft." in rendered
    for name in callback_names:
        assert f"CALLBACK {name}" in rendered
        getattr(focal.callbacks, name).render.assert_called_once()
    focal.render_instructions.assert_called_once_with()
    focal.callbacks.validate_draft.render.assert_not_called()
    focal.callbacks.commit_draft.render.assert_not_called()
