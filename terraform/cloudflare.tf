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

resource "cloudflare_zero_trust_access_identity_provider" "otp" {
  account_id = var.cloudflare_account_id
  name       = "One-time PIN"
  type       = "onetimepin"
  config     = {}
}

# Calibre-Web is the first and only application placed behind Access in this
# phase. Audiobookshelf native clients require separate compatibility testing.
resource "cloudflare_zero_trust_access_application" "calibre_web" {
  count = var.enable_calibre_access ? 1 : 0

  account_id                = var.cloudflare_account_id
  name                      = "Calibre-Web"
  domain                    = local.application_hostnames.calibre_web
  type                      = "self_hosted"
  session_duration          = var.access_session_duration
  allowed_idps              = [cloudflare_zero_trust_access_identity_provider.otp.id]
  auto_redirect_to_identity = true

  policies = [{
    name       = "Allow approved users with OTP"
    decision   = "allow"
    precedence = 1
    include = [for email in var.access_users : {
      email = { email = email }
    }]
    require = [{
      login_method = {
        id = cloudflare_zero_trust_access_identity_provider.otp.id
      }
    }]
  }]

  lifecycle {
    prevent_destroy = true
  }
}

# This opt-in hostname exercises Cloudflare Access without changing the
# production Audiobookshelf hostname used by native clients.
resource "cloudflare_dns_record" "audiobookshelf_access_test" {
  count = var.enable_audiobookshelf_access_test ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = local.audiobookshelf_test_hostname
  type    = "CNAME"
  content = "${var.tunnel_id}.cfargotunnel.com"
  proxied = true
  ttl     = 1

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_zero_trust_access_application" "audiobookshelf_test" {
  count = var.enable_audiobookshelf_access_test ? 1 : 0

  account_id                = var.cloudflare_account_id
  name                      = "Audiobookshelf compatibility test"
  domain                    = local.audiobookshelf_test_hostname
  type                      = "self_hosted"
  session_duration          = var.access_session_duration
  allowed_idps              = [cloudflare_zero_trust_access_identity_provider.otp.id]
  auto_redirect_to_identity = true

  policies = [{
    name       = "Allow approved test users with OTP"
    decision   = "allow"
    precedence = 1
    include = [for email in var.access_users : {
      email = { email = email }
    }]
    require = [{
      login_method = {
        id = cloudflare_zero_trust_access_identity_provider.otp.id
      }
    }]
  }]

  lifecycle {
    prevent_destroy = true
  }
}
