output "otp_identity_provider_id" {
  description = "Cloudflare ID of the Terraform-managed One-Time PIN identity provider."
  value       = cloudflare_zero_trust_access_identity_provider.otp.id
}

output "calibre_web_application_audience" {
  description = "Access JWT audience for Calibre-Web, or null while protection is disabled."
  value       = try(cloudflare_zero_trust_access_application.calibre_web[0].aud, null)
}
