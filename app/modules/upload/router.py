import os
import uuid
from fastapi import APIRouter, Depends, File, Form, UploadFile, Request
import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.dependencies import get_current_user, TokenPayload
from app.core.exceptions import ValidationError, BitenexException

router = APIRouter(tags=["Upload"])
settings = get_settings()

@router.post("/upload/file")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    folder: str = Form("general"),
    current_user: TokenPayload = Depends(get_current_user),
):
    """
    Upload a file.
    If S3 configuration is present, uploads to AWS S3.
    Otherwise, saves to local storage under /media/uploads/{folder}/
    """
    # Validate file extension
    if not file.filename:
        raise ValidationError(
            message="Tên tệp không hợp lệ.",
        )
        
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf", ".svg"]:
        raise ValidationError(
            message="Định dạng tệp không được hỗ trợ. Chỉ cho phép ảnh (jpg, png, webp, gif, svg) hoặc pdf.",
        )

    # Generate a unique file name
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    s3_key = f"uploads/{folder}/{unique_filename}"

    # Check S3 settings
    has_s3 = (
        settings.aws_access_key_id is not None
        and settings.aws_secret_access_key is not None
        and settings.aws_bucket_name is not None
        and settings.aws_access_key_id.strip() != ""
        and settings.aws_secret_access_key.strip() != ""
        and settings.aws_bucket_name.strip() != ""
    )

    if has_s3:
        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region,
            )
            
            # Read file content
            content = await file.read()
            
            # Upload to S3
            s3_client.put_object(
                Bucket=settings.aws_bucket_name,
                Key=s3_key,
                Body=content,
                ContentType=file.content_type or "application/octet-stream",
            )
            
            # Construct public URL
            url = f"https://{settings.aws_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
            return {"url": url}
            
        except ClientError as e:
            raise BitenexException(
                message=f"Lỗi khi tải tệp lên AWS S3: {str(e)}",
            )
        except Exception as e:
            raise BitenexException(
                message=f"Lỗi hệ thống khi tải tệp lên S3: {str(e)}",
            )
    else:
        # Fallback to local storage
        try:
            local_folder = os.path.join("media", "uploads", folder)
            os.makedirs(local_folder, exist_ok=True)
            
            local_filepath = os.path.join(local_folder, unique_filename)
            content = await file.read()
            
            with open(local_filepath, "wb") as f:
                f.write(content)
                
            # Build local URL
            base_url = str(request.base_url)
            if base_url.endswith("/"):
                base_url = base_url[:-1]
                
            url = f"{base_url}/media/uploads/{folder}/{unique_filename}"
            return {"url": url}
            
        except Exception as e:
            raise BitenexException(
                message=f"Lỗi khi lưu tệp cục bộ: {str(e)}",
            )
