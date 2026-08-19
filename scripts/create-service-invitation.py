#!/usr/bin/env python3
"""Create a reusable bearer-link service invitation inside `ak shell`."""

import hashlib
import os
from datetime import timedelta

from django.utils import timezone
from authentik.core.models import User
from authentik.flows.models import Flow
from authentik.stages.invitation.models import Invitation


label = os.environ.get("SERVICE_INVITE_LABEL", "shared").strip().lower()
hours = int(os.environ.get("SERVICE_INVITE_HOURS", "24"))
flow = Flow.objects.get(slug="google-source-enrollment")
creator = User.objects.get(username="akadmin")
invitation = Invitation.objects.create(
    name=(
        "audiobooks-"
        f"{hashlib.sha256(label.encode()).hexdigest()[:12]}-"
        f"{timezone.now().strftime('%Y%m%d%H%M%S')}"
    ),
    expires=timezone.now() + timedelta(hours=hours),
    flow=flow,
    created_by=creator,
    fixed_data={"services": ["audiobookshelf"], "reusable_link": True},
    # Social-source redirects do not retain Invitation-stage context. The
    # signed handoff cookie binds the browser to this reusable approval record;
    # repeat evaluation is safe because downstream provisioning is idempotent.
    single_use=False,
)
print(f"https://auth.shelfgoblin.dev/invite/{invitation.pk}")
