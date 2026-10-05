#!/usr/bin/env python3
"""Run inside authentik-worker using ak shell."""
from django.db import transaction
from authentik.core.models import Application, Group
from authentik.outposts.models import Outpost
from authentik.policies.models import PolicyBinding
from authentik.providers.proxy.models import ProxyProvider

with transaction.atomic():
    template = ProxyProvider.objects.get(name='Status Proxy')
    group, _ = Group.objects.get_or_create(name='torrent-users')
    provider, _ = ProxyProvider.objects.update_or_create(
        name='qBittorrent Proxy', defaults={
            'authentication_flow': template.authentication_flow,
            'authorization_flow': template.authorization_flow,
            'invalidation_flow': template.invalidation_flow,
            'mode': 'forward_single',
            'external_host': 'https://torrents.shelfgoblin.dev',
            'internal_host': 'http://m920-qbittorrent:8091',
            'skip_path_regex': '',
            'basic_auth_enabled': False,
        })
    provider.property_mappings.set(template.property_mappings.all())
    app, _ = Application.objects.update_or_create(slug='qbittorrent', defaults={
        'name': 'qBittorrent', 'provider': provider, 'group': 'Administration',
        'meta_launch_url': 'https://torrents.shelfgoblin.dev',
        'meta_icon': 'fa://fa-download', 'meta_hide': False,
        'policy_engine_mode': 'all',
    })
    PolicyBinding.objects.update_or_create(target=app, order=0, defaults={
        'group': group, 'policy': None, 'user': None, 'enabled': True,
        'negate': False, 'failure_result': False,
    })
    Outpost.objects.get(name='authentik Embedded Outpost').providers.add(provider)
print('qBittorrent SSO and restricted portal tile reconciled; grant torrent-users explicitly.')
