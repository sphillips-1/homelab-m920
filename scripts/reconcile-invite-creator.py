#!/usr/bin/env python3
"""Idempotently reconcile the admin-only invite creator application tile."""

from authentik.core.models import Application
from authentik.policies.expression.models import ExpressionPolicy
from authentik.policies.models import PolicyBinding


application, _ = Application.objects.update_or_create(
    slug="create-user-invite",
    defaults={
        "name": "Create user invite",
        "group": "Administration",
        "provider": None,
        "meta_launch_url": "https://auth.shelfgoblin.dev/invite/new/",
        "meta_icon": "fa://fa-user-plus",
        "meta_publisher": "Homelab",
        "meta_description": (
            "Create a 24-hour media-service invite and copy it to the clipboard."
        ),
        "meta_hide": False,
        "open_in_new_tab": False,
        "policy_engine_mode": "all",
    },
)

policy, _ = ExpressionPolicy.objects.update_or_create(
    name="require-superuser-for-invite-creator",
    defaults={"expression": "return request.user.is_superuser"},
)

PolicyBinding.objects.update_or_create(
    target=application,
    order=0,
    defaults={
        "policy": policy,
        "group": None,
        "user": None,
        "enabled": True,
        "negate": False,
        "failure_result": False,
        "timeout": 30,
    },
)

print("Invite creator application and superuser policy are reconciled.")
