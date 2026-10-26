#!/usr/bin/env python3
"""Run inside authentik-worker using ak shell. Membership is managed separately."""
from django.db import transaction
from authentik.core.models import Application, Group
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

with transaction.atomic():
    template = ProxyProvider.objects.get(name='Status Proxy')
    group, _ = Group.objects.get_or_create(name='bambu-users')
    provider, _ = ProxyProvider.objects.update_or_create(name='Bambu Studio Proxy', defaults={
        'authentication_flow': template.authentication_flow,
        'authorization_flow': template.authorization_flow,
        'invalidation_flow': template.invalidation_flow,
        'mode': 'proxy', 'external_host': 'https://bambu.shelfgoblin.dev',
        'internal_host': 'http://bambustudio:3000',
        'skip_path_regex': '', 'basic_auth_enabled': False,
    })
    provider.set_oauth_defaults()
    provider.save()
    app, _ = Application.objects.update_or_create(slug='bambustudio', defaults={
        'name': 'Bambu Studio', 'provider': provider, 'group': 'Administration',
        'meta_launch_url': 'https://bambu.shelfgoblin.dev',
        'meta_icon': 'fa://fa-cube', 'meta_hide': False, 'policy_engine_mode': 'all',
    })
    PolicyBinding.objects.update_or_create(target=app, order=0, defaults={
        'group': group, 'policy': None, 'user': None, 'enabled': True,
        'negate': False, 'failure_result': False,
    })
    Outpost.objects.get(name='authentik Embedded Outpost').providers.add(provider)
print('Bambu Studio restricted proxy reconciled; grant bambu-users explicitly.')
