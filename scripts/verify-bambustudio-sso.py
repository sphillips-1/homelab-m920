#!/usr/bin/env python3
"""Run using authentik-worker ak shell; no credentials are printed or created."""
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from authentik.core.api.applications import ApplicationViewSet
from authentik.core.models import Application, Group, User
from authentik.tenants.models import Tenant
from authentik.providers.proxy.models import ProxyProvider
from rest_framework.test import APIRequestFactory, force_authenticate

group = Group.objects.get(name='bambu-users')
app = Application.objects.get(slug='bambustudio')
provider = ProxyProvider.objects.get(pk=app.provider_id)
assert provider.mode == 'proxy' and provider.skip_path_regex == ''
assert provider.internal_host == 'http://bambustudio:3000'
assert 'authorization_code' in provider.grant_types
assert any(uri.url.startswith('https://bambu.shelfgoblin.dev/outpost.goauthentik.io/callback')
           for uri in provider.redirect_uris)
view = ApplicationViewSet.as_view({'get': 'list'})
factory = APIRequestFactory()

def visible(user):
    request = factory.get('/api/v3/core/applications/', {
        'search': 'Bambu Studio', 'only_with_launch_url': 'true', 'page_size': 100,
    })
    request.tenant = Tenant.objects.first()
    force_authenticate(request, user=user)
    response = view(request)
    assert response.status_code == 200
    return any(item['slug'] == app.slug for item in response.data['results'])

approved = list(group.users.filter(is_active=True))
assert approved, 'No approved trial user'
for user in approved:
    assert visible(user), 'Approved user missing portal access'
denied = User.objects.filter(is_active=True, groups__name='books-users').exclude(groups=group).first()
assert denied and not visible(denied), 'Ordinary library user must be denied'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

for path in ('/', '/websockets'):
    request = Request('http://authentik-server:9000' + path, headers={
        'Host': 'bambu.shelfgoblin.dev', 'X-Forwarded-Proto': 'https',
    })
    try:
        build_opener(NoRedirect).open(request, timeout=15)
        raise AssertionError('Anonymous access was not redirected')
    except HTTPError as error:
        assert error.code in (302, 303), error.code
        assert '/outpost.goauthentik.io/' in error.headers['Location']
print('Approved portal access, ordinary-user denial, and anonymous HTTP/streaming gate passed.')
