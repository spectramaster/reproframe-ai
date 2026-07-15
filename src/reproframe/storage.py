from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ArtifactStore(ABC):
    @abstractmethod
    def put_bytes(self, key: str, payload: bytes, content_type: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_bytes(self, key: str) -> tuple[bytes, str]:
        raise NotImplementedError

    @abstractmethod
    def list_keys(self, prefix: str = "") -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def url_for(self, key: str) -> str:
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
        return self.url_for(key)

    def get_bytes(self, key: str) -> tuple[bytes, str]:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("artifact key escapes configured root")
        suffix = path.suffix.casefold()
        content_types = {
            ".json": "application/json",
            ".svg": "image/svg+xml",
            ".zip": "application/zip",
        }
        return path.read_bytes(), content_types.get(suffix, "application/octet-stream")

    def list_keys(self, prefix: str = "") -> list[str]:
        normalized = prefix.strip("/")
        base = (self.root / normalized).resolve() if normalized else self.root
        if base != self.root and self.root not in base.parents:
            raise ValueError("artifact prefix escapes configured root")
        if base.is_file():
            return [base.relative_to(self.root).as_posix()]
        if not base.exists():
            return []
        return sorted(
            path.relative_to(self.root).as_posix()
            for path in base.rglob("*")
            if path.is_file()
        )

    def url_for(self, key: str) -> str:
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
        return self.url_for(key)

    def get_bytes(self, key: str) -> tuple[bytes, str]:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read(), response.get("ContentType", "application/octet-stream")

    def list_keys(self, prefix: str = "") -> list[str]:
        keys: list[str] = []
        token: str | None = None
        while True:
            params = {"Bucket": self.bucket, "Prefix": prefix, "MaxKeys": 1000}
            if token:
                params["ContinuationToken"] = token
            response = self.client.list_objects_v2(**params)
            keys.extend(item["Key"] for item in response.get("Contents", []))
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")
            if not token:
                break
        return sorted(keys)

    def url_for(self, key: str) -> str:
        return f"/api/artifacts/{key}"
