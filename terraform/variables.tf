variable "cloudflare_account_id" {
  description = "Cloudflare account ID discovered from the dashboard or API."
  type        = string
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for the homelab domain."
  type        = string
}

variable "zone_name" {
  description = "Authoritative DNS zone, without a scheme."
  type        = string
}

variable "tunnel_id" {
  description = "UUID of the existing, locally configured cloudflared tunnel."
  type        = string
}

variable "tunnel_name" {
  description = "Exact current name of the existing tunnel. Verify before import."
  type        = string
  default     = "homelab-m920-local"
}

variable "enable_authentik_blueprint" {
  description = "Manage the reviewed Authentik export as an internal blueprint. Enable only after adoption/import."
  type        = bool
  default     = false
}

variable "authentik_blueprint_name" {
  description = "Stable name of the Terraform-managed Authentik blueprint instance."
  type        = string
  default     = "homelab-terraform"
}
