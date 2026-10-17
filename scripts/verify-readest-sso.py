#!/usr/bin/env python3
"""Run through authentik-worker ak shell to verify portal authorization."""
from authentik.core.api.applications import ApplicationViewSet
from authentik.core.models import Application, Group, User
from authentik.providers.proxy.models import ProxyProvider
from authentik.tenants.models import Tenant
from rest_framework.test import APIRequestFactory, force_authenticate

provider = ProxyProvider.objects.get(name='Readest Proxy')
assert provider.mode == 'proxy'
assert provider.internal_host == 'http://readest-gateway:8080'
assert 'authorization_code' in provider.grant_types
assert any(uri.url.startswith('https://readest.shelfgoblin.dev/outpost.goauthentik.io/callback')
           for uri in provider.redirect_uris)
group = Group.objects.get(name='readest-users')
assert group.users.filter(is_active=True).exists()
view = ApplicationViewSet.as_view({'get': 'list'})


def visible(user):
    request = APIRequestFactory().get('/api/v3/core/applications/',
                                     {'search': 'Readest', 'only_with_launch_url': 'true'})
    request.tenant = Tenant.objects.first()
    force_authenticate(request, user=user)
    response = view(request)
    assert response.status_code == 200
    return any(item['slug'] == 'readest' for item in response.data['results'])


for user in group.users.filter(is_active=True):
    assert visible(user), 'Approved identity cannot see Readest'
denied = next((user for user in User.objects.filter(is_active=True, groups__name='books-users').exclude(groups=group)
               if not user.is_superuser), None)
assert denied is not None, 'No unapproved identity available for verification'
assert not visible(denied), 'Unapproved identity can see Readest'
print('Readest callback, approved portal visibility, and unapproved identity denial verified.')
