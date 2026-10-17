#!/usr/bin/env python3
"""Run via ak shell with READEST_ALLOWED_EMAILS after native provisioning."""
import os
from django.db import transaction
from authentik.core.models import Group, User

emails = [email.strip().lower() for email in os.environ['READEST_ALLOWED_EMAILS'].split(',') if email.strip()]
if not emails:
    raise RuntimeError('Explicit email list is required')
with transaction.atomic():
    group = Group.objects.get(name='readest-users')
    for email in emails:
        users = list(User.objects.filter(email__iexact=email, is_active=True))
        if not users:
            raise RuntimeError('An approved Authentik identity does not exist')
        group.users.add(*users)
        print('Readest Authentik access granted:', email)
