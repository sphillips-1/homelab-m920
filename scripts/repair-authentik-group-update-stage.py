#!/usr/bin/env python3
"""Remove one orphaned Authentik in-memory GroupUpdateStage database row."""

from django.db import transaction

from authentik.flows.models import FlowStageBinding, Stage


STAGE_NAME = "authentik.core.sources.flow_manager.GroupUpdateStage"

with transaction.atomic():
    matches = list(Stage.objects.select_for_update().filter(name=STAGE_NAME))
    if not matches:
        print("No orphaned GroupUpdateStage row found; no repair needed.")
    elif len(matches) != 1:
        raise RuntimeError(
            f"Refusing repair: expected at most one {STAGE_NAME!r} row, found {len(matches)}."
        )
    else:
        stage = matches[0]
        concrete = Stage.objects.get_subclass(stage_uuid=stage.stage_uuid)
        if concrete.__class__ is not Stage:
            raise RuntimeError(
                "Refusing repair: the matching row has concrete stage type "
                f"{concrete.__class__.__module__}.{concrete.__class__.__name__}."
            )
        if FlowStageBinding.objects.filter(stage=stage).exists():
            raise RuntimeError("Refusing repair: the matching row is bound to a flow.")
        stage.delete()
        print(f"Removed orphaned in-memory stage row {stage.stage_uuid}.")
