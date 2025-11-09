# GCP Deployment Guide - Quick Reference

## Deployment Strategy: Hybrid Approach

**Phase 1 (Weeks 1-2): SSH for Discovery** 🔍
- Manually deploy instances to test configurations
- SSH access for debugging and iteration
- Document what works in this file
- Goal: Find optimal GPU type, config, and costs

**Phase 2 (Week 3+): Terraform for Production** 🏗️
- Codify working setup in Terraform
- Push-to-deploy workflow (no SSH needed)
- Separate environments: dev/staging/prod
- Immutable infrastructure for training and inference

**Current Phase:** Discovery (SSH-based testing)

## Current Status

✅ GCP project created: `realtime-avatar-bg`  
✅ Billing enabled  
✅ APIs enabled: Compute Engine, Storage, Artifact Registry  
✅ CUDA Docker image built  
✅ Firewall rule created (port 8000)
🔄 Instance provisioning in progress

## Discovery Phase: Things to Learn

During SSH testing, document:
- [ ] Which GPU type gives best price/performance (T4, V100, L4, A100)
- [ ] Optimal instance size (n1-standard-4 vs 8 vs 16)
- [ ] GFPGAN performance on CUDA vs M3
- [ ] Model loading time (affects cold start)
- [ ] Actual costs per video generation
- [ ] Memory requirements (peak GPU VRAM usage)
- [ ] Autoscaling trigger metrics (CPU? GPU? Queue depth?)
- [ ] Network egress costs (video downloads)

## Next Steps

### 1. Verify Image Push Complete

```bash
gcloud artifacts docker images list us-central1-docker.pkg.dev/realtime-avatar-bg/realtime-avatar/runtime
```

Should show: `cuda-latest` tag

### 2. Deploy Test GPU Instance (Manual - First Time)

**Option A: Using the deployment script:**
```bash
./scripts/gcp-deploy.sh deploy
```

**Option B: Manual deployment:**
```bash
# Create firewall rule (one-time)
gcloud compute firewall-rules create allow-http-8000 \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:8000 \
    --source-ranges=0.0.0.0/0 \
    --target-tags=http-server

# Create GPU instance
gcloud compute instances create realtime-avatar-test \
    --project=realtime-avatar-bg \
    --zone=us-central1-a \
    --machine-type=n1-standard-4 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --maintenance-policy=TERMINATE \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB \
    --boot-disk-type=pd-balanced \
    --tags=http-server
```

### 3. SSH into Instance and Set Up

```bash
# SSH to instance
gcloud compute ssh realtime-avatar-test --zone=us-central1-a

# On the instance:
# Install NVIDIA drivers (takes 5-10 minutes)
curl https://raw.githubusercontent.com/GoogleCloudPlatform/compute-gpu-installation/main/linux/install_gpu_driver.py --output install_gpu_driver.py
sudo python3 install_gpu_driver.py

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install nvidia-docker
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Verify GPU access
nvidia-smi

# Authenticate Docker with Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet

# Pull and run container
docker pull us-central1-docker.pkg.dev/realtime-avatar-bg/realtime-avatar/runtime:cuda-latest
docker run -d --gpus all --name realtime-avatar -p 8000:8000 \
    us-central1-docker.pkg.dev/realtime-avatar-bg/realtime-avatar/runtime:cuda-latest

# Check logs
docker logs -f realtime-avatar
```

### 4. Get Instance IP and Test

```bash
# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe realtime-avatar-test \
    --zone=us-central1-a \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "Instance IP: $EXTERNAL_IP"

# Test health endpoint (from local machine)
curl http://$EXTERNAL_IP:8000/health

# Test video generation
curl -X POST http://$EXTERNAL_IP:8000/api/script \
    -H "Content-Type: application/json" \
    -d '{
        "script": "Hello from the cloud! This is running on a Tesla T4 GPU.",
        "image_path": "assets/images/bruce_kunming.png"
    }'
```

### 5. Run Benchmark Comparison

**Local (M3 MPS):**
- Baseline: ~52s for 8.7s video
- With GFPGAN: ~284s (5.4x slower)

**Expected on T4 GPU:**
- Baseline: ~8-10s (5-6x faster)
- With GFPGAN: ~20-30s (8-12x faster)

```bash
# Benchmark on GCP
time curl -X POST http://$EXTERNAL_IP:8000/api/script \
    -H "Content-Type: application/json" \
    -d '{
        "script": "This is a benchmark test running on Google Cloud.",
        "image_path": "assets/images/bruce_kunming.png",
        "enhancer": "gfpgan"
    }' \
    --output test_gcp_output.json
```

### 6. Clean Up Test Instance

```bash
# Stop instance (stop billing, keep disk)
gcloud compute instances stop realtime-avatar-test --zone=us-central1-a

# Delete instance (remove everything)
gcloud compute instances delete realtime-avatar-test --zone=us-central1-a
```

## Cost Tracking

**Current spend:**
- Image storage: ~$0.01/day (~$0.30/month)
- T4 instance when running: $0.35/hour
- Network egress: ~$0.12/GB

**Budget alerts set at:**
- $50 - Warning
- $100 - Alert
- (Set more aggressive limits as needed)

## Troubleshooting

**GPU not detected:**
```bash
# Check NVIDIA driver
nvidia-smi

# Check Docker GPU access
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

**Container crashes:**
```bash
docker logs realtime-avatar
docker exec -it realtime-avatar /bin/bash
# Inside container:
python -c "import torch; print(torch.cuda.is_available())"
```

**Firewall issues:**
```bash
# Check firewall rules
gcloud compute firewall-rules list | grep 8000

# Test from instance itself
curl http://localhost:8000/health
```

## Next Phase: Auto-scaling Setup

After validating the single instance works and documenting findings:

### Week 3: Terraform Infrastructure-as-Code
1. ✅ Create `infrastructure/gcp/` directory structure
2. ✅ Define instance templates in Terraform
3. ✅ Set up Managed Instance Groups with autoscaling
4. ✅ Configure Cloud Load Balancer
5. ✅ Add Cloud Monitoring dashboards
6. ✅ Implement Pub/Sub queue for async jobs

### Week 4: CI/CD Pipeline
1. ✅ GitHub Actions workflow for Docker builds
2. ✅ Automatic push to Artifact Registry on merge
3. ✅ Terraform plan/apply on infrastructure changes
4. ✅ Blue/green deployments for zero-downtime updates
5. ✅ Automated rollback on health check failures

### Production Readiness Checklist
- [ ] Terraform modules tested in staging environment
- [ ] Load testing completed (100+ concurrent requests)
- [ ] Cost monitoring and budget alerts configured
- [ ] Logging and error tracking (Cloud Logging + Sentry)
- [ ] Disaster recovery plan documented
- [ ] Security audit (IAM roles, firewall rules, secrets management)
- [ ] Documentation for team handoff

See `CLOUD_DEPLOYMENT.md` for full architecture details.
