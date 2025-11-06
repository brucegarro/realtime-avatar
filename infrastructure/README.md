# Realtime Avatar Infrastructure

Terraform configuration for GCP deployment.

## Status
🚧 **Stub - To be implemented for production deployment**

## Planned Resources
- Cloud Run GPU (L4) for runtime service
- Cloud Run Web (CPU) for web UI
- Google Cloud Storage for assets
- IAM roles and service accounts
- Load balancer / CDN
- Monitoring and logging

## Usage
```bash
cd infrastructure
terraform init
terraform plan
terraform apply
```

## Cost Management
- Cloud Run GPU: Scales to zero when idle
- Target: < $100/month
- GPU billing: Usage-based only
