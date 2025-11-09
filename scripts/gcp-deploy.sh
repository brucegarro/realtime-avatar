#!/bin/bash
# GCP Deployment Helper Script
# Usage: ./scripts/gcp-deploy.sh [build|push|deploy|all]

set -e

PROJECT_ID="realtime-avatar-bg"
REGION="us-central1"
ZONE="us-central1-a"
REPOSITORY="realtime-avatar"
IMAGE_NAME="runtime"
IMAGE_TAG="cuda-latest"

IMAGE_URI="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:$IMAGE_TAG"

function build_image() {
    echo "Building CUDA Docker image..."
    cd runtime
    docker build -f Dockerfile.cuda -t $IMAGE_URI .
    cd ..
    echo "✓ Image built: $IMAGE_URI"
}

function push_image() {
    echo "Pushing image to Artifact Registry..."
    docker push $IMAGE_URI
    echo "✓ Image pushed: $IMAGE_URI"
}

function deploy_instance() {
    echo "Deploying GPU instance..."
    
    INSTANCE_NAME="realtime-avatar-gpu-1"
    
    # Check if instance exists
    if gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE &> /dev/null; then
        echo "Instance $INSTANCE_NAME already exists. Delete it first with:"
        echo "  gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE"
        exit 1
    fi
    
    # Create instance with T4 GPU
    gcloud compute instances create $INSTANCE_NAME \
        --project=$PROJECT_ID \
        --zone=$ZONE \
        --machine-type=n1-standard-4 \
        --accelerator=type=nvidia-tesla-t4,count=1 \
        --maintenance-policy=TERMINATE \
        --image-family=ubuntu-2204-lts \
        --image-project=ubuntu-os-cloud \
        --boot-disk-size=50GB \
        --boot-disk-type=pd-balanced \
        --metadata=startup-script='#!/bin/bash
# Install NVIDIA drivers
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

# Authenticate Docker with Artifact Registry
gcloud auth configure-docker '$REGION-docker.pkg.dev' --quiet

# Pull and run container
docker pull '$IMAGE_URI'
docker run -d --gpus all --name realtime-avatar -p 8000:8000 '$IMAGE_URI'
' \
        --tags=http-server,https-server
    
    echo "✓ Instance created: $INSTANCE_NAME"
    echo ""
    echo "Waiting for instance to be ready (this takes ~5 minutes for GPU drivers)..."
    echo "Monitor progress with:"
    echo "  gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='sudo journalctl -u google-startup-scripts -f'"
    echo ""
    echo "Once ready, get the external IP:"
    echo "  gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)'"
}

function create_firewall_rule() {
    echo "Creating firewall rule..."
    gcloud compute firewall-rules create allow-http-8000 \
        --project=$PROJECT_ID \
        --direction=INGRESS \
        --priority=1000 \
        --network=default \
        --action=ALLOW \
        --rules=tcp:8000 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=http-server || echo "Firewall rule may already exist"
    echo "✓ Firewall rule created"
}

case "$1" in
    build)
        build_image
        ;;
    push)
        push_image
        ;;
    deploy)
        create_firewall_rule
        deploy_instance
        ;;
    all)
        build_image
        push_image
        create_firewall_rule
        deploy_instance
        ;;
    *)
        echo "Usage: $0 {build|push|deploy|all}"
        echo ""
        echo "Commands:"
        echo "  build   - Build Docker image"
        echo "  push    - Push image to Artifact Registry"
        echo "  deploy  - Create GPU instance and deploy"
        echo "  all     - Build, push, and deploy"
        exit 1
        ;;
esac
