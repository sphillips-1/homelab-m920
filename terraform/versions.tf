terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.23.0"
    }
    authentik = {
      source  = "goauthentik/authentik"
      version = "~> 2026.5.0"
    }
  }

  # HCP Terraform is configured during init. See backend.hcl.example.
  backend "remote" {}
}

provider "cloudflare" {}

# AUTHENTIK_URL and AUTHENTIK_TOKEN are read from the environment. Keeping the
# token out of HCL also keeps it out of plans and version control.
provider "authentik" {}
