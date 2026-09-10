terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_cognitive_account" "main" {
  name                          = var.openai_account_name
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  kind                          = var.openai_kind
  sku_name                      = var.openai_sku_name
  custom_subdomain_name         = var.openai_account_name
  public_network_access_enabled = true
  local_auth_enabled            = true
  tags                          = var.tags
}

resource "azurerm_cognitive_deployment" "main" {
  name                 = var.openai_deployment_name
  cognitive_account_id = azurerm_cognitive_account.main.id
  rai_policy_name      = "Microsoft.Default"

  model {
    format  = "OpenAI"
    name    = var.openai_model_name
    version = var.openai_model_version
  }

  scale {
    type     = "Standard"
    capacity = var.openai_model_capacity
  }
}
