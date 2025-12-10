# Enable necessary APIs
resource "google_project_service" "enabled_apis" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "gmail.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "firestore.googleapis.com",
    "aiplatform.googleapis.com",
    "speech.googleapis.com",
    "generativelanguage.googleapis.com",
    "discoveryengine.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}


# Define the Artifact Registry Docker repository
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "${var.service_name}-repo"
  description   = "Docker repository for the Email Agent."
  format        = "DOCKER"
}


# Create Firestore database
resource "google_firestore_database" "database" {
  project = var.project_id
  name    = "${var.service_name}-db"
  location_id = var.region
  type = "FIRESTORE_NATIVE" 
}