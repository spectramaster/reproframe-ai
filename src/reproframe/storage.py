from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ArtifactStore(ABC):
    @abstractmethod
    def put_bytes(self, key: str, payload: bytes, content_type: str) -> str:
        raise NotImplementedError


class LocalArtifactStore(ArtifactStore):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, key: str, payload: bytes, content_type: str) -> str:
        del content_type
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("artifact key escapes configured root")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return f"/artifacts/{key}"


class B2ArtifactStore(ArtifactStore):
    """Narrow Backblaze B2 writer using the official S3-compatible surface."""

    def __init__(
        self,
        bucket: str,
        region: str,
        *,
        key_id: str,
        app_key: str,
    ) -> None:
        import boto3

        self.bucket = bucket
        self.region = region
        self.endpoint = f"https://s3.{region}.backblazeb2.com"
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            region_name=region,
            aws_access_key_id=key_id,
            aws_secret_access_key=app_key,
        )

    def put_bytes(self, key: str, payload: bytes, content_type: str) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=payload,
            ContentType=content_type,
        )
        return f"https://{self.bucket}.s3.{self.region}.backblazeb2.com/{key}"
