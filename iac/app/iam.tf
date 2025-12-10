########################
### Service Accounts ###
########################

# Service Account for the Cloud Run service
resource "google_service_account" "email_agent_sa" {
  account_id   = "email-agent-sa"
  display_name = "Email Agent Service Account"
}

# Service Account for the PubSub subscription
resource "google_service_account" "pubsub_invoker" {
  account_id   = "pubsub-invoker-sa"
  display_name = "PubSub Invoker for Cloud Run"
}

# Service Account for the scheduled watch job
resource "google_service_account" "scheduler_sa" {
  account_id   = "cloud-schduler-sa"
  display_name = "Cloud Scheduler Service Account"
}

###########
### IAM ###
###########

# Grant the Cloud Run SA permission to read secrets
resource "google_project_iam_member" "secret_accessor" {
  project   = var.project_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.email_agent_sa.email}"
}

# Grant the Cloud Run SA permission to read/write Firestore data
resource "google_project_iam_member" "firestore_data_access" {
  project = var.project_id
  role    = "roles/datastore.user" 
  member  = "serviceAccount:${google_service_account.email_agent_sa.email}"
}

# Grant the Cloud Run SA permission to call Vertex AI
resource "google_project_iam_member" "vertex_ai_access" {
  project = var.project_id
  role    = "roles/aiplatform.user" 
  member  = "serviceAccount:${google_service_account.email_agent_sa.email}"
}

# Grant the Cloud Run SA permission to ingest data into the Vector Store
resource "google_project_iam_member" "vector_store_role" {
  project = var.project_id
  role    = "roles/vectorsearch.collectionWriter"
  member  = "serviceAccount:${google_service_account.email_agent_sa.email}"
}

# Grant the Cloud Run SA permission to read/write the GCS files
resource "google_project_iam_member" "gcs_object_admin_role" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.email_agent_sa.email}"
}

# Grant the Cloud Run SA permission to list GCS buckets
resource "google_project_iam_member" "gcs_bucket_reader_role" {
  project = var.project_id
  role    = "roles/storage.bucketViewer"
  member  = "serviceAccount:${google_service_account.email_agent_sa.email}"
}

# Allow the PubSub Service Account to invoke Cloud Run
resource "google_cloud_run_service_iam_member" "pubsub_invokes_run" {
  location = google_cloud_run_v2_service.agent_service.location
  service  = google_cloud_run_v2_service.agent_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

# Allow Gmail (Global Google Service) to publish to the pubsub topic
resource "google_pubsub_topic_iam_member" "gmail_publish" {
  topic  = google_pubsub_topic.gmail_updates.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:gmail-api-push@system.gserviceaccount.com" # Google's global sender
}

# Allow the Google Storage Service Agent to publish to the RAG-update pubsub topic
resource "google_pubsub_topic_iam_member" "gcs_event_publish" {
  topic  = google_pubsub_topic.gcs_event_topic.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-305120775386@gs-project-accounts.iam.gserviceaccount.com"
}

# Allow the Cloud Scheduler Service Account to invoke Cloud Run
resource "google_cloud_run_service_iam_member" "scheduler_invokes_run" {
  location = google_cloud_run_v2_service.agent_service.location
  service  = google_cloud_run_v2_service.agent_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_sa.email}"
}