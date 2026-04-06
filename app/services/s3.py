import uuid
import logging
import boto3
from botocore.exceptions import ClientError
from app.config.settings import settings

logger = logging.getLogger(__name__)

def create_presigned_upload_url(file_name: str, file_type: str, max_size: int, expiration: int = 300) -> dict | None:
    """
    Generate a pre-signed POST policy to upload a file directly to S3 with strict constraints.
    """
    if not settings.S3_BUCKET_NAME:
        logger.error("S3_BUCKET_NAME is not configured.")
        return None

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )

    # Generate a unique filename to prevent overwrites
    s3_key = f"uploads/{uuid.uuid4()}-{file_name}"

    conditions = [
        ["content-length-range", 0, max_size],
        ["eq", "$Content-Type", file_type]
    ]

    try:
        response = s3_client.generate_presigned_post(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Fields={"Content-Type": file_type},
            Conditions=conditions,
            ExpiresIn=expiration
        )
        # Return both the URL to upload to, and the final public URL to save in the DB
        return {
            "upload_url": response["url"],
            "upload_fields": response["fields"],
            "file_key": s3_key,
            "file_url": f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
        }
    except ClientError as e:
        logger.error(f"Error generating presigned URL: {e}")
        return None

def verify_s3_file(file_key: str) -> bool:
    """Check if a file actually exists in S3."""
    if not settings.S3_BUCKET_NAME:
        return False
    s3_client = boto3.client("s3", aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, region_name=settings.AWS_REGION)
    try:
        s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=file_key)
        return True
    except ClientError:
        return False