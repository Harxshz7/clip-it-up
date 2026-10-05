#!/bin/sh
set -e

echo "Waiting for MinIO server to be reachable..."
until (/usr/bin/mc alias set localminio http://minio:9000 minioadmin minioadmin); do
  echo "MinIO not ready yet, retrying in 2s..."
  sleep 2
done

echo "Creating bucket 'clip-it-up-videos' if it doesn't exist..."
/usr/bin/mc mb --ignore-existing localminio/clip-it-up-videos

echo "Setting public download policy on bucket..."
/usr/bin/mc anonymous set download localminio/clip-it-up-videos

echo "MinIO bucket initialization completed successfully."
