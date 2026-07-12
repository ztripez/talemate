export const editorMetadata = Object.freeze({
    definition_kinds: ['decks', 'roll_tables', 'meters', 'clocks', 'relationship_models', 'modifiers', 'attribute_sources', 'adventures'],
    editable_definition_kinds: ['decks', 'roll_tables', 'meters', 'clocks', 'modifiers', 'adventures'],
    primitive_kinds: ['meters', 'clocks', 'decks', 'roll_tables', 'attributes', 'modifiers'],
    editable_primitive_kinds: ['meters', 'clocks', 'decks', 'roll_tables', 'attributes', 'modifiers'],
    definition_editor_kinds: ['decks', 'roll_tables', 'meters', 'clocks', 'modifiers'],
    primitive_editor_kinds: ['meters', 'clocks', 'decks', 'roll_tables', 'attributes'],
    anchor_kinds: ['scene', 'character', 'object', 'relationship', 'location', 'story_scene', 'project'],
    condition_kinds: ['path', 'primitive', 'anchor_has_tag', 'anchor_missing_tag', 'meter', 'clock_complete', 'relationship', 'always', 'never'],
    effect_kinds: ['set', 'unset', 'inc', 'dec', 'add_tag', 'remove_tag', 'append', 'extend'],
    render_policies: ['hidden', 'prompt', 'summary', 'memory'],
});
