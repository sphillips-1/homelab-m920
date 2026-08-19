#!/usr/bin/env python3
"""Run through `ak shell` and redirect stdout to a private Compose env file."""

import json

from authentik.policies.expression.models import ExpressionPolicy
from authentik.providers.oauth2.models import OAuth2Provider
from authentik.sources.oauth.models import OAuthSource


def emit(name: str, value: str) -> None:
    # JSON string syntax is accepted by Docker Compose's dotenv parser and
    # safely represents quotes, newlines, and backslashes.
    print(f"{name}={json.dumps(str(value))}")


oidc = OAuth2Provider.objects.get(name="Audiobookshelf OIDC")
google = OAuthSource.objects.get(slug="google")
allowlist = ExpressionPolicy.objects.get(name="google-email-allowlist")

emit("AUTHENTIK_AUDIOBOOKSHELF_CLIENT_SECRET", oidc.client_secret)
emit("AUTHENTIK_GOOGLE_CLIENT_ID", google.consumer_key)
emit("AUTHENTIK_GOOGLE_CLIENT_SECRET", google.consumer_secret)
emit("AUTHENTIK_GOOGLE_EMAIL_ALLOWLIST_EXPRESSION", allowlist.expression)
