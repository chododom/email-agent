resource "google_storage_bucket" "rag_delta_bucket" {
  name     = "rag-delta-bucket-${var.project_id}"
  location = var.region
  uniform_bucket_level_access = true
}

# Vertex AI Index
resource "google_vertex_ai_index" "vector_index" {
  project      = var.project_id
  region       = var.region
  display_name = "vector-search-index"
  description  = "Vertex AI Index for RAG text data."

  metadata {
    contents_delta_uri = "gs://${google_storage_bucket.rag_delta_bucket.name}/contents"
    config {
      dimensions          = var.vector_dimensions
      distance_measure_type = "COSINE_DISTANCE"
      feature_norm_type = "UNIT_L2_NORM"
      approximate_neighbors_count = 100
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count    = 100
        }
      }
    }
  }

  # Continuous, near real-time ingestion
  index_update_method = "STREAM_UPDATE"
}

# Vertex AI Index Endpoint
resource "google_vertex_ai_index_endpoint" "index_endpoint" {
  project             = var.project_id
  region              = var.region
  display_name        = "rag-vector-search-endpoint"
  public_endpoint_enabled = false # Allows querying over the public internet (secured by IAM)
}

# Deploy the Index to the Endpoint
resource "google_vertex_ai_index_endpoint_deployed_index" "deployed_index" {
  index_endpoint    = google_vertex_ai_index_endpoint.index_endpoint.id
  display_name      = "rag-deployed-index"
  index             = google_vertex_ai_index.vector_index.id
  deployed_index_id = "rag_index_deployment2"

  automatic_resources {
    min_replica_count = 1
    max_replica_count = 1
  }
}


# GCS Bucket for input files
resource "google_storage_bucket" "rag_data_bucket" {
  project      = var.project_id
  name         = "vector-data-source-${var.project_id}"
  location     = var.region
  force_destroy = true
  uniform_bucket_level_access = true
}

# PubSub Topic to receive GCS events
resource "google_pubsub_topic" "gcs_event_topic" {
  project = var.project_id
  name    = "gcs-file-vector-ingestion-events"
}


# GCS sends a notification to PubSub on new object creation
resource "google_storage_notification" "gcs_pubsub_notification" {
  bucket         = google_storage_bucket.rag_data_bucket.name
  topic          = google_pubsub_topic.gcs_event_topic.id
  payload_format = "JSON_API_V1"
  event_types    = ["OBJECT_FINALIZE"] # Trigger on new object creation

  depends_on = [google_storage_bucket.rag_data_bucket, google_pubsub_topic.gcs_event_topic]
}

resource "google_pubsub_subscription" "cloud_run_subscription" {
  project = var.project_id
  name    = "gcs-event-to-vector-run-sub"
  topic   = google_pubsub_topic.gcs_event_topic.name

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.agent_service.uri}/v1/ingest"
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
  }

  depends_on = [google_storage_notification.gcs_pubsub_notification]
}