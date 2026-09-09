# Azure OpenAI Terraform

This folder provisions:

- an Azure resource group named `RehnaResourceGroup`
- an Azure OpenAI account
- a GPT-5 mini deployment

Use the default values or override them with Terraform variables.

Example:

```bash
terraform init
terraform plan \
  -var="resource_group_name=RehnaResourceGroup" \
  -var="location=West US 3" \
  -var="openai_account_name=rehnaopenai" \
  -var="openai_deployment_name=gpt-4.1-mini" \
  -var="openai_model_name=gpt-4.1-mini" \
  -var="openai_model_version=2025-04-14"

tterraform apply -auto-approve
```

After deployment, Terraform will output the endpoint and sensitive access key.
