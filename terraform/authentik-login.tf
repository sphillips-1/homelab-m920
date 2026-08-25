# Authentik's adopted global blueprint remains compatibility-guarded because
# its content PUT triggers a false duplicate GroupUpdateStage validation error.
# Manage new configuration with native provider resources where coverage exists
# so ordinary Terraform applies can still deploy reviewed Authentik changes.

data "authentik_flow" "default_authentication" {
  slug = "default-authentication-flow"
}

data "authentik_flow" "administrator_recovery" {
  slug = "administrator-recovery"
}

resource "authentik_stage_identification" "google_login" {
  name                      = "homelab-google-login"
  user_fields               = []
  sources                   = ["ea38341d-43ff-4148-adde-c0892ec7a32c"]
  recovery_flow             = data.authentik_flow.administrator_recovery.id
  case_insensitive_matching = true
  pretend_user_exists       = true
  show_matched_user         = false
  show_source_labels        = true
}

resource "authentik_flow_stage_binding" "default_authentication_identification" {
  target               = data.authentik_flow.default_authentication.id
  stage                = authentik_stage_identification.google_login.id
  order                = 10
  evaluate_on_plan     = false
  re_evaluate_policies = true
  policy_engine_mode   = "any"
}

# Adopt the existing binding instead of attempting to create a second order-10
# identification step in the live default authentication flow.
import {
  to = authentik_flow_stage_binding.default_authentication_identification
  id = "452a8f98-8048-426a-9cf5-48d9ecf83482"
}
