from typing import Annotated
from fastapi import APIRouter, Depends, UploadFile, File
from app.api.deps import get_current_user
from app.models.user import User
from app.services.upload import UploadService

router = APIRouter()

@router.post("/image", status_code=201)
async def upload_image(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[User, Depends(get_current_user)]
):
    service = UploadService()
    file_url = await service.upload_image_to_s3(file)
    return {"url": file_url}