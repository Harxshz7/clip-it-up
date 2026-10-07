import re
import uuid
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from clip_shared.config import get_settings


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal or unsafe characters."""
    # Keep alphanumeric, dot, underscore, dash
    clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
    # Remove leading dots or slashes
    clean = clean.lstrip('._')
    return clean or "unnamed_video.mp4"


def get_storage_key(user_id: uuid.UUID, video_id: uuid.UUID, filename: str) -> str:
    """Generate canonical S3 storage key: users/{user_id}/videos/{video_id}/source/{filename}"""
    clean_name = sanitize_filename(filename)
    return f"users/{str(user_id)}/videos/{str(video_id)}/source/{clean_name}"


class S3Client:
    def __init__(self):
        self.settings = get_settings()

        client_kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": self.settings.S3_REGION,
            "aws_access_key_id": self.settings.S3_ACCESS_KEY_ID,
            "aws_secret_access_key": self.settings.S3_SECRET_ACCESS_KEY,
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"}
            ),
        }

        if self.settings.S3_ENDPOINT_URL:
            client_kwargs["endpoint_url"] = self.settings.S3_ENDPOINT_URL

        self.client = boto3.client(**client_kwargs)

    def generate_presigned_put_url(
        self,
        storage_key: str,
        content_type: str,
        expires_in: int | None = None,
    ) -> str:
        """Generate a presigned PUT URL for single-part direct upload."""
        if expires_in is None:
            expires_in = self.settings.PRESIGNED_URL_EXPIRY_SECONDS

        url = self.client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.settings.S3_BUCKET_NAME,
                "Key": storage_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

        # If public endpoint is configured differently from internal docker endpoint (e.g. localhost:9000 vs minio:9000)
        if self.settings.S3_PUBLIC_ENDPOINT_URL and self.settings.S3_ENDPOINT_URL:
            if self.settings.S3_PUBLIC_ENDPOINT_URL != self.settings.S3_ENDPOINT_URL:
                url = url.replace(self.settings.S3_ENDPOINT_URL, self.settings.S3_PUBLIC_ENDPOINT_URL)

        return url

    def create_multipart_upload(self, storage_key: str, content_type: str) -> str:
        """Initialize a multipart upload and return the UploadId."""
        response = self.client.create_multipart_upload(
            Bucket=self.settings.S3_BUCKET_NAME,
            Key=storage_key,
            ContentType=content_type,
        )
        return response["UploadId"]

    def generate_presigned_part_url(
        self,
        storage_key: str,
        upload_id: str,
        part_number: int,
        expires_in: int | None = None,
    ) -> str:
        """Generate a presigned PUT URL for a specific multipart upload part."""
        if expires_in is None:
            expires_in = self.settings.PRESIGNED_URL_EXPIRY_SECONDS

        url = self.client.generate_presigned_url(
            ClientMethod="upload_part",
            Params={
                "Bucket": self.settings.S3_BUCKET_NAME,
                "Key": storage_key,
                "UploadId": upload_id,
                "PartNumber": part_number,
            },
            ExpiresIn=expires_in,
        )

        if self.settings.S3_PUBLIC_ENDPOINT_URL and self.settings.S3_ENDPOINT_URL:
            if self.settings.S3_PUBLIC_ENDPOINT_URL != self.settings.S3_ENDPOINT_URL:
                url = url.replace(self.settings.S3_ENDPOINT_URL, self.settings.S3_PUBLIC_ENDPOINT_URL)

        return url

    def complete_multipart_upload(
        self,
        storage_key: str,
        upload_id: str,
        parts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Complete a multipart upload given sorted parts [{'PartNumber': 1, 'ETag': '...'}]."""
        formatted_parts = [
            {"PartNumber": p.get("part_number", p.get("PartNumber")), "ETag": p.get("etag", p.get("ETag"))}
            for p in sorted(parts, key=lambda x: x.get("part_number", x.get("PartNumber", 0)))
        ]

        response = self.client.complete_multipart_upload(
            Bucket=self.settings.S3_BUCKET_NAME,
            Key=storage_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": formatted_parts},
        )
        return response

    def abort_multipart_upload(self, storage_key: str, upload_id: str) -> None:
        """Abort a multipart upload to clean up unused parts."""
        self.client.abort_multipart_upload(
            Bucket=self.settings.S3_BUCKET_NAME,
            Key=storage_key,
            UploadId=upload_id,
        )

    def check_object_exists(self, storage_key: str) -> bool:
        """Check if an object exists in the S3 bucket using a HEAD request."""
        try:
            self.client.head_object(
                Bucket=self.settings.S3_BUCKET_NAME,
                Key=storage_key,
            )
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def generate_presigned_get_url(
        self,
        storage_key: str,
        expires_in: int | None = None,
        response_content_disposition: str | None = None,
    ) -> str:
        """Generate a presigned GET URL for downloading or streaming media."""
        if expires_in is None:
            expires_in = self.settings.PRESIGNED_URL_EXPIRY_SECONDS

        params: dict[str, Any] = {
            "Bucket": self.settings.S3_BUCKET_NAME,
            "Key": storage_key,
        }
        if response_content_disposition:
            params["ResponseContentDisposition"] = response_content_disposition

        url = self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

        if self.settings.S3_PUBLIC_ENDPOINT_URL and self.settings.S3_ENDPOINT_URL:
            if self.settings.S3_PUBLIC_ENDPOINT_URL != self.settings.S3_ENDPOINT_URL:
                url = url.replace(self.settings.S3_ENDPOINT_URL, self.settings.S3_PUBLIC_ENDPOINT_URL)

        return url

    def download_file_stream(self, storage_key: str, target_path: str, chunk_size: int = 8 * 1024 * 1024) -> None:
        """Stream download an object directly to a local file path in chunks."""
        response = self.client.get_object(Bucket=self.settings.S3_BUCKET_NAME, Key=storage_key)
        body = response["Body"]
        with open(target_path, "wb") as f:
            while True:
                chunk = body.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)

    def upload_file(self, file_path: str, storage_key: str, content_type: str | None = None) -> None:
        """Upload a local file to S3 with content type."""
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        self.client.upload_file(
            Filename=file_path,
            Bucket=self.settings.S3_BUCKET_NAME,
            Key=storage_key,
            ExtraArgs=extra_args if extra_args else None,
        )

    def upload_json(self, data: Any, storage_key: str) -> None:
        """Serialize data to JSON and upload to S3."""
        import json
        payload_bytes = json.dumps(data, indent=2).encode("utf-8")
        self.client.put_object(
            Bucket=self.settings.S3_BUCKET_NAME,
            Key=storage_key,
            Body=payload_bytes,
            ContentType="application/json",
        )

    def download_json(self, storage_key: str) -> Any:
        """Download and parse a JSON object from S3."""
        import json
        response = self.client.get_object(Bucket=self.settings.S3_BUCKET_NAME, Key=storage_key)
        body = response["Body"].read().decode("utf-8")
        return json.loads(body)

    def delete_object(self, storage_key: str) -> None:
        """Delete an object from S3 if it exists."""
        try:
            self.client.delete_object(Bucket=self.settings.S3_BUCKET_NAME, Key=storage_key)
        except Exception:
            pass


_s3_client_instance: S3Client | None = None


def get_s3_client() -> S3Client:
    global _s3_client_instance
    if _s3_client_instance is None:
        _s3_client_instance = S3Client()
    return _s3_client_instance
