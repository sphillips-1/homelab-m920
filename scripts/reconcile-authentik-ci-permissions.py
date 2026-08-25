#!/usr/bin/env python3
"""Idempotently reconcile the scoped Terraform CI role permissions."""

from django.db import transaction

from authentik.core.models import User
from authentik.rbac.models import Role


USERNAME = "terraform-github-actions"
ROLE_NAME = "Terraform GitHub Actions Blueprint Manager"
PERMISSIONS = {
    "authentik_blueprints.add_blueprintinstance",
    "authentik_blueprints.change_blueprintinstance",
    "authentik_blueprints.view_blueprintinstance",
    "authentik_flows.add_flowstagebinding",
    "authentik_flows.change_flowstagebinding",
    "authentik_flows.view_flow",
    "authentik_flows.view_flowstagebinding",
    "authentik_stages_identification.add_identificationstage",
    "authentik_stages_identification.change_identificationstage",
    "authentik_stages_identification.view_identificationstage",
}


with transaction.atomic():
    user = User.objects.get(username=USERNAME)
    role = Role.objects.get(name=ROLE_NAME)
    role.assign_perms(sorted(PERMISSIONS))
    user.roles.add(role)

print("Terraform CI role permissions are reconciled.")
