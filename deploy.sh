#!/bin/bash

PROJECT_ID="rafahm-run-dev"
SERVICE_NAME="yt-sentiment-analysis"
REGION="us-central1"
GCLOUD_PATH="gcloud"
IMAGE_URL="$REGION-docker.pkg.dev/$PROJECT_ID/cr-images/$SERVICE_NAME"

# Load environment variables from .env if it exists
set -a
[ -f .env ] && . .env
set +a

# Fallback GEMINI_API_KEY to YOUTUBE_API_KEY if not set
if [ -z "$GEMINI_API_KEY" ]; then
  export GEMINI_API_KEY="$YOUTUBE_API_KEY"
fi

echo "Setting project to $PROJECT_ID..."
$GCLOUD_PATH config set project $PROJECT_ID

echo "Enabling necessary APIs..."
$GCLOUD_PATH services enable cloudscheduler.googleapis.com cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com drive.googleapis.com youtube.googleapis.com

echo "Submitting build to Cloud Build..."
$GCLOUD_PATH builds submit . --tag $IMAGE_URL --suppress-logs

echo "Deploying to Cloud Run..."
$GCLOUD_PATH run deploy $SERVICE_NAME \
  --image $IMAGE_URL \
  --platform managed \
  --region $REGION \
  --ingress internal-and-cloud-load-balancing \
  --no-allow-unauthenticated \
  --clear-binary-authorization \
  --clear-network \
  --cpu 4 \
  --timeout 3600 \
  --memory 10Gi \
  --set-env-vars YOUTUBE_API_KEY="$YOUTUBE_API_KEY",GEMINI_API_KEY="$GEMINI_API_KEY"
