import logging
import tempfile
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError, ReadTimeoutError

log = logging.getLogger(__name__)


class StorageError(Exception):
    def __init__(self, message: str, *, transient: bool) -> None:
        super().__init__(message)
        self.transient = transient


class MinioStorage:
    def __init__(self, endpoint: str, access_key: str, secret_key: str) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def download(self, bucket: str, object_key: str) -> Path:
        temp = tempfile.NamedTemporaryFile(prefix="omnidoc-", suffix=".pdf", delete=False)
        temp.close()
        destination = Path(temp.name)
        try:
            self._client.download_file(bucket, object_key, str(destination))
        except (EndpointConnectionError, ReadTimeoutError, ConnectionError) as exc:
            destination.unlink(missing_ok=True)
            raise StorageError(f"MinIO is unreachable for {object_key}", transient=True) from exc
        except ClientError as exc:
            destination.unlink(missing_ok=True)
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
            code = exc.response.get("Error", {}).get("Code", "")
            transient = status >= 500 or code in {"SlowDown", "ServiceUnavailable"}
            raise StorageError(f"Unable to download {object_key}: {code or status}", transient=transient) from exc
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        log.info("Downloaded s3://%s/%s", bucket, object_key)
        return destination
