#!/usr/bin/env python3
"""Run via configure-beszel-sso.py inside authentik-worker using ak shell.

Stdout contains a credential-bearing marker; callers must capture it, never log it.
"""
import json

from django.db import transaction
from authentik.core.models import Application, Group
from authentik.policies.models import PolicyBinding
from authentik.policies.expression.models import ExpressionPolicy
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping, RedirectURI

with transaction.atomic():
    template = OAuth2Provider.objects.get(name="Audiobookshelf OIDC")
    group = Group.objects.get(name="status-users")
    email, _ = ScopeMapping.objects.update_or_create(
        name="Beszel verified Google email",
        defaults={
            "scope_name": "email",
            "description": "Verified Google identity for Beszel account matching",
            "expression": 'return {"email": request.user.email, "email_verified": request.user.sources.filter(slug="google").exists()}',
        },
    )
    identity, _ = ExpressionPolicy.objects.update_or_create(
        name="beszel-google-identity",
        defaults={"expression": 'return bool(request.user.email) and request.user.sources.filter(slug="google").exists()'},
    )
    provider, _ = OAuth2Provider.objects.update_or_create(
        name="Beszel OIDC",
        defaults={
            "authentication_flow": template.authentication_flow,
            "authorization_flow": template.authorization_flow,
            "invalidation_flow": template.invalidation_flow,
            "client_type": "confidential",
            "grant_types": ["authorization_code"],
            "signing_key": template.signing_key,
            "access_code_validity": "minutes=1",
            "access_token_validity": "minutes=5",
            "include_claims_in_id_token": True,
        },
    )
    # Defaults generate the client credentials only on creation; redeploys retain them.
    if not provider.client_id or not provider.client_secret or not provider.signing_key:
        raise RuntimeError("Beszel OIDC requires client credentials and the existing signing key.")
    provider.redirect_uris = [RedirectURI(
        matching_mode="strict",
        url="https://status.shelfgoblin.dev/api/oauth2-redirect",
        redirect_uri_type="authorization",
    )]
    provider.save()
    scopes = [ScopeMapping.objects.get(managed=f"goauthentik.io/providers/oauth2/scope-{scope}")
              for scope in ("openid", "profile")]
    provider.property_mappings.set([*scopes, email])
    app, _ = Application.objects.update_or_create(
        slug="beszel",
        defaults={
            "name": "Beszel", "provider": provider, "group": "Administration",
            "meta_launch_url": "https://status.shelfgoblin.dev/",
            # The existing Status proxy application owns the visible portal tile.
            "meta_hide": True, "policy_engine_mode": "all",
        },
    )
    for order, binding in enumerate(({"group": group, "policy": None}, {"group": None, "policy": identity})):
        PolicyBinding.objects.update_or_create(
            target=app, order=order,
            defaults={**binding, "user": None, "enabled": True,
                      "negate": False, "failure_result": False, "timeout": 30},
        )

print("BESZEL_OIDC_CONFIG=" + json.dumps({
    "clientId": provider.client_id, "clientSecret": provider.client_secret,
}))
