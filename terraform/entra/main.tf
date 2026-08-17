data "azuread_client_config" "current" {}

resource "azuread_application" "cloudflare_access" {
  display_name     = var.application_display_name
  description      = "OIDC identity provider for Cloudflare Access"
  sign_in_audience = "AzureADMyOrg"
  owners           = [data.azuread_client_config.current.object_id]

  api {
    requested_access_token_version = 2
  }

  required_resource_access {
    resource_app_id = "00000003-0000-0000-c000-000000000000"

    # Delegated Microsoft Graph User.Read. Group and Conditional Access sync
    # are intentionally disabled, so broader directory reads are unnecessary.
    resource_access {
      id   = "e1fe6dd8-ba31-4d61-89e7-88639da4683d"
      type = "Scope"
    }
  }

  web {
    redirect_uris = [
      "https://${var.cloudflare_access_team_name}.cloudflareaccess.com/cdn-cgi/access/callback",
    ]
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "azuread_service_principal" "cloudflare_access" {
  client_id                    = azuread_application.cloudflare_access.client_id
  app_role_assignment_required = false
  owners                       = [data.azuread_client_config.current.object_id]

  lifecycle {
    prevent_destroy = true
  }
}

resource "azuread_application_password" "cloudflare_access" {
  application_id = azuread_application.cloudflare_access.id
  display_name   = "Cloudflare Access"
  end_date       = var.client_secret_end_date
}
