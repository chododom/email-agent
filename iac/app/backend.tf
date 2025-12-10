# Remote backend
terraform {
  backend "gcs" {
    bucket  = "app-alza-email-agent"
    prefix  = "terraform/state"
  }
}