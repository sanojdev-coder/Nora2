variable "resource_group_name" {
  type        = string
  description = "Name oof the Azure Resource Group"
  default     = "SanojResourceGroup"
}

variable "location" {
  type        = string
  description = "Azure region"
  default     = "West US 3"
}

variable "acr_name" {
  type        = string
  description = "Name of the Azure Container Registry"
  default     = "sanojacr"
}

variable "acr_sku" {
  type        = string
  description = "SKU of the Azure Container Registry"
  default     = "Standard"
}

variable "acr_admin_enabled" {
  type        = bool
  description = "Enable the admin user for the Azure Container Registry"
  default     = true
}
