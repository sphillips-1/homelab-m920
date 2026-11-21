"""Reconcile HolyArrs as an administrator-only Authentik OIDC application."""

from django.db import transaction
from authentik.core.models import Application
from authentik.policies.expression.models import ExpressionPolicy
from authentik.policies.models import PolicyBinding
from authentik.providers.oauth2.models import OAuth2Provider, RedirectURI, ScopeMapping


with transaction.atomic():
    template = OAuth2Provider.objects.get(name="Audiobookshelf OIDC")
    if not template.signing_key:
        raise RuntimeError("Expected an asymmetric signing key on Audiobookshelf OIDC.")
    provider, _ = OAuth2Provider.objects.update_or_create(
        name="HolyArrs OIDC",
        defaults={
            "authentication_flow": template.authentication_flow,
            "authorization_flow": template.authorization_flow,
            "invalidation_flow": template.invalidation_flow,
            "client_type": "public",
            "client_id": "holyarrs-lan",
            "grant_types": ["authorization_code"],
            "signing_key": template.signing_key,
            "include_claims_in_id_token": True,
            "access_code_validity": "minutes=1",
            "access_token_validity": "minutes=5",
        },
    )
    provider.redirect_uris = [
        RedirectURI(
            matching_mode="strict",
            url="https://holyarrs.shelfgoblin.dev/api/v1/auth/oidc/callback",
            redirect_uri_type="authorization",
        )
    ]
    provider.save()
    provider.property_mappings.set(ScopeMapping.objects.filter(
        managed__in=[f"goauthentik.io/providers/oauth2/scope-{scope}"
                     for scope in ("openid", "profile", "email")]
    ))
    app, _ = Application.objects.update_or_create(
        slug="holyarrs",
        defaults={
            "name": "HolyArrs", "provider": provider, "meta_hide": True,
            "meta_launch_url": "https://holyarrs.shelfgoblin.dev",
            "policy_engine_mode": "all",
        },
    )
    policy, _ = ExpressionPolicy.objects.update_or_create(
        name="holyarrs-administrator",
        defaults={"expression": "return bool(request.user.is_active and request.user.is_superuser)"},
    )
    PolicyBinding.objects.update_or_create(
        target=app, order=0,
        defaults={"policy": policy, "user": None, "group": None, "enabled": True,
                  "negate": False, "failure_result": False, "timeout": 30},
    )
print("HolyArrs Authentik application reconciled.")
