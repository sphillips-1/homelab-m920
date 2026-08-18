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

variable "access_users" {
  description = "Exact email addresses authorized for Cloudflare Access. Authentication alone never grants access."
  type        = set(string)
  sensitive   = true
  default     = []

  validation {
    condition     = !(var.enable_calibre_access || var.enable_audiobookshelf_access_test) || (length(var.access_users) > 0 && alltrue([for email in var.access_users : can(regex("^[^@[:space:]]+@[^@[:space:]]+$", email))]))
    error_message = "When an Access application is enabled, access_users must contain at least one syntactically valid email address."
  }
}

variable "enable_calibre_access" {
  description = "Create Cloudflare Access protection for Calibre-Web after the tunnel and DNS adoption plan is clean."
  type        = bool
  default     = false
}

variable "enable_audiobookshelf_access_test" {
  description = "Create an isolated OTP-protected Audiobookshelf compatibility hostname. This never changes the production Audiobookshelf hostname."
  type        = bool
  default     = false
}

variable "access_session_duration" {
  description = "Cloudflare Access session duration. Match the imported applications before first plan."
  type        = string
  default     = "168h"
}
