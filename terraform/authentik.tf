# Authentik's native blueprint engine can represent more Authentik models than
# the Terraform provider's individual resources. The reviewed export is stored
# in Git, while Terraform owns the internal blueprint instance and its state.
#
# The checked-in file begins as a no-op seed. Replace it from the live instance
# with scripts/export-authentik-blueprint.sh, remove users/tokens/events and
# restore write-only secrets through !Env references, then enable this resource
# and run the adoption workflow.
resource "authentik_blueprint" "homelab" {
  count = var.enable_authentik_blueprint ? 1 : 0

  name    = var.authentik_blueprint_name
  content = file("${path.module}/authentik/homelab.yaml")
  enabled = var.authentik_blueprint_enabled

  lifecycle {
    prevent_destroy = true

    # Authentik 2026.5.6 and 2026.8.0 reject provider PUT validation for this
    # adopted blueprint while planning the source manager's dynamic
    # GroupUpdateStage. Keep Terraform ownership and destroy protection without
    # repeatedly submitting unchanged content. The reviewed YAML remains the
    # desired source for a future provider/Authentik validator fix.
    ignore_changes = [content]
  }
}
