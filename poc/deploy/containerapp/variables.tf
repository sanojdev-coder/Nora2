variable "resource_group_name" {
  type        = string
  description = "Name of the Azure Resource Group"
  default     = "SanojResourceGroup"
}

variable "location" {
  type        = string
  description = "Azure region"
  default     = "West US 3"
}

variable "log_analytics_workspace_name" {
  type        = string
  description = "Name of the Log Analytics workspace used by the Container App Environment"
  default     = "sanoj-containerapps-logs"
}

variable "log_analytics_sku" {
  type        = string
  description = "SKU of the Log Analytics workspace"
  default     = "PerGB2018"
}

variable "log_analytics_retention_days" {
  type        = number
  description = "Retention period in days for the Log Analytics workspace"
  default     = 30
}

variable "container_app_environment_name" {
  type        = string
  description = "Name of the Azure Container App Environment"
  default     = "sanoj-container-apps-env"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to Azure resources"
  default = {
    environment = "dev"
  }
}
