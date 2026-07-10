"""Scenario primitive planning and authoring for the creator agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic

import talemate.game.focal as focal
from talemate.exceptions import TalemateError
from talemate.game.primitives.authoring.focal import PrimitiveAuthoringFocal
from talemate.game.primitives.authoring.planner import (
    PrimitiveCreationCounts,
    PrimitiveDraftReport,
    PrimitivePlanExtraction,
    PrimitiveScenarioBundleResult,
    PrimitiveScenarioPlan,
)
from talemate.game.primitives.authoring.tools import PrimitiveAuthoringService
from talemate.game.primitives.exceptions import PrimitiveError
from talemate.prompts import Prompt

if TYPE_CHECKING:
    from talemate.tale_mate import Scene


_CREATION_CALLBACKS = {
    "create_anchor",
    "create_meter",
    "create_clock",
    "create_deck",
    "create_roll_table",
    "create_relationship_model",
    "create_modifier",
    "create_attribute_source",
}


class ScenarioPrimitiveCreatorMixin:
    """Add isolated Game Primitive generation to scenario creation."""

    async def plan_primitives_for_scenario(
        self,
        *,
        description: str,
        characters: list[str] | None = None,
    ) -> PrimitiveScenarioPlan:
        """Request and strictly validate an advisory primitive plan.

        Args:
            description: Scenario premise to analyze.
            characters: Character names available to the scenario.

        Returns:
            The validated plan; no scene data is created or persisted.

        Raises:
            pydantic.ValidationError: If extracted data violates the plan schema.
            Exception: If the prompt request fails.
        """
        _, extracted = await Prompt.request(
            "creator.primitive-plan",
            self.client,
            "analyze_long",
            vars={
                "scenario": description,
                "characters": characters or [],
            },
            data_expected=True,
        )
        envelope = PrimitivePlanExtraction.model_validate(extracted, strict=True)
        return envelope.response

    async def generate_primitive_bundle_for_scenario(
        self,
        *,
        description: str,
        characters: list[str] | None = None,
        scene: "Scene | None" = None,
        auto_commit: bool = True,
    ) -> PrimitiveScenarioBundleResult:
        """Plan, author, validate, and optionally commit scenario primitives.

        Args:
            description: Scenario premise used for planning and authoring.
            characters: Character names available to generated systems.
            scene: Scene to modify. When omitted, generation uses the creator's
                attached scene and returns a failed result if neither scene exists.
            auto_commit: Whether to commit a valid draft; defaults to true. When false,
                the draft remains persisted and inspectable without modifying committed
                primitive definitions or anchors.

        Returns:
            Generation outcome. An empty plan returns success without creating a draft.
            Validation failures return ``ok=False`` with the persisted draft identifier
            and validation errors so the invalid draft remains inspectable. Planning or
            domain failures before draft creation return ``ok=False`` without a draft
            identifier.

        Raises:
            Exception: If an unexpected prompt, focal, or service failure occurs.

        Side Effects:
            Requests model output and may persist a draft in the selected scene. Valid
            drafts are committed only when ``auto_commit`` is true; otherwise they remain
            inspectable as drafts. Drafts that fail validation also remain persisted and
            inspectable without changing committed primitive definitions or anchors.
        """
        target_scene = scene or getattr(self, "scene", None)
        draft_id = None
        empty_counts = PrimitiveCreationCounts()
        try:
            if target_scene is None:
                raise PrimitiveError(
                    "A scene is required to author scenario primitives"
                )

            plan = await self.plan_primitives_for_scenario(
                description=description,
                characters=characters,
            )
            if plan.is_empty:
                return PrimitiveScenarioBundleResult(
                    ok=True,
                    summary="No scenario primitives were needed.",
                    created=empty_counts,
                )

            service = PrimitiveAuthoringService()
            draft = service.create_draft(target_scene)
            draft_id = draft.id
            callbacks = [
                callback
                for callback in PrimitiveAuthoringFocal(service).callbacks(
                    target_scene, draft.id
                )
                if callback.name in _CREATION_CALLBACKS
            ]
            focal_handler = focal.Focal(
                self.client,
                callbacks=callbacks,
                max_calls=32,
                scenario=description,
                characters=characters or [],
                plan=plan.model_dump(mode="json"),
                safety_rules=[
                    "Do not create visual-generation primitives.",
                    "Do not put mechanics into character base attributes.",
                ],
                draft_id=draft.id,
                scene=target_scene,
            )
            await focal_handler.request("creator.primitive-authoring")

            call_errors = [
                f"{call.name}: {call.error}"
                for call in focal_handler.state.calls
                if call.error
            ]
            validated = service.validate_draft(target_scene, draft.id)
            warnings = list(validated.validation.warnings)
            errors = [*call_errors, *validated.validation.errors]
            valid = validated.validation.ok and not call_errors
            committed = False
            if valid and auto_commit:
                service.commit_draft(target_scene, draft.id)
                committed = True
            report = PrimitiveDraftReport.from_draft(validated, committed=committed)

            return PrimitiveScenarioBundleResult(
                ok=valid,
                draft_id=draft.id,
                committed=committed,
                summary=report.summary,
                created=report.created,
                warnings=warnings,
                errors=errors,
            )
        except (pydantic.ValidationError, TalemateError, PrimitiveError) as exc:
            return PrimitiveScenarioBundleResult(
                ok=False,
                draft_id=draft_id,
                summary="Scenario primitive generation failed.",
                created=empty_counts,
                errors=[str(exc)],
            )


__all__ = ["ScenarioPrimitiveCreatorMixin"]
