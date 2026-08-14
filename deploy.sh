#!/bin/bash
set -e

PROJECT_ID="rafahm-run-dev"
SERVICE_NAME="yt-sentiment-analysis"
REGION="us-central1"

echo "[1/3] Submitting Cloud Build with --no-cache..."
gcloud builds submit --config=cloudbuild.yaml .

IMAGE_URL="$REGION-docker.pkg.dev/$PROJECT_ID/cr-images/$SERVICE_NAME:latest"

echo "[2/3] Deploying $IMAGE_URL to Cloud Run..."
gcloud run deploy "$SERVICE_NAME"   --image "$IMAGE_URL"   --platform managed   --region "$REGION"   --ingress internal-and-cloud-load-balancing   --no-allow-unauthenticated   --cpu 4   --timeout 3600   --memory 10Gi   --set-env-vars YOUTUBE_API_KEY="${YOUTUBE_API_KEY}",GEMINI_API_KEY="${GEMINI_API_KEY}",DRIVE_FOLDER_ID="1MsXuPKrR6MM6o02NXt-yPE-Hwj7caiCT",DRIVE_RESOURCE_KEY="0-X26e-T0YzerdpL_8vA-uRg"

echo "[3/3] Updating traffic to 100% on latest revision..."
gcloud run services update-traffic "$SERVICE_NAME" --region "$REGION" --to-latest

gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format="yaml(status.latestReadyRevisionName,status.traffic)"
echo "✅ Deployment successful and serving 100% traffic on latest revision!"
