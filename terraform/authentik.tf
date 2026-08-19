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
  }
}
