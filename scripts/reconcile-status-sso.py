#!/usr/bin/env python3

from authentik.policies.expression.models import ExpressionPolicy


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

