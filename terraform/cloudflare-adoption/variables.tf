variable "cloudflare_account_id" {
  type = string
}

variable "cloudflare_zone_id" {
  type = string
}

variable "zone_name" {
  type = string
}

variable "tunnel_id" {
  type = string
}

variable "tunnel_name" {
  type = string
}

# Declared only so the shared adoption tfvars file remains warning-free.
variable "enable_entra" {
  type    = bool
  default = false
}

variable "enable_access" {
  type    = bool
  default = false
}
