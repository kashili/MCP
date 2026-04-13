variable "resource_group_name" {
  description = "Azure Resource Group name."
  type        = string
  default     = "mcp-rg"
}

variable "location" {
  description = "Azure region for the resources."
  type        = string
  default     = "centralus"
}

variable "app_name" {
  description = "Globally unique Azure App Service name."
  type        = string
  default     = "mcpprojectmanager"
}

variable "app_service_tier" {
  description = "Azure App Service Plan tier."
  type        = string
  default     = "Basic"
}

variable "app_service_sku" {
  description = "Azure App Service Plan SKU size."
  type        = string
  default     = "B1"
}

variable "startup_command" {
  description = "Gunicorn startup command for the FastAPI app."
  type        = string
  default     = "gunicorn app:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000"
}

variable "app_settings" {
  description = "Azure App Service Settings / environment variables for the app."
  type        = map(string)
  default     = {}
}
