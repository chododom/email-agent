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

variable "container_image" {
  description = "The container image to deploy"
  type        = string
}

variable "user_email" {
  description = "Email of the agent's inbox"
  type        = string
}

variable "vector_dimensions" {
  description = "Dimensionality of the vectors in the vector database"
  type        = number
  default     = 256
}