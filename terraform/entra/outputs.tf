output "application_client_id" {
  description = "Client ID for the Cloudflare Access Entra integration."
  value       = azuread_application.cloudflare_access.client_id
}

output "application_object_id" {
  description = "Object ID of the Cloudflare Access Entra application."
  value       = azuread_application.cloudflare_access.object_id
}

output "service_principal_object_id" {
  description = "Object ID of the Cloudflare Access service principal."
  value       = azuread_service_principal.cloudflare_access.object_id
}
