#!/bin/bash
# Build all Docker images for the project

set -e

echo "=== Building Realtime Avatar Docker Images ==="

# Build runtime service
echo ""
echo "Building runtime service..."
docker build -t realtime-avatar-runtime:latest ./runtime

# Build evaluator
echo ""
echo "Building evaluator..."
docker build -t realtime-avatar-evaluator:latest ./evaluator

echo ""
echo "=== Build Complete ==="
docker images | grep realtime-avatar
