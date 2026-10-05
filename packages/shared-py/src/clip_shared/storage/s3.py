import re
import uuid
from typing import Dict, List, Optional, Any
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
        
        client_kwargs: Dict[str, Any] = {
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
        expires_in: Optional[int] = None,
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
        expires_in: Optional[int] = None,
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
        parts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
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

    def get_object_metadata(self, storage_key: str) -> Dict[str, Any]:
        """Get object metadata / size."""
        return self.client.head_object(
            Bucket=self.settings.S3_BUCKET_NAME,
            Key=storage_key,
        )


_s3_client_instance: Optional[S3Client] = None


def get_s3_client() -> S3Client:
    global _s3_client_instance
    if _s3_client_instance is None:
        _s3_client_instance = S3Client()
    return _s3_client_instance
