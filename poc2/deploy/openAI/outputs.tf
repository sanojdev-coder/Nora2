output "resource_group_name" {
  description = "Azure Resource Group name"
  value       = azurerm_resource_group.main.name
}

output "resource_group_location" {
  description = "Azure Resource Group location"
  value       = azurerm_resource_group.main.location
}

output "openai_account_name" {
  description = "Azure OpenAI account name"
  value       = azurerm_cognitive_account.main.name
}

output "openai_endpoint" {
  description = "Azure OpenAI endpoint"
  value       = azurerm_cognitive_account.main.endpoint
}

output "openai_primary_key" {
  description = "Primary key for the Azure OpenAI account"
  value       = azurerm_cognitive_account.main.primary_access_key
  sensitive   = true
}

output "openai_deployment_name" {
  description = "Deployment name for the Azure OpenAI model"
  value       = azurerm_cognitive_deployment.main.name
}
