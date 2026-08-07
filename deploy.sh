#!/bin/bash

PROJECT_ID="rafahm-run-dev"
SERVICE_NAME="yt-sentiment-analysis"
REGION="us-central1"
GCLOUD_PATH="gcloud"
IMAGE_URL="$REGION-docker.pkg.dev/$PROJECT_ID/cr-images/$SERVICE_NAME"

# Load environment variables from .env if it exists
if [ -f .env ]; then
  eval $(grep -v '^#' .env | sed 's/=/="/;s/$/"/')
fi

# Strip quotes if any remain
YOUTUBE_API_KEY=$(echo "$YOUTUBE_API_KEY" | tr -d "'\"")
GEMINI_API_KEY=$(echo "$GEMINI_API_KEY" | tr -d "'\"")

# Fallback GEMINI_API_KEY to YOUTUBE_API_KEY only if GEMINI_API_KEY is unset
if [ -z "$GEMINI_API_KEY" ]; then
  export GEMINI_API_KEY="$YOUTUBE_API_KEY"
fi
if [ -z "$YOUTUBE_API_KEY" ]; then
  export YOUTUBE_API_KEY="$GEMINI_API_KEY"
fi

export YOUTUBE_API_KEY
export GEMINI_API_KEY

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
  --set-env-vars YOUTUBE_API_KEY="$YOUTUBE_API_KEY",GEMINI_API_KEY="$GEMINI_API_KEY",DRIVE_FOLDER_ID="1MsXuPKrR6MM6o02NXt-yPE-Hwj7caiCT",DRIVE_RESOURCE_KEY="0-X26e-T0YzerdpL_8vA-uRg"
