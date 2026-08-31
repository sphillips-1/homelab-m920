#!/usr/bin/env python3
"""Turn an Authentik global export into a reviewable configuration blueprint."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


EXCLUDED_MODELS = {
    None,
    "null",
    "authentik_blueprints.blueprintinstance",
    "authentik_core.token",
    "authentik_core.user",
    "authentik_crypto.certificatekeypair",
    "authentik_events.notificationrule",
    "authentik_events.notificationtransport",
    "authentik_rbac.role",
    "authentik_sources_oauth.useroauthsourceconnection",
    "authentik_stages_invitation.invitation",
    "authentik_tasks_schedules.schedule",
}

CUSTOM_GROUPS = {"audiobooks-users", "books-users", "status-users"}

SEED_NAMES = {
    "Audiobookshelf",
    "Audiobookshelf OIDC",
    "Books",
    "Books Proxy",
    "Status",
    "Status Proxy",
    "Top listeners",
    "Google",
    "authentik Embedded Outpost",
    "default-authentication-identification",
}
SEED_SLUGS = {
    "audiobookshelf",
    "books",
    "status",
    "top-listeners",
    "google",
    "google-source-enrollment",
}
REVERSE_REFERENCE_MODELS = {
    "authentik_flows.flowstagebinding",
    "authentik_policies.policybinding",
    "authentik_stages_identification.identificationstage",
}


class EnvReference(str):
    """A scalar rendered as Authentik's !Env blueprint tag."""


def represent_env(dumper: yaml.SafeDumper, value: EnvReference) -> yaml.Node:
    return dumper.represent_scalar("!Env", str(value))


yaml.SafeDumper.add_representer(EnvReference, represent_env)


def sanitize_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    model = entry.get("model")
    if model in EXCLUDED_MODELS:
        return None

    attrs = entry.get("attrs") or {}

    if model == "authentik_sources_oauth.oauthsource":
        # Authentik 2026.5 rebuilds source-owned flow-manager stages whenever an
        # OAuth source is updated. Replaying an adopted source through a
        # blueprint then fails validation because its internal GroupUpdateStage
        # already exists. Keep the live source outside reconciliation; managed
        # identification stages can still reference its stable UUID.
        return None

    if (
        model == "authentik_stages_identification.identificationstage"
        and attrs.get("name") == "default-authentication-identification"
    ):
        # This bundled stage owns the source selector. Validating an update to
        # its source relation plans Authentik's dynamic GroupUpdateStage and
        # collides with the existing in-memory stage name. Providers and flow
        # bindings continue to reference the unchanged live stage by UUID.
        return None

    if model == "authentik_core.group":
        if attrs.get("name") not in CUSTOM_GROUPS:
            return None
        # Omit authorization grants rather than emitting empty collections.
        # Empty users would revoke every existing membership on reconciliation;
        # omission preserves live grants while keeping identities out of Git.
        attrs.pop("users", None)
        attrs.pop("roles", None)

    if model == "authentik_providers_oauth2.oauth2provider":
        attrs.pop("client_secret", None)
        if attrs.get("name") == "Audiobookshelf OIDC":
            attrs["client_secret"] = EnvReference(
                "AUTHENTIK_AUDIOBOOKSHELF_CLIENT_SECRET"
            )

    if (
        model == "authentik_policies_expression.expressionpolicy"
        and attrs.get("name") == "google-email-allowlist"
    ):
        # This policy contains personal email addresses. Store the complete
        # Authentik expression in the private service environment instead.
        attrs["expression"] = EnvReference(
            "AUTHENTIK_GOOGLE_EMAIL_ALLOWLIST_EXPRESSION"
        )

    if (
        model == "authentik_flows.flowstagebinding"
        and attrs.get("evaluate_on_plan") is False
        and attrs.get("re_evaluate_policies") is False
    ):
        # Authentik can persist this combination, but its 2026.5 blueprint
        # validator rejects it as having neither plan nor run evaluation.
        attrs["re_evaluate_policies"] = True

    entry["attrs"] = attrs
    return entry


def scalar_values(value: Any) -> set[Any]:
    if isinstance(value, dict):
        result: set[Any] = set()
        for nested in value.values():
            result.update(scalar_values(nested))
        return result
    if isinstance(value, list):
        result = set()
        for nested in value:
            result.update(scalar_values(nested))
        return result
    if isinstance(value, (str, int)):
        return {value}
    return set()


def select_configuration_closure(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep custom roots, their dependencies, and bindings targeting them."""

    by_pk = {
        entry.get("identifiers", {}).get("pk"): index
        for index, entry in enumerate(entries)
        if entry.get("identifiers", {}).get("pk") is not None
    }
    selected = {
        index
        for index, entry in enumerate(entries)
        if (entry.get("attrs") or {}).get("name") in SEED_NAMES
        or (entry.get("attrs") or {}).get("slug") in SEED_SLUGS
        or (
            entry.get("model") == "authentik_core.group"
            and (entry.get("attrs") or {}).get("name") in CUSTOM_GROUPS
        )
    }

    changed = True
    while changed:
        changed = False
        selected_pks = {
            entries[index].get("identifiers", {}).get("pk") for index in selected
        }

        for index in tuple(selected):
            for value in scalar_values(entries[index].get("attrs") or {}):
                dependency = by_pk.get(value)
                if dependency is not None and dependency not in selected:
                    selected.add(dependency)
                    changed = True

        for index, entry in enumerate(entries):
            if index in selected or entry.get("model") not in REVERSE_REFERENCE_MODELS:
                continue
            if scalar_values(entry.get("attrs") or {}) & selected_pks:
                selected.add(index)
                changed = True

    return [entry for index, entry in enumerate(entries) if index in selected]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.input.resolve() == args.output.resolve():
        raise SystemExit("Input and output must be different files.")
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite {args.output}")

    document = yaml.safe_load(args.input.read_text(encoding="utf-8"))
    candidates = []
    removed = 0
    for original in document.get("entries", []):
        sanitized = sanitize_entry(original)
        if sanitized is None:
            removed += 1
        else:
            candidates.append(sanitized)

    entries = select_configuration_closure(candidates)
    removed += len(candidates) - len(entries)

    result = {
        "version": 1,
        "metadata": {
            "name": "Homelab Terraform configuration",
            "labels": {
                "blueprints.goauthentik.io/description": (
                    "Sanitized Authentik configuration managed by Terraform"
                )
            },
        },
        "context": {},
        "entries": entries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.dump(result, Dumper=yaml.SafeDumper, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    print(f"Retained {len(entries)} configuration entries; removed {removed} stateful entries.")


if __name__ == "__main__":
    main()
