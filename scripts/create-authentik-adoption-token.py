#!/usr/bin/env python3
"""Create one four-hour Authentik API token for Terraform adoption."""

import json
from datetime import timedelta

from django.utils import timezone

from authentik.core.models import Token, User


IDENTIFIER = "terraform-adoption"

if Token.objects.filter(identifier=IDENTIFIER).exists():
    raise RuntimeError(f"Refusing to replace existing token {IDENTIFIER!r}")

token = Token.objects.create(
    identifier=IDENTIFIER,
    user=User.objects.get(username="akadmin"),
    intent="api",
    expiring=True,
    expires=timezone.now() + timedelta(hours=4),
    description="Short-lived Terraform adoption token",
)
print(f"AUTHENTIK_TOKEN={json.dumps(token.key)}")
