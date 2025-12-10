variable "project_id" {
  description = "The GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for resources"
  type        = string
  default     = "europe-west3"
}

variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string
  default     = "email-agent"
}