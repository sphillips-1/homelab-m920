#!/usr/bin/env python3

from authentik.core.models import Application, Group
from authentik.policies.models import PolicyBinding
from authentik.policies.expression.models import ExpressionPolicy
from authentik.providers.proxy.models import ProxyProvider


POLICY_NAME = "provision-application-invitation"
OLD_BLOCK = '''groups = list(Group.objects.filter(name__in=["audiobooks-users", "books-users"]))
if len(groups) != 2:'''
NEW_BLOCK = '''access_group_names = ["audiobooks-users", "books-users", "status-users"]
groups = list(Group.objects.filter(name__in=access_group_names))
if len(groups) != len(access_group_names):'''


policy = ExpressionPolicy.objects.get(name=POLICY_NAME)

if NEW_BLOCK in policy.expression:
    print(f"Authentik policy '{POLICY_NAME}' already grants Status access.")
elif OLD_BLOCK in policy.expression:
    policy.expression = policy.expression.replace(OLD_BLOCK, NEW_BLOCK, 1)
    policy.full_clean()
    policy.save(update_fields=["expression"])
    print(f"Authentik policy '{POLICY_NAME}' now grants Status access.")
else:
    raise RuntimeError(
        f"Authentik policy '{POLICY_NAME}' does not contain the expected group block; "
        "refusing to rewrite it."
    )

provider = ProxyProvider.objects.get(name="Status Proxy")
desired_internal_host = "http://status-gateway:8080"
if provider.internal_host != desired_internal_host:
    provider.internal_host = desired_internal_host
    # This adopted provider contains legacy blank optional fields that current
    # Authentik rejects during full-model validation. Update only the routed
    # host so unrelated provider state remains untouched.
    provider.save(update_fields=["internal_host"])
    print(f"Authentik provider 'Status Proxy' now routes through {desired_internal_host}.")
else:
    print(f"Authentik provider 'Status Proxy' already routes through {desired_internal_host}.")

listeners, _ = Application.objects.update_or_create(
    slug="top-listeners",
    defaults={
        "name": "Top listeners",
        "group": "Media",
        "provider": None,
        "meta_launch_url": "https://status.shelfgoblin.dev/top-users/",
        "meta_icon": "fa://fa-headphones",
        "meta_publisher": "Homelab",
        "meta_description": "Audiobookshelf listening hours during the last seven days.",
        "meta_hide": False,
        "open_in_new_tab": False,
        "policy_engine_mode": "all",
    },
)

PolicyBinding.objects.update_or_create(
    target=listeners,
    order=0,
    defaults={
        "policy": None,
        "group": Group.objects.get(name="status-users"),
        "user": None,
        "enabled": True,
        "negate": False,
        "failure_result": False,
        "timeout": 30,
    },
)

print("Authentik 'Top listeners' application tile is reconciled.")
