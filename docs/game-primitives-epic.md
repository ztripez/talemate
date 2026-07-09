# Epic: Game Primitives runtime, authoring, and adventure structure

## Summary

Introduce **Game Primitives** as a deterministic, attachable systems layer for Talemate.

Talemate currently treats `Scene` as the main runtime/save container and relies heavily on LLM-generated text for state, variation, relationships, and story structure. This epic adds a reusable primitive runtime so scenario authors and LLM-assisted scenario creation can define systems such as decks, roll tables, meters, clocks, relationships, modifiers, primitive attributes, objects, and adventure/story-scene transitions.

The goal is not to hardcode a genre. The goal is to provide generic authoring/runtime tools that can be attached to any context/anchor:

- `scene:main`
- `story_scene:warmup`
- `character:Model`
- `object:HasselbladCamera`
- `relationship:Model->Photographer`
- `location:studio`
- `project:studio-session`

## Design principles

- **Runtime state stays out of character prose.** Mechanical primitive state must not leak into `Character.base_attributes`, character sheets, or memory unless explicitly rendered or committed.
- **LLMs author and narrate, but do not own deterministic state.** Scenario creation may create primitive drafts through validated tools; runtime resolution remains deterministic and inspectable.
- **All primitives attach to anchors.** A meter, deck, table, clock, modifier, relationship, object, or adventure scene is addressed through an anchor.
- **Definitions and runtime state are separate.** Deck/table/meter definitions are reusable; draw piles, current values, cooldowns, and transition history are runtime state.
- **Prompt visibility is explicit.** Primitives have render policies such as `hidden`, `prompt`, `summary`, and `memory`.
- **Node modules orchestrate; Python runtime resolves.** Node modules should call a tested primitive runtime rather than reimplementing deterministic logic in graphs.

## Proposed MVP storage

MVP storage should live under:

```python
scene.game_state.variables["game_primitives"]
```

This avoids early scene schema migrations while preserving save/load compatibility.

Longer term, once the runtime stabilizes, this can graduate into a typed scene field or first-class subsystem.

## Non-goals

- Visual generation or visual style control.
- Full polished UI for every primitive type.
- Genre-specific content packs as required implementation.
- Replacing Talemate `Scene` as the runtime/save container.
- Storing primitive mechanics as ordinary character base attributes.

## Runtime shape

```text
Game Primitives
  definitions
    decks
    roll_tables
    meters
    clocks
    relationship_models
    modifiers
    attribute_sources
    adventures
  anchors
    scene:main
    character:<name>
    object:<id>
    relationship:<source>-><target>
    location:<id>
    story_scene:<id>
    project:<id>
  runtime
    deck_piles
    meter_values
    clock_values
    relationship_edges
    active_modifiers
    current_story_scene
    transition_log
  ledger
    deterministic debug/audit events
```

## Ladder

### Rung 0 — Core import seam

**Goal:** Make it possible to register Game Primitives Python nodes/runtime.

Required work:

- Add `src/talemate/game/primitives/` package.
- Add `src/talemate/game/engine/nodes/primitives/` package.
- Import primitive nodes during node bootstrap so `@register(...)` runs.
- Add minimal smoke test that primitive node registries are available.

Acceptance criteria:

- `primitives/*` Python node classes can be discovered by the node registry.
- No behavior changes when no primitive package is installed.

### Rung 1 — Primitive store, anchors, refs, and ledger

**Goal:** Create the storage and addressing foundation.

Required work:

- Implement `PrimitiveStore` around `scene.game_state.variables["game_primitives"]`.
- Implement `AnchorRef` and `PrimitiveRef` parsing/formatting.
- Support anchor kinds: `scene`, `character`, `object`, `relationship`, `location`, `story_scene`, `project`.
- Implement basic ledger entries for deterministic operations.
- Add runtime validation and migration hook for missing/default store shape.

Acceptance criteria:

- Primitive state persists across save/load through `game_state`.
- Invalid refs produce clear validation errors.
- Ledger can record and read recent primitive operations.

### Rung 2 — Effects and primitive-aware conditions

**Goal:** Provide deterministic mutation and selection predicates.

Required work:

- Implement effects: `set`, `unset`, `inc`, `dec`, `add_tag`, `remove_tag`, `append`, `apply_effects`.
- Implement primitive-aware conditions for:
  - state path comparisons
  - primitive path comparisons
  - anchor tags
  - meter values
  - clock completion
  - relationship dimensions
- Reuse existing condition operator semantics where possible.
- Add debug output explaining why a condition matched or failed.

Acceptance criteria:

- Effects are deterministic and validated before mutation.
- Conditions can be used by future decks/tables/transitions.
- Failed condition/effect paths do not silently corrupt state.

### Rung 3 — Roll tables and selection results

**Goal:** Add stateless/lightly stateful authored probability tables.

Required work:

- Implement common `SelectionResult` model.
- Implement roll table definitions:
  - dice expressions, e.g. `1d6`, `2d6`, `1d100`
  - range rows
  - weighted rows
  - row effects
  - row tags/metadata
- Implement modifiers for roll totals.
- Implement odds preview for simple dice/range and weighted tables.
- Add node wrappers:
  - `RollTable.Roll`
  - `RollTable.PreviewOdds`
  - `Selection.ApplyEffects`

Acceptance criteria:

- Roll result includes raw roll, modifiers, final result, row id, row label, effects, and debug trace.
- Results can optionally apply effects through the common effect engine.
- Roll tables can be anchored to any supported anchor.

### Rung 4 — Decks

**Goal:** Add deterministic/stateful authored variation sources.

Required work:

- Implement deck definitions with cards, tags, weights, variables, prompt text, and effects.
- Implement deck modes:
  - `sample`
  - `draw`
  - `bag`
  - `physical`
- Implement runtime state:
  - draw pile
  - discard pile
  - recent cards
  - cooldowns
  - seed/shuffle state
- Add filters:
  - include/exclude tags
  - avoid recent
  - condition-based card availability
- Add node wrappers:
  - `Deck.Draw`
  - `Deck.Peek`
  - `Deck.Shuffle`
  - `Deck.Reset`

Acceptance criteria:

- Deck draws are reproducible through persisted runtime state.
- Physical decks can be treated as object-attached primitives.
- Decks can be used for both authoring variation and in-story objects.

### Rung 5 — Relationship graph

**Goal:** Make relationships a first-class primitive rather than character attributes.

Required work:

- Implement directional relationship anchors: `relationship:A->B`.
- Implement relationship dimensions as meters, e.g. `trust`, `fear`, `comfort`, `obligation`, `suspicion`.
- Implement relationship modifiers and summaries.
- Add node wrappers:
  - `Relationship.Get`
  - `Relationship.Set`
  - `Relationship.Adjust`
  - `Relationship.Summary`
  - `Relationship.RenderRelevant`

Acceptance criteria:

- Alice → Bob and Bob → Alice are separate relationship states.
- Raw relationship values are hidden from prompts unless explicitly rendered.
- Prompt summaries are prose-oriented, not mechanical dumps.

### Rung 6 — Primitive attributes

**Goal:** Extend character/object/scene attributes so values can come from primitives instead of always being generated by LLM text.

Required work:

- Implement attribute source types:
  - `literal`
  - `llm`
  - `deck`
  - `roll_table`
  - `meter`
  - `clock`
  - `relationship`
  - `modifier`
  - `expression`
  - `state_ref`
- Implement render policies:
  - `hidden`
  - `prompt`
  - `summary`
  - `memory`
- Add node wrappers:
  - `Attribute.Resolve`
  - `Attribute.Get`
  - `Attribute.Set`
  - `Attribute.Render`

Acceptance criteria:

- Primitive attributes do not get written into `Character.base_attributes` by default.
- A character can have a prompt-rendered attribute whose value comes from a deck/table/meter/relationship.
- LLM-facing and system-only attributes are clearly separated.

### Rung 7 — Prompt bridge and installable node package

**Goal:** Make primitive state useful to conversation/narration without leaking mechanics.

Required work:

- Implement `Primitive.RenderRelevantContext` runtime function.
- Add prompt bridge for:
  - conversation generation
  - narrator generation
  - creator contextual generation
  - director/scene-direction context later if needed
- Add installable package under `templates/modules/game-primitives/`.
- Add listener modules:
  - inject conversation context
  - inject narrator context
  - advance/respond on new messages

Acceptance criteria:

- Installed Game Primitives package injects only rendered, relevant context.
- Raw deck piles, roll totals, hidden meters, and mechanical internals are not sent to LLM prompts.
- Package can be installed/uninstalled without breaking scenes.

### Rung 8 — LLM-facing primitive authoring tools

**Goal:** Let LLMs create primitive drafts during scenario creation and director-assisted authoring.

Required work:

- Implement authoring draft store.
- Implement authoring validation.
- Implement creation tools:
  - `CreateAnchor`
  - `CreateMeter`
  - `CreateClock`
  - `CreateDeck`
  - `CreateRollTable`
  - `CreateRelationshipModel`
  - `CreateModifier`
  - `CreateAttributeSource`
  - `ValidateDraft`
  - `CommitDraft`
- Expose authoring tools through FOCAL-compatible callbacks.
- Add DirectorChatAction node modules for primitive authoring.

Acceptance criteria:

- LLMs can propose primitives without directly mutating committed runtime state.
- Draft validation reports errors/warnings before commit.
- Committed primitive definitions are normalized and reference-checked.

### Rung 9 — Creator scenario primitive generation

**Goal:** When a user creates a new scenario, the creator can create appropriate primitives: decks, tables, modifiers, relationships, and attribute sources.

Required work:

- Add creator-side primitive planning pass.
- Add FOCAL-backed primitive bundle generation.
- Inject authoring guidance into scenario creation.
- Commit a validated primitive bundle into the new scene.
- Produce a user-readable summary of created systems.

Acceptance criteria:

- A scenario request like “photoshoot with a model” can create a pose deck, relationship meters, model confidence/stress meters, reaction roll table, and modifiers.
- The generated primitive bundle is inspectable before/after commit.
- Scenario creation remains usable if primitive generation fails; failure should degrade gracefully.

### Rung 10 — Adventure/story-scene graph

**Goal:** Add structure above the current Talemate `Scene` runtime container.

Required work:

- Implement `AdventureState` under Game Primitives.
- Implement `StorySceneDefinition` with intro, goals, local anchors, entry effects, exit effects.
- Implement `TransitionDefinition` with conditions, carry rules, entry/exit effects, and intro rendering.
- Add nodes:
  - `Adventure.GetCurrentScene`
  - `Adventure.ListTransitions`
  - `Adventure.CanTakeTransition`
  - `Adventure.TakeTransition`
  - `Adventure.RenderCurrentSceneContext`
- Store transition log in primitive ledger/runtime state.

Acceptance criteria:

- Talemate `Scene` remains the runtime/save container.
- Adventure/current story scene can transition deterministically.
- Scene messages can be tagged with current story scene via message metadata or ledger events.
- Prompt bridge can render current story-scene context and available transitions.

## Suggested first vertical slice

A good first end-to-end slice is:

```text
PrimitiveStore
  -> RollTable.Roll
  -> Effects.Apply
  -> Relationship.Adjust
  -> RenderRelevantContext
```

This proves persistence, deterministic resolution, mutation, relationship state, and prompt-safe rendering before implementing more complex decks/adventure behavior.

## Testing expectations

- Unit tests for schema parsing and validation.
- Unit tests for anchor/ref roundtrips.
- Unit tests for effect application and failed validation.
- Unit tests for condition evaluation.
- Unit tests for roll table probabilities/modifiers.
- Unit tests for deck state transitions.
- Unit tests for relationship summaries.
- Save/load regression for primitive runtime state.
- Prompt bridge tests ensuring hidden primitives are not rendered.

## Open design questions

- Should definitions live entirely under `game_state.variables`, or should reusable definitions be file-backed in `info/game-primitives/` once stable?
- Should primitive authoring require explicit user confirmation before commit, or should that be configurable per scenario-creation flow?
- Should primitive packs integrate with world-state template groups later, or remain a separate pack format?
- How much primitive status should be emitted in `scene_status` versus a separate websocket event?
