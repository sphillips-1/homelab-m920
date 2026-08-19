#!/usr/bin/env python3
"""Revoke the fixed short-lived token created for Terraform adoption."""

from authentik.core.models import Token


deleted, _ = Token.objects.filter(identifier="terraform-adoption").delete()
print(f"revoked={deleted}")
