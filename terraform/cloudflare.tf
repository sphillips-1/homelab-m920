# This resource MUST be imported before any apply. The connector remains locally
# configured from /srv/homelab/appdata/cloudflared/config.yml.
resource "cloudflare_zero_trust_tunnel_cloudflared" "homelab" {
  account_id = var.cloudflare_account_id
  name       = var.tunnel_name
  config_src = "local"

  lifecycle {
    prevent_destroy = true
  }
}

# These records MUST each be imported before apply. Their names intentionally
# match the existing cloudflared templates.
resource "cloudflare_dns_record" "public_hostnames" {
  for_each = toset(concat(values(local.application_hostnames), ["auth.${var.zone_name}"]))

  zone_id = var.cloudflare_zone_id
  name    = each.value
  type    = "CNAME"
  content = "${var.tunnel_id}.cfargotunnel.com"
  proxied = true
  ttl     = 1

  lifecycle {
    prevent_destroy = true
  }
}
