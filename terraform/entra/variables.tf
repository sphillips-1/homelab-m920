variable "tenant_id" {
  description = "Directory ID of the Entra External ID tenant."
  type        = string
}

variable "cloudflare_access_team_name" {
  description = "Cloudflare Zero Trust team name used in the OAuth callback URI."
  type        = string
}

variable "application_display_name" {
  description = "Display name of the Entra application used by Cloudflare Access."
  type        = string
  default     = "Cloudflare Access - homelab-m920"
}

variable "client_secret_end_date" {
  description = "UTC RFC3339 expiration for Cloudflare's OAuth client credential."
  type        = string
}
