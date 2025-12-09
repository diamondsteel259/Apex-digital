"""Storage layer for transcript persistence (local filesystem or S3)."""

from __future__ import annotations

import asyncio
import functools
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)


class TranscriptStorage:
    """Handles transcript storage to local filesystem or S3."""

    def __init__(self) -> None:
        self.storage_type = os.getenv("TRANSCRIPT_STORAGE_TYPE", "local").lower()
        self.local_path = Path(os.getenv("TRANSCRIPT_LOCAL_PATH", "transcripts"))
        
        self.s3_bucket: Optional[str] = os.getenv("S3_BUCKET")
        self.s3_region: Optional[str] = os.getenv("S3_REGION", "us-east-1")
        self.s3_access_key: Optional[str] = os.getenv("S3_ACCESS_KEY")
        self.s3_secret_key: Optional[str] = os.getenv("S3_SECRET_KEY")
        
        self._s3_client = None
        self._initialized = False
        self._validation_warnings_issued = False
        
        # Validate configuration immediately
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """
        Validate storage configuration and normalize settings.
        
        Checks that TRANSCRIPT_STORAGE_TYPE is valid ('local' or 's3') and verifies
        required S3 environment variables are present if S3 is selected. Logs warnings
        and falls back to local storage if configuration is invalid.
        """
        # Normalize storage_type to only allow 'local' or 's3'
        if self.storage_type not in ("local", "s3"):
            logger.warning(
                f"Unknown storage type '{self.storage_type}', only 'local' and 's3' are supported. "
                "Defaulting to 'local'."
            )
            self.storage_type = "local"
            self._validation_warnings_issued = True
            return
        
        # Only validate S3 if that's what the user wants
        if self.storage_type == "s3":
            missing_creds = []
            if not self.s3_bucket:
                missing_creds.append("S3_BUCKET")
            if not self.s3_access_key:
                missing_creds.append("S3_ACCESS_KEY")
            if not self.s3_secret_key:
                missing_creds.append("S3_SECRET_KEY")
            
            if not BOTO3_AVAILABLE:
                logger.warning(
                    "⚠️ S3 storage selected but boto3 is not installed. "
                    "Install with: pip install -r requirements-optional.txt"
                )
                logger.warning("Falling back to local transcript storage.")
                self.storage_type = "local"
                self._validation_warnings_issued = True
            elif missing_creds:
                logger.warning(
                    f"⚠️ S3 storage selected but missing required environment variables: {', '.join(missing_creds)}. "
                    "Please set all required S3_* environment variables."
                )
                logger.warning("Falling back to local transcript storage.")
                self.storage_type = "local"
                self._validation_warnings_issued = True

    def _initialize_local(self) -> None:
        """
        Initialize local storage directory.
        
        Creates the local transcript directory if it doesn't exist, including
        any parent directories as needed.
        """
        if not self.local_path.exists():
            self.local_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created transcript storage directory: {self.local_path}")

    def _initialize_s3(self) -> None:
        """
        Initialize S3 client and verify bucket access.
        
        Creates boto3 S3 client with configured credentials and region, then
        verifies access to the bucket. Falls back to local storage if boto3
        is unavailable or credentials are missing.
        
        Raises:
            RuntimeError: If S3 initialization fails after all validations pass
        """
        if not BOTO3_AVAILABLE:
            logger.warning(
                "⚠️ S3 storage unavailable. boto3 is not installed. "
                "Install with: pip install -r requirements-optional.txt"
            )
            logger.warning("Falling back to local transcript storage.")
            self.storage_type = "local"
            self._initialize_local()
            return
        
        try:
            if not all([self.s3_bucket, self.s3_access_key, self.s3_secret_key]):
                raise RuntimeError(
                    "S3 storage requires S3_BUCKET, S3_ACCESS_KEY, and S3_SECRET_KEY environment variables"
                )
            
            self._s3_client = boto3.client(
                's3',
                region_name=self.s3_region,
                aws_access_key_id=self.s3_access_key,
                aws_secret_access_key=self.s3_secret_key,
            )
            
            self._s3_client.head_bucket(Bucket=self.s3_bucket)
            logger.info(f"Initialized S3 storage: bucket={self.s3_bucket}, region={self.s3_region}")
            
        except ClientError as e:
            raise RuntimeError(f"Failed to initialize S3 storage: {e}")

    def initialize(self) -> None:
        """
        Initialize storage backend based on configuration.
        
        Sets up either local filesystem storage or S3 storage depending on
        TRANSCRIPT_STORAGE_TYPE setting. If initialization fails, falls back to
        local storage. Idempotent - safe to call multiple times.
        """
        if self._initialized:
            return

        # If we already validated and found issues, log a single startup warning
        if self._validation_warnings_issued:
            logger.warning(f"Transcript storage initialization: using {self.storage_type} storage (fallback due to configuration issues)")

        if self.storage_type == "s3":
            try:
                self._initialize_s3()
            except RuntimeError as e:
                # Only warn if we haven't already warned during validation
                if not self._validation_warnings_issued:
                    logger.warning(f"Failed to initialize S3 storage: {e}")
                    logger.warning("Falling back to local transcript storage.")
                self.storage_type = "local"
                self._initialize_local()
        else:
            # Local storage
            self._initialize_local()
        
        self._initialized = True
        logger.info(f"Transcript storage initialized: {self.storage_type}")

    async def save_transcript(
        self,
        ticket_id: int,
        channel_name: str,
        content: str,
    ) -> Tuple[str, int]:
        """
        Save transcript to configured storage backend (local filesystem or S3).
        
        Creates a transcript file and saves it to either local storage or S3 based
        on configuration. If S3 storage is unavailable, falls back to local storage.
        The filename is constructed from ticket_id and channel_name.
        
        Args:
            ticket_id: Unique identifier for the ticket
            channel_name: Name of the Discord channel for the transcript
            content: Transcript content as string (will be UTF-8 encoded)
        
        Returns:
            Tuple of (storage_path, file_size_bytes) where storage_path is the
            local filesystem path or S3 key, and file_size_bytes is the size
            of the saved content in bytes
        
        Raises:
            Exception: If transcript cannot be saved to either storage backend
        """
        if not self._initialized:
            self.initialize()

        filename = f"ticket-{ticket_id}-{channel_name}.html"
        content_bytes = content.encode("utf-8")
        file_size = len(content_bytes)

        if self.storage_type == "s3":
            return await self._save_to_s3(filename, content_bytes, file_size)
        else:
            return await self._save_to_local(filename, content_bytes, file_size)

    async def _save_to_local(
        self,
        filename: str,
        content_bytes: bytes,
        file_size: int,
    ) -> Tuple[str, int]:
        """
        Save transcript to local filesystem.
        
        Writes content to a file in the configured local transcript directory.
        Creates the directory if it doesn't exist.
        
        Args:
            filename: Name of the file to create
            content_bytes: File content as bytes
            file_size: Size of content in bytes (for return value)
        
        Returns:
            Tuple of (file_path_str, file_size_bytes)
        
        Raises:
            OSError: If unable to write file to filesystem
            Exception: For other unexpected errors during save
        """
        file_path = self.local_path / filename
        
        try:
            file_path.write_bytes(content_bytes)
            logger.info(f"Saved transcript to local storage: {file_path}")
            return str(file_path), file_size
        except Exception as e:
            logger.error(f"Failed to save transcript to local storage: {e}")
            raise

    async def _save_to_s3(
        self,
        filename: str,
        content_bytes: bytes,
        file_size: int,
    ) -> Tuple[str, int]:
        """
        Save transcript to S3 storage.
        
        Uploads content to S3 bucket with HTML content type. If S3 is unavailable
        or upload fails, automatically falls back to local storage.
        
        Args:
            filename: Name of the file to create
            content_bytes: File content as bytes
            file_size: Size of content in bytes (for return value)
        
        Returns:
            Tuple of (s3_key, file_size_bytes) or local path if fallback occurs
        
        Raises:
            ClientError: S3 client errors are caught and logged (fallback to local storage)
            Exception: Other unexpected errors are caught and logged (fallback to local storage)
        """
        if not BOTO3_AVAILABLE or not self._s3_client:
            logger.warning(
                "S3 storage not available. Falling back to local storage for: %s", filename
            )
            return await self._save_to_local(filename, content_bytes, file_size)
        
        try:
            s3_key = f"transcripts/{filename}"
            
            upload_partial = functools.partial(
                self._s3_client.put_object,
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=content_bytes,
                ContentType="text/html",
            )
            
            await asyncio.to_thread(upload_partial)
            logger.info(f"Saved transcript to S3: s3://{self.s3_bucket}/{s3_key}")
            return s3_key, file_size
            
        except ClientError as e:
            logger.error(f"Failed to save transcript to S3: {e}")
            logger.info("Falling back to local storage.")
            return await self._save_to_local(filename, content_bytes, file_size)
        except Exception as e:
            logger.error(f"Unexpected error saving to S3: {e}")
            logger.info("Falling back to local storage.")
            return await self._save_to_local(filename, content_bytes, file_size)

    async def retrieve_transcript(self, storage_path: str, storage_type: str) -> Optional[bytes]:
        """
        Retrieve transcript from storage backend.
        
        Loads transcript content from either local filesystem or S3 based on
        storage_type parameter.
        
        Args:
            storage_path: Filesystem path or S3 key where the transcript is stored
            storage_type: Storage backend type: 'local' for filesystem or 's3' for S3
        
        Returns:
            Transcript content as bytes if found, otherwise None
        """
        if storage_type == "s3":
            return await self._retrieve_from_s3(storage_path)
        else:
            return await self._retrieve_from_local(storage_path)

    async def _retrieve_from_local(self, file_path: str) -> Optional[bytes]:
        """
        Retrieve transcript from local filesystem.
        
        Reads file content synchronously but wrapped in the async context.
        Returns None if file not found or any error occurs during read.
        
        Args:
            file_path: Filesystem path to the transcript file
        
        Returns:
            File content as bytes if found, otherwise None
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"Transcript not found at local path: {file_path}")
                return None
            
            return path.read_bytes()
        except Exception as e:
            logger.error(f"Failed to retrieve transcript from local storage: {e}")
            return None

    async def _retrieve_from_s3(self, s3_key: str) -> Optional[bytes]:
        """
        Retrieve transcript from S3 storage.
        
        Fetches object from S3 bucket. Returns None if S3 is unavailable, key not found,
        or any error occurs during retrieval.
        
        Args:
            s3_key: S3 key (path) of the transcript object
        
        Returns:
            Object content as bytes if found, otherwise None
        """
        if not BOTO3_AVAILABLE or not self._s3_client:
            logger.warning(f"S3 storage not available. Cannot retrieve: {s3_key}")
            return None
        
        try:
            if not self._initialized:
                self.initialize()
            
            def _read_response_body(response):
                return response['Body'].read()
            
            get_partial = functools.partial(
                self._s3_client.get_object,
                Bucket=self.s3_bucket,
                Key=s3_key
            )
            
            response = await asyncio.to_thread(get_partial)
            return _read_response_body(response)
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"Transcript not found in S3: {s3_key}")
            else:
                logger.error(f"Failed to retrieve transcript from S3: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving from S3: {e}")
            return None

    def get_s3_presigned_url(self, s3_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for S3 object access (useful for sharing).
        
        Creates a temporary URL that allows anyone to access the S3 object without
        AWS credentials. URL expires after specified duration. Only works when
        storage_type is 's3'.
        
        Args:
            s3_key: S3 key (path) of the object to access
            expiration: URL expiration time in seconds (default: 3600 = 1 hour)
        
        Returns:
            Presigned URL string if successful, otherwise None
        """
        if not BOTO3_AVAILABLE or not self._s3_client:
            logger.warning("S3 storage not available. Cannot generate presigned URL.")
            return None
        
        try:
            if not self._initialized:
                self.initialize()
            
            if self.storage_type != "s3":
                return None
            
            url = self._s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.s3_bucket, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return None
