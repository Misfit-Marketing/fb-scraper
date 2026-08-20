"""
Uploads scraped ad media (image or video) to S3 so it survives after
Facebook's original CDN link expires.

Requires these env vars (see README):
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_REGION          (optional, defaults to us-east-1)
    S3_BUCKET_NAME
    S3_MEDIA_PREFIX     (optional, defaults to "competitors-creatives" — the folder inside the bucket)

Keys are deterministic — one object per ad, named after its Library ID
(`<S3_MEDIA_PREFIX>/<library_id><ext>`) — so re-running a scrape never
creates duplicate S3 objects, and an ad whose media is already in S3 is
skipped instead of re-downloaded.
"""
from __future__ import annotations

import mimetypes
import os
import urllib.parse

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError

S3_STORAGE_CLASS = os.getenv("S3_STORAGE_CLASS", "STANDARD_IA")
S3_CACHE_CONTROL = "public, max-age=31536000, immutable"  # keys are content-addressed by library_id — never change under the same key
S3_MEDIA_PREFIX = os.getenv("S3_MEDIA_PREFIX", "competitors-creatives").strip("/")  # folder inside the bucket

_VALID_MEDIA_EXTS = {".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".gif", ".webp"}


def get_s3_client():
    return boto3.client(
        "s3",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def _public_url(bucket: str, key: str, region: str) -> str:
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def _guess_extension(url: str, content_type: str | None) -> str:
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    if ext in _VALID_MEDIA_EXTS:
        return ext
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return guessed
    return ".mp4" if content_type and content_type.startswith("video") else ".jpg"


def _key_exists(s3_client, bucket: str, key: str) -> bool:
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


def upload_media_to_s3(media_url: str, library_id: str, s3_client, bucket: str) -> str | None:
    """
    Downloads `media_url` (image or video) and streams it into S3 under a key
    derived from `library_id`. Returns the permanent S3 URL, or None on
    failure. If the object already exists (from a previous run), the URL is
    returned without re-uploading.
    """
    region = os.getenv("AWS_REGION", "us-east-1")

    try:
        with requests.get(media_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            content_type = (r.headers.get("Content-Type") or "").split(";")[0].strip() or "application/octet-stream"
            key = f"{S3_MEDIA_PREFIX}/{library_id}{_guess_extension(media_url, content_type)}"

            if _key_exists(s3_client, bucket, key):
                return _public_url(bucket, key, region)

            s3_client.upload_fileobj(
                r.raw,
                bucket,
                key,
                ExtraArgs={
                    "ContentType": content_type,
                    "StorageClass": S3_STORAGE_CLASS,
                    "CacheControl": S3_CACHE_CONTROL,
                },
            )
        return _public_url(bucket, key, region)

    except (ClientError, BotoCoreError, requests.RequestException) as e:
        print(f"  [s3] failed to upload media for ad {library_id}: {e}")
        return None


def attach_s3_media_urls(ads: list[dict]) -> None:
    """
    For every ad with both a media_url and a library_id, uploads the media
    to S3 and sets ad["s3_media_url"] to the permanent S3 link, in place.
    Ads missing either field are left untouched (s3_media_url stays unset).

    No-ops (with a warning) if S3_BUCKET_NAME isn't configured, so local
    runs / workflows without AWS credentials aren't broken by this step.
    """
    bucket = os.getenv("S3_BUCKET_NAME")
    if not bucket:
        print("  [s3] S3_BUCKET_NAME not set — skipping media upload.")
        return

    s3_client = get_s3_client()

    for ad in ads:
        media_url = ad.get("media_url")
        library_id = ad.get("library_id")
        if not media_url or not library_id:
            continue

        print(f"  [s3] uploading media for ad {library_id}...")
        ad["s3_media_url"] = upload_media_to_s3(media_url, library_id, s3_client, bucket)
