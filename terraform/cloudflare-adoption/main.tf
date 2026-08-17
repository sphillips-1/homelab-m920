locals {
  public_hostnames = toset([
    "audiobooks.${var.zone_name}",
    "books.${var.zone_name}",
    "auth.${var.zone_name}",
  ])
}

resource "cloudflare_zero_trust_tunnel_cloudflared" "homelab" {
  account_id = var.cloudflare_account_id
  name       = var.tunnel_name
  config_src = "local"

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_dns_record" "public_hostnames" {
  for_each = local.public_hostnames

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
