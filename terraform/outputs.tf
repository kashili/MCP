output "web_app_url" {
  description = "Public URL for the deployed Azure web app."
  value       = "https://${azurerm_linux_web_app.main.default_hostname}"
}

output "resource_group_name" {
  description = "Azure resource group created for this deployment."
  value       = azurerm_resource_group.main.name
}

output "app_service_plan_name" {
  description = "Azure App Service Plan created for this deployment."
  value       = azurerm_service_plan.main.name
}
