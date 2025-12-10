# Reference base remote state to get outputs of shared resources
data "terraform_remote_state" "base" {
  backend = "gcs"

  config = {
    bucket  = "base-alza-email-agent"
    prefix  = "terraform/state" 
  }
}

# Secret to store the Gmail OAuth refresh token in (version uploaded manually)
resource "google_secret_manager_secret" "gmail_sa_key" {
  secret_id = "gmail-service-account-key"
  replication {
    auto {}
  }
}

# PubSub Topic for Gmail push notifications
resource "google_pubsub_topic" "gmail_updates" {
  name       = "gmail-inbox-topic"
}

# Cloud Run Service
resource "google_cloud_run_v2_service" "agent_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.email_agent_sa.email

    scaling {
      min_instance_count = 0 
      max_instance_count = 1
    }
    
    containers {
      image = var.container_image
      
      # Environment variables from Secret Manager
      env {
        name = "GMAIL_SERVICE_ACC_JSON" 
        value_source {
          secret_key_ref {
            secret = google_secret_manager_secret.gmail_sa_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "LANGSMITH_API_KEY" 
        value_source {
          secret_key_ref {
            secret = "langsmith-api-key"
            version = "latest"
          }
        }
      }
      
      # Other necessary environment variables
      env {
        name  = "USER_EMAIL"
        value = var.user_email
      }
      env {
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.gmail_updates.id
      }
      env {
        name  = "FIRESTORE_NAME"
        value = data.terraform_remote_state.base.outputs.firestore_database_name
      }
      env {
        name  = "LANGSMITH_TRACING"
        value = true
      }
      env {
        name  = "LANGSMITH_ENDPOINT"
        value = "https://eu.api.smith.langchain.com"
      }
      env {
        name  = "LANGSMITH_PROJECT"
        value = "email-agent"
      }
      env {
        name  = "INDEX_ID"
        value = google_vertex_ai_index.vector_index.id
      }
      
      resources {
        cpu_idle = true
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
      }
    }
  }
}

# PubSub Subscription from Gmail-targeted topic to Cloud Run service
resource "google_pubsub_subscription" "push_to_agent" {
  name  = "gmail-push-subscription"
  topic = google_pubsub_topic.gmail_updates.name

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.agent_service.uri}/v1/gmail-webhook"
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
  }
}


# Cloud Scheduler Job for Gmail Watch Renewal
resource "google_cloud_scheduler_job" "watch_renewal_job" {
  name        = "${var.service_name}-watch-renewal"
  description = "Renews the Gmail API watch instruction every day."
  # Run once every 24 hours at 3:00 AM UTC (using the standard cron format)
  schedule    = "0 3 * * *" 
  region      = var.region

  http_target {
    uri         = "${google_cloud_run_v2_service.agent_service.uri}/v1/renew-watch"
    http_method = "POST"
    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }
}