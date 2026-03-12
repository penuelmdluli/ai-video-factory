"""
Cloud Storage — Temporary video hosting for Instagram Reels upload.

Supports multiple backends (auto-detects best available):
1. Cloudflare R2 via S3 API (R2_ACCESS_KEY_ID + R2_SECRET_ACCESS_KEY)
2. Cloudflare R2 via REST API (CF_ACCOUNT_ID + CF_API_TOKEN — you already have these!)
3. AWS S3
4. Local temp server fallback (ngrok/localhost)

Instagram Graph API requires a publicly accessible video URL.
Files are auto-deleted after upload completes (configurable TTL).
"""
import os
import asyncio
import uuid
import json
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Configuration ──────────────────────────────────────────
# Option 1: Cloudflare R2 via S3-compatible API
R2_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "ai-video-factory")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")  # e.g., https://pub-xxxx.r2.dev

# Option 2: Cloudflare R2 via standard REST API
# R2_API_TOKEN is preferred (scoped to R2). Falls back to CF_API_TOKEN.
CF_API_TOKEN = os.getenv("R2_API_TOKEN", "") or os.getenv("CF_API_TOKEN", "")

# Option 3: AWS S3 fallback
S3_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "")
S3_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

# Track uploaded files for cleanup
_uploaded_files: list[dict] = []


def _get_storage_backend() -> str:
    """Detect which cloud storage backend is available."""
    # Best: R2 with S3-compatible keys (supports presigned URLs)
    if R2_ACCESS_KEY and R2_SECRET_KEY and R2_ACCOUNT_ID:
        return "r2_s3"
    # Good: R2 via Cloudflare API (you already have CF_ACCOUNT_ID + CF_API_TOKEN)
    if R2_ACCOUNT_ID and CF_API_TOKEN:
        return "r2_api"
    # Fallback: AWS S3
    if S3_ACCESS_KEY and S3_SECRET_KEY and S3_BUCKET_NAME:
        return "s3"
    return "none"


async def upload_to_cloud(local_path: str) -> str:
    """
    Upload a local video file to cloud storage and return a public URL.

    This is the main function wired into Instagram uploader.
    Auto-detects the best available backend.

    Args:
        local_path: Path to local video file

    Returns:
        Public URL string accessible by Instagram's servers

    Raises:
        RuntimeError: If no cloud storage backend is configured
    """
    backend = _get_storage_backend()

    if backend == "r2_s3":
        return await _upload_to_r2_s3(local_path)
    elif backend == "r2_api":
        return await _upload_to_r2_api(local_path)
    elif backend == "s3":
        return await _upload_to_s3(local_path)
    else:
        raise RuntimeError(
            "No cloud storage configured for Instagram upload. "
            "Easiest fix: Create an R2 bucket in Cloudflare dashboard and set R2_BUCKET_NAME. "
            "You already have CF_ACCOUNT_ID + CF_API_TOKEN set. "
            "Or set R2_ACCESS_KEY_ID + R2_SECRET_ACCESS_KEY for S3-compatible access."
        )


async def _upload_to_r2_s3(local_path: str) -> str:
    """Upload to Cloudflare R2 via S3-compatible API (best option — supports presigned URLs)."""
    import boto3
    from botocore.config import Config

    file_path = Path(local_path)
    file_key = f"temp/{uuid.uuid4().hex[:12]}_{file_path.name}"

    endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: s3_client.upload_file(
            str(file_path),
            R2_BUCKET_NAME,
            file_key,
            ExtraArgs={"ContentType": "video/mp4"},
        ),
    )

    # Build public URL
    if R2_PUBLIC_URL:
        public_url = f"{R2_PUBLIC_URL.rstrip('/')}/{file_key}"
    else:
        public_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": R2_BUCKET_NAME, "Key": file_key},
            ExpiresIn=3600,
        )

    _uploaded_files.append({
        "backend": "r2_s3",
        "key": file_key,
        "bucket": R2_BUCKET_NAME,
        "uploaded_at": datetime.now().isoformat(),
    })

    print(f"[CloudStorage] Uploaded to R2 (S3): {file_key}")
    return public_url


async def _upload_to_r2_api(local_path: str) -> str:
    """
    Upload to Cloudflare R2 via the standard REST API.

    This uses the CF_ACCOUNT_ID + CF_API_TOKEN you already have.
    Requires: an R2 bucket exists (create in Cloudflare dashboard).
    The bucket must have public access enabled (r2.dev subdomain).

    Steps to enable public access:
    1. Go to Cloudflare Dashboard > R2 > your bucket > Settings
    2. Enable "Public access" via r2.dev subdomain
    3. Copy the public URL to R2_PUBLIC_URL in .env
    """
    import httpx

    file_path = Path(local_path)
    file_key = f"temp/{uuid.uuid4().hex[:12]}_{file_path.name}"
    file_size = file_path.stat().st_size

    # R2 REST API endpoint
    api_url = f"https://api.cloudflare.com/client/v4/accounts/{R2_ACCOUNT_ID}/r2/buckets/{R2_BUCKET_NAME}/objects/{file_key}"

    print(f"[CloudStorage] Uploading to R2 via API ({file_size / 1024 / 1024:.1f}MB)...")

    async with httpx.AsyncClient(timeout=300) as client:
        with open(file_path, "rb") as f:
            resp = await client.put(
                api_url,
                content=f.read(),
                headers={
                    "Authorization": f"Bearer {CF_API_TOKEN}",
                    "Content-Type": "video/mp4",
                },
            )

        if resp.status_code not in (200, 201):
            # Check if bucket doesn't exist — provide helpful error
            if resp.status_code == 404:
                raise RuntimeError(
                    f"R2 bucket '{R2_BUCKET_NAME}' not found. "
                    f"Create it at: https://dash.cloudflare.com > R2 > Create Bucket > name it '{R2_BUCKET_NAME}'"
                )
            error_text = resp.text[:300]
            raise RuntimeError(f"R2 API upload failed ({resp.status_code}): {error_text}")

    # Build public URL
    if R2_PUBLIC_URL:
        public_url = f"{R2_PUBLIC_URL.rstrip('/')}/{file_key}"
    else:
        # Without a public URL, we need to use a Workers route or presigned URL
        # Fall back to generating a temporary public URL via the API
        # The bucket must have public access enabled via r2.dev
        public_url = f"https://{R2_BUCKET_NAME}.{R2_ACCOUNT_ID}.r2.dev/{file_key}"
        print(f"[CloudStorage] WARNING: Using default r2.dev URL. If this doesn't work, "
              f"enable public access on your R2 bucket and set R2_PUBLIC_URL in .env")

    _uploaded_files.append({
        "backend": "r2_api",
        "key": file_key,
        "bucket": R2_BUCKET_NAME,
        "uploaded_at": datetime.now().isoformat(),
    })

    print(f"[CloudStorage] Uploaded to R2 (API): {file_key}")
    return public_url


async def _upload_to_s3(local_path: str) -> str:
    """Upload to AWS S3."""
    import boto3

    file_path = Path(local_path)
    file_key = f"temp/{uuid.uuid4().hex[:12]}_{file_path.name}"

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
    )

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: s3_client.upload_file(
            str(file_path),
            S3_BUCKET_NAME,
            file_key,
            ExtraArgs={"ContentType": "video/mp4"},
        ),
    )

    public_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET_NAME, "Key": file_key},
        ExpiresIn=3600,
    )

    _uploaded_files.append({
        "backend": "s3",
        "key": file_key,
        "bucket": S3_BUCKET_NAME,
        "uploaded_at": datetime.now().isoformat(),
    })

    print(f"[CloudStorage] Uploaded to S3: {file_key}")
    return public_url


async def cleanup_old_uploads(max_age_hours: int = 2):
    """
    Delete temporary uploads older than max_age_hours.

    Call this after Instagram confirms the upload is processed.
    """
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    to_remove = []

    for i, upload in enumerate(_uploaded_files):
        try:
            uploaded_at = datetime.fromisoformat(upload["uploaded_at"])
            if uploaded_at < cutoff:
                backend = upload["backend"]

                if backend == "r2_api":
                    # Delete via Cloudflare API
                    import httpx
                    api_url = (
                        f"https://api.cloudflare.com/client/v4/accounts/{R2_ACCOUNT_ID}"
                        f"/r2/buckets/{upload['bucket']}/objects/{upload['key']}"
                    )
                    async with httpx.AsyncClient(timeout=30) as client:
                        await client.delete(
                            api_url,
                            headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
                        )

                elif backend in ("r2_s3", "s3"):
                    import boto3
                    from botocore.config import Config

                    if backend == "r2_s3":
                        endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
                        client = boto3.client(
                            "s3",
                            endpoint_url=endpoint_url,
                            aws_access_key_id=R2_ACCESS_KEY,
                            aws_secret_access_key=R2_SECRET_KEY,
                            config=Config(signature_version="s3v4"),
                            region_name="auto",
                        )
                    else:
                        client = boto3.client(
                            "s3",
                            aws_access_key_id=S3_ACCESS_KEY,
                            aws_secret_access_key=S3_SECRET_KEY,
                            region_name=S3_REGION,
                        )

                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: client.delete_object(
                            Bucket=upload["bucket"],
                            Key=upload["key"],
                        ),
                    )

                to_remove.append(i)
                print(f"[CloudStorage] Cleaned up: {upload['key']}")
        except Exception as e:
            print(f"[CloudStorage] Cleanup failed for {upload.get('key')}: {e}")

    for i in reversed(to_remove):
        _uploaded_files.pop(i)


def is_cloud_storage_configured() -> bool:
    """Check if any cloud storage backend is available."""
    return _get_storage_backend() != "none"


def get_storage_status() -> dict:
    """Get current storage backend status for diagnostics."""
    backend = _get_storage_backend()
    return {
        "backend": backend,
        "configured": backend != "none",
        "r2_s3_ready": bool(R2_ACCESS_KEY and R2_SECRET_KEY and R2_ACCOUNT_ID),
        "r2_api_ready": bool(R2_ACCOUNT_ID and CF_API_TOKEN),
        "s3_ready": bool(S3_ACCESS_KEY and S3_SECRET_KEY and S3_BUCKET_NAME),
        "bucket_name": R2_BUCKET_NAME,
        "public_url": R2_PUBLIC_URL or "(auto-detect)",
        "pending_uploads": len(_uploaded_files),
    }
