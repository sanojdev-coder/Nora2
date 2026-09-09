variable "resource_group_name" {
  type        = string
  description = "Name of the Azure Resource Group"
  default     = "RehnaResourceGroup"
}

variable "location" {
  type        = string
  description = "Azure region"
  default     = "West US 3"
}

variable "tags" {
  type = map(string)
  default = {
    environment = "dev"
    project     = "Nora"
    managed-by  = "terraform"
  }
}

variable "openai_account_name" {
  type        = string
  description = "Globally unique Azure OpenAI account name"
  default     = "rehnaopenai"
}

variable "openai_kind" {
  type        = string
  description = "Cognitive Services account kind"
  default     = "OpenAI"
}

variable "openai_sku_name" {
  type        = string
  description = "Azure OpenAI SKU"
  default     = "S0"
}

variable "openai_deployment_name" {
  type        = string
  description = "Name of the Azure OpenAI model deployment"
  default     = "gpt-4.1-mini"
}

variable "openai_model_name" {
  type        = string
  description = "Azure OpenAI model name"
  default     = "gpt-4.1-mini"
}

variable "openai_model_version" {
  type        = string
  description = "Version of the Azure OpenAI model to deploy"
  default     = "2025-04-14"
}

variable "openai_model_capacity" {
  type        = number
  description = "Capacity for the Azure OpenAI deployment"
  default     = 1
}
