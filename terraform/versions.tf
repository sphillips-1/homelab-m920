terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.23.0"
    }
  }

  # HCP Terraform is configured during init. See backend.hcl.example.
  backend "remote" {}
}

provider "cloudflare" {}
