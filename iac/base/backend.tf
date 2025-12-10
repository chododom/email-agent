# Remote backend
terraform {
  backend "gcs" {
    bucket  = "base-alza-email-agent"
    prefix  = "terraform/state"
  }
}