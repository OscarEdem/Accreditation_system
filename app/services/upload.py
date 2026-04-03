import uuid
import boto3
from fastapi import UploadFile, HTTPException, status
from app.config.settings import settings

class UploadService:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.allowed_content_types = ["image/jpeg", "image/png", "image/webp"]
        self.max_file_size_mb = 5

    async def upload_image_to_s3(self, file: UploadFile) -> str:
        if not settings.S3_BUCKET_NAME:
            raise HTTPException(status_code=500, detail="S3 is not configured.")

        # 1. Validate File Type
        if file.content_type not in self.allowed_content_types:
            raise HTTPException(status_code=400, detail="Invalid file type. Only JPEG, PNG, and WEBP are allowed.")

        # 2. Check File Size securely by reading to end, then resetting the cursor
        file_size = len(await file.read())
        await file.seek(0)
        if file_size > (self.max_file_size_mb * 1024 * 1024):
            raise HTTPException(status_code=413, detail=f"File too large. Maximum allowed size is {self.max_file_size_mb}MB.")

        # 3. Sanitize Filename by generating a unique UUID
        file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        secure_file_name = f"uploads/{uuid.uuid4()}.{file_extension}"

        try:
            self.s3_client.upload_fileobj(file.file, settings.S3_BUCKET_NAME, secure_file_name)
            return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{secure_file_name}"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload to S3: {str(e)}")