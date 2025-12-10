output "cloud_run_url" {
  description = "The URL of the deployed agent"
  value       = google_cloud_run_v2_service.agent_service.uri
}

output "pubsub_topic_id" {
  description = "The Topic ID to use in your Python Gmail watch() call"
  value       = google_pubsub_topic.gmail_updates.id
}

output "service_account_email" {
  description = "The email of the service account used by Cloud Run"
  value       = google_service_account.email_agent_sa.email
}

output "vector_index_name" {
  description = "Name of the deployed Vertex Search index"
  value       = google_vertex_ai_index_endpoint_deployed_index.deployed_index.id
}

output "vector_index_endpoint_id" {
  description = "ID of the Index Endpoint with the deployed Vertex Search index"
  value       = google_vertex_ai_index_endpoint.index_endpoint.id
}