#!/usr/bin/env python3
"""Run inside authentik-worker using ak shell. Membership is managed separately."""
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.db import transaction
from authentik.core.models import Application, Group
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

with transaction.atomic():
    template = ProxyProvider.objects.get(name='Status Proxy')
    group, _ = Group.objects.get_or_create(name='holyarrs-users')
    provider, _ = ProxyProvider.objects.update_or_create(name='HolyArrs Public Proxy', defaults={
        'authentication_flow': template.authentication_flow,
        'authorization_flow': template.authorization_flow,
        'invalidation_flow': template.invalidation_flow,
        'mode': 'proxy', 'external_host': 'https://holyarrs.shelfgoblin.dev',
        'internal_host': 'http://holyarrs:6262',
        'skip_path_regex': '', 'basic_auth_enabled': False,
    })
    provider.set_oauth_defaults()
    provider.save()
    app, _ = Application.objects.update_or_create(slug='holyarrs-public', defaults={
        'name': 'HolyArrs Public', 'provider': provider, 'group': 'Administration',
        'meta_launch_url': 'https://bambu.shelfgoblin.dev',
        'meta_icon': 'fa://fa-film', 'meta_hide': True, 'policy_engine_mode': 'all',
    })
    PolicyBinding.objects.update_or_create(target=app, order=0, defaults={
        'group': group, 'policy': None, 'user': None, 'enabled': True,
        'negate': False, 'failure_result': False,
    })
    Outpost.objects.get(name='authentik Embedded Outpost').providers.add(provider)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


# The embedded outpost reloads providers asynchronously. Verify it is enforcing
# SSO on both browser and API requests before deployment restarts the tunnel.
opener = build_opener(NoRedirect)
deadline = monotonic() + 60
for path in ('/', '/api/v1/auth/oidc/callback'):
    request = Request(f'http://authentik-server:9000{path}', headers={
        'Host': 'holyarrs.shelfgoblin.dev', 'X-Forwarded-Proto': 'https',
    })
    while True:
        try:
            with opener.open(request, timeout=5):
                pass
        except HTTPError as error:
            if error.code in (302, 303) and '/outpost.goauthentik.io/' in error.headers.get('Location', ''):
                break
        except URLError:
            pass
        if monotonic() >= deadline:
            raise RuntimeError(f'HolyArrs public SSO did not gate {path}')
        sleep(2)

print('HolyArrs public proxy reconciled and anonymous SSO redirects verified.')
