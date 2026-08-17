terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.9.0"
    }
  }

  backend "remote" {}
}

provider "azuread" {
  tenant_id = var.tenant_id
}
