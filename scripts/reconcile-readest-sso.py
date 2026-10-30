#!/usr/bin/env python3
"""Run inside authentik-worker with ak shell; users remain outside Git."""
from django.db import transaction
from django.core.cache import cache
from authentik.core.api.applications import user_app_cache_key
from authentik.core.models import Application, Group
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

with transaction.atomic():
    template = ProxyProvider.objects.get(name='Status Proxy')
    group, _ = Group.objects.get_or_create(name='readest-users')
    provider, _ = ProxyProvider.objects.update_or_create(name='Readest Proxy', defaults={
        'authentication_flow': template.authentication_flow,
        'authorization_flow': template.authorization_flow,
        'invalidation_flow': template.invalidation_flow,
        'mode': 'proxy', 'external_host': 'https://readest.shelfgoblin.dev',
        'internal_host': 'http://readest-gateway:8080',
        'skip_path_regex': '', 'basic_auth_enabled': False,
    })
    provider.set_oauth_defaults()
    provider.save()
    app, _ = Application.objects.update_or_create(slug='readest', defaults={
        'name': 'Readest', 'provider': provider, 'group': 'Media',
        'meta_launch_url': 'https://readest.shelfgoblin.dev/sso',
        'meta_icon': 'fa://fa-book-open', 'meta_hide': False, 'policy_engine_mode': 'all',
    })
    PolicyBinding.objects.update_or_create(target=app, order=0, defaults={
        'group': group, 'policy': None, 'user': None, 'enabled': True,
        'negate': False, 'failure_result': False,
    })
    Outpost.objects.get(name='authentik Embedded Outpost').providers.add(provider)

for user in group.users.all():
    cache.delete_many([user_app_cache_key(user.pk, page, launch)
                       for page in [None, *range(1, Application.objects.count() + 2)]
                       for launch in (False, True)])
print('Readest proxy and restricted portal tile reconciled.')
