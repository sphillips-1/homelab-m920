#!/usr/bin/env python3
"""Run inside authentik-worker using ak shell to verify the SSO integration."""
from authentik.core.api.applications import ApplicationViewSet
from authentik.core.models import Application, Group, User
from authentik.providers.proxy.models import ProxyProvider
from authentik.tenants.models import Tenant
from rest_framework.test import APIRequestFactory, force_authenticate

provider = ProxyProvider.objects.get(name='qBittorrent Proxy')
expected = ('https://torrents.shelfgoblin.dev/outpost.goauthentik.io/callback'
            '?X-authentik-auth-callback=true')
assert any(uri.url == expected for uri in provider.redirect_uris), provider.redirect_uris
assert 'authorization_code' in provider.grant_types
assert provider.mode == 'forward_single'
app = Application.objects.get(slug='qbittorrent')
assert app.provider_id == provider.pk and not app.meta_hide
group = Group.objects.get(name='torrent-users')
factory = APIRequestFactory()
view = ApplicationViewSet.as_view({'get': 'list'})

def portal_contains(user, search, slug='qbittorrent'):
    request = factory.get('/api/v3/core/applications/', {
        'search': search, 'only_with_launch_url': 'true', 'page_size': 100,
    })
    request.tenant = Tenant.objects.first()
    force_authenticate(request, user=user)
    response = view(request)
    assert response.status_code == 200, response.data
    return any(item['slug'] == slug for item in response.data['results'])

for user in group.users.filter(is_active=True):
    assert portal_contains(user, 'qBittorrent'), 'Uncached portal omitted tile'
    assert portal_contains(user, ''), 'Cached portal omitted tile'
    assert portal_contains(user, 'Import audiobooks', 'audiobook-imports'), 'Import tile missing'
    assert portal_contains(user, '', 'audiobook-imports'), 'Cached import tile missing'
# Ordinary approved library users still have no torrent access.
denied = User.objects.filter(is_active=True, groups__name='books-users').exclude(
    groups=group).first()
if denied:
    assert not portal_contains(denied, 'qBittorrent'), 'Unapproved user saw tile'
    assert not portal_contains(denied, 'Import audiobooks', 'audiobook-imports'), 'Import tile exposed'
print('OAuth callback and grant type valid; approved portal tile visible; unapproved user denied.')
