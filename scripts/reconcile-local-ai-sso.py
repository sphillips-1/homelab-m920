#!/usr/bin/env python3
"""Run in authentik-worker; credential-bearing stdout must be captured privately."""
import json
from django.db import transaction
from authentik.core.models import Application, Group
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.policies.expression.models import ExpressionPolicy
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping, RedirectURI
from authentik.providers.proxy.models import ProxyProvider

with transaction.atomic():
    group, created = Group.objects.get_or_create(name="ai-users")
    if created:
        # The existing Bambu trial has exactly one Google-linked owner/admin.
        # Bootstrap once; later membership changes remain administrator-managed.
        owners = [user for user in Group.objects.get(name="bambu-users").users.filter(
            is_active=True, sources__slug="google").distinct() if user.is_superuser]
        if len(owners) != 1:
            raise RuntimeError("Expected exactly one existing Google-linked Bambu owner/admin.")
        group.users.add(owners[0])
    identity, _ = ExpressionPolicy.objects.update_or_create(
        name="local-ai-verified-google", defaults={"expression":
            'return bool(request.user.email) and request.user.sources.filter(slug="google").exists()'})
    template = OAuth2Provider.objects.get(name="Audiobookshelf OIDC")
    provider, _ = OAuth2Provider.objects.update_or_create(name="Local AI OIDC", defaults={
        "authentication_flow": template.authentication_flow,
        "authorization_flow": template.authorization_flow,
        "invalidation_flow": template.invalidation_flow,
        "client_type": "confidential", "grant_types": ["authorization_code"],
        "signing_key": template.signing_key, "include_claims_in_id_token": True,
        "access_code_validity": "minutes=1", "access_token_validity": "minutes=5",
    })
    assert provider.client_id and provider.client_secret and provider.signing_key
    provider.redirect_uris = [RedirectURI(matching_mode="strict",
        url="https://ai.shelfgoblin.dev/oauth/oidc/callback", redirect_uri_type="authorization")]
    provider.save()
    email, _ = ScopeMapping.objects.update_or_create(name="Local AI verified email", defaults={
        "scope_name": "email", "expression":
        'return {"email": request.user.email, "email_verified": request.user.sources.filter(slug="google").exists()}'})
    provider.property_mappings.set([email, *[ScopeMapping.objects.get(
        managed=f"goauthentik.io/providers/oauth2/scope-{scope}") for scope in ("openid", "profile")]])
    oidc, _ = Application.objects.update_or_create(slug="local-ai-oidc", defaults={
        "name": "Local AI OIDC", "provider": provider, "meta_hide": True,
        "meta_launch_url": "https://ai.shelfgoblin.dev", "policy_engine_mode": "all"})
    proxy_template = ProxyProvider.objects.get(name="Status Proxy")
    proxy, _ = ProxyProvider.objects.update_or_create(name="Local AI Proxy", defaults={
        "authentication_flow": proxy_template.authentication_flow,
        "authorization_flow": proxy_template.authorization_flow,
        "invalidation_flow": proxy_template.invalidation_flow,
        "mode": "proxy", "external_host": "https://ai.shelfgoblin.dev",
        "internal_host": "http://local-ai-webui:8080", "skip_path_regex": "",
        "basic_auth_enabled": False,
    })
    proxy.set_oauth_defaults()
    proxy.save()
    app, _ = Application.objects.update_or_create(slug="local-ai", defaults={
        "name": "Local Coding AI", "provider": proxy, "group": "Administration",
        "meta_launch_url": "https://ai.shelfgoblin.dev", "meta_icon": "fa://fa-code",
        "meta_hide": False, "policy_engine_mode": "all"})
    for application in (app, oidc):
        for order, values in enumerate(({"group": group, "policy": None},
                                      {"group": None, "policy": identity})):
            PolicyBinding.objects.update_or_create(target=application, order=order, defaults={
                **values, "user": None, "enabled": True, "negate": False,
                "failure_result": False, "timeout": 30})
    Outpost.objects.get(name="authentik Embedded Outpost").providers.add(proxy)

print("LOCAL_AI_OIDC=" + json.dumps({"OAUTH_CLIENT_ID": provider.client_id,
                                    "OAUTH_CLIENT_SECRET": provider.client_secret}))
