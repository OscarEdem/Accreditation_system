import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.s3 import create_presigned_upload_url, verify_s3_file
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

logger = logging.getLogger(__name__)

ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"]
PHOTO_MAX_SIZE = 2 * 1024 * 1024  # 2 MB
DOC_MAX_SIZE = 5 * 1024 * 1024    # 5 MB

class PresignedUrlRequest(BaseModel):
    file_name: str
    file_type: str
    file_size: int
    is_photo: bool = False

class PresignedUrlResponse(BaseModel):
    upload_url: str
    upload_fields: dict
    file_key: str
    file_url: str

class ConfirmUploadRequest(BaseModel):
    file_key: str

@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def get_presigned_url(
    request: PresignedUrlRequest,
    current_user: User = Depends(get_current_user)
):
    max_allowed_size = PHOTO_MAX_SIZE if request.is_photo else DOC_MAX_SIZE

    if request.file_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: JPEG, PNG, WEBP, PDF.")
        
    if request.file_size > max_allowed_size:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {max_allowed_size // (1024 * 1024)}MB.")
        
    logger.info(f"User {current_user.id} requested pre-signed S3 URL for {request.file_name}")
    
    url_data = create_presigned_upload_url(file_name=request.file_name, file_type=request.file_type, max_size=max_allowed_size)
    if not url_data:
        raise HTTPException(status_code=500, detail="Could not generate S3 upload URL")
    
    return PresignedUrlResponse(**url_data)

@router.post("/confirm")
async def confirm_upload(
    request: ConfirmUploadRequest,
    current_user: User = Depends(get_current_user)
):
    is_valid = verify_s3_file(request.file_key)
    if not is_valid:
        raise HTTPException(status_code=404, detail="File not found in S3. Upload may have failed.")
        
    return {"status": "confirmed", "file_key": request.file_key}