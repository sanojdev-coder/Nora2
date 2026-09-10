output "resource_group_name" {
  description = "Azure Resource Group name"
  value       = azurerm_resource_group.main.name
}

output "resource_group_location" {
  description = "Azure Resource Group location"
  value       = azurerm_resource_group.main.location
}

output "container_app_environment_name" {
  description = "Name of the Azure Container App Environment"
  value       = azurerm_container_app_environment.main.name
}

output "container_app_environment_id" {
  description = "Resource ID of the Azure Container App Environment"
  value       = azurerm_container_app_environment.main.id
}

output "log_analytics_workspace_id" {
  description = "Resource ID of the Log Analytics workspace"
  value       = azurerm_log_analytics_workspace.main.id
}
