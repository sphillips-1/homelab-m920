#!/usr/bin/env python3
"""Create a scoped 90-day Authentik credential for Terraform CI."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from authentik.core.models import Token, User
from authentik.rbac.models import Role


USERNAME = "terraform-github-actions"
TOKEN_IDENTIFIER = "terraform-github-actions"
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

if User.objects.filter(username=USERNAME).exists():
    raise RuntimeError(f"Refusing to replace existing user {USERNAME!r}")
if Token.objects.filter(identifier=TOKEN_IDENTIFIER).exists():
    raise RuntimeError(f"Refusing to replace existing token {TOKEN_IDENTIFIER!r}")
if Role.objects.filter(name=ROLE_NAME).exists():
    raise RuntimeError(f"Refusing to replace existing role {ROLE_NAME!r}")

with transaction.atomic():
    user = User.objects.create(
        username=USERNAME,
        name="Terraform GitHub Actions",
        type="service_account",
        path="goauthentik.io/service-accounts",
        is_active=True,
    )
    role = Role.objects.create(name=ROLE_NAME)
    role.assign_perms(sorted(PERMISSIONS))
    user.roles.add(role)

    token = Token.objects.create(
        identifier=TOKEN_IDENTIFIER,
        user=user,
        intent="api",
        expiring=True,
        expires=timezone.now() + timedelta(days=90),
        description="Scoped Terraform GitHub Actions token; rotate before expiry",
    )
print(token.key)
