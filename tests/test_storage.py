"""Unit tests for storage module."""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apex_core.storage import TranscriptStorage, BOTO3_AVAILABLE


@pytest.fixture
def storage_local():
    """Create a TranscriptStorage instance configured for local storage."""
    with patch.dict(os.environ, {
        'TRANSCRIPT_STORAGE_TYPE': 'local',
        'TRANSCRIPT_LOCAL_PATH': 'test_transcripts'
    }):
        storage = TranscriptStorage()
        yield storage
        # Cleanup
        test_path = Path('test_transcripts')
        if test_path.exists():
            for file in test_path.iterdir():
                file.unlink()
            test_path.rmdir()


@pytest.fixture
def storage_s3():
    """Create a TranscriptStorage instance configured for S3 storage."""
    with patch.dict(os.environ, {
        'TRANSCRIPT_STORAGE_TYPE': 's3',
        'S3_BUCKET': 'test-bucket',
        'S3_REGION': 'us-east-1',
        'S3_ACCESS_KEY': 'test-access-key',
        'S3_SECRET_KEY': 'test-secret-key',
    }):
        storage = TranscriptStorage()
        yield storage


class TestLocalStorage:
    """Tests for local filesystem storage."""

    @pytest.mark.asyncio
    async def test_save_to_local(self, storage_local):
        """Test saving transcript to local filesystem."""
        storage_local.initialize()
        
        content = "<html><body>Test transcript</body></html>"
        path, size = await storage_local.save_transcript(
            ticket_id=123,
            channel_name="test-channel",
            content=content
        )
        
        assert Path(path).exists()
        assert size == len(content.encode('utf-8'))
        assert "ticket-123-test-channel.html" in path

    @pytest.mark.asyncio
    async def test_retrieve_from_local(self, storage_local):
        """Test retrieving transcript from local filesystem."""
        storage_local.initialize()
        
        content = "<html><body>Test transcript</body></html>"
        path, _ = await storage_local.save_transcript(
            ticket_id=456,
            channel_name="test-retrieve",
            content=content
        )
        
        retrieved = await storage_local.retrieve_transcript(path, "local")
        assert retrieved is not None
        assert retrieved.decode('utf-8') == content


@pytest.mark.skipif(not BOTO3_AVAILABLE, reason="boto3 not installed")
class TestS3Storage:
    """Tests for S3 storage."""

    @pytest.mark.asyncio
    async def test_save_to_s3_uses_partial(self, storage_s3):
        """Test that _save_to_s3 uses functools.partial and asyncio.to_thread."""
        mock_s3_client = MagicMock()
        mock_s3_client.put_object = MagicMock()
        mock_s3_client.head_bucket = MagicMock()
        
        storage_s3._s3_client = mock_s3_client
        storage_s3._initialized = True
        
        content = "<html><body>S3 test transcript</body></html>"
        content_bytes = content.encode('utf-8')
        
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = None
            
            path, size = await storage_s3._save_to_s3(
                filename="ticket-789-s3-test.html",
                content_bytes=content_bytes,
                file_size=len(content_bytes)
            )
            
            # Verify asyncio.to_thread was called
            assert mock_to_thread.called
            assert mock_to_thread.call_count == 1
            
            # Verify the partial function was created properly
            call_args = mock_to_thread.call_args
            partial_func = call_args[0][0]
            
            # Execute the partial to verify it calls put_object correctly
            partial_func()
            
            # Verify put_object was called with correct parameters
            mock_s3_client.put_object.assert_called_once_with(
                Bucket='test-bucket',
                Key='transcripts/ticket-789-s3-test.html',
                Body=content_bytes,
                ContentType='text/html'
            )
            
            assert path == 'transcripts/ticket-789-s3-test.html'
            assert size == len(content_bytes)

    @pytest.mark.asyncio
    async def test_save_to_s3_fallback_on_error(self, storage_s3):
        """Test that S3 errors fall back to local storage."""
        from botocore.exceptions import ClientError
        
        mock_s3_client = MagicMock()
        mock_s3_client.put_object = MagicMock(
            side_effect=ClientError({'Error': {'Code': 'AccessDenied'}}, 'PutObject')
        )
        
        storage_s3._s3_client = mock_s3_client
        storage_s3._initialized = True
        storage_s3.local_path = Path('test_transcripts_fallback')
        storage_s3.local_path.mkdir(parents=True, exist_ok=True)
        
        content = "<html><body>Fallback test</body></html>"
        content_bytes = content.encode('utf-8')
        
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            # Make to_thread raise the ClientError
            async def raise_error(func):
                func()
            
            mock_to_thread.side_effect = raise_error
            
            path, size = await storage_s3._save_to_s3(
                filename="ticket-fallback.html",
                content_bytes=content_bytes,
                file_size=len(content_bytes)
            )
            
            # Verify it fell back to local storage
            assert 'test_transcripts_fallback' in path
            assert Path(path).exists()
            
            # Cleanup
            Path(path).unlink()
            storage_s3.local_path.rmdir()

    @pytest.mark.asyncio
    async def test_retrieve_from_s3_uses_partial(self, storage_s3):
        """Test that _retrieve_from_s3 uses functools.partial."""
        mock_s3_client = MagicMock()
        mock_response = {
            'Body': MagicMock(read=MagicMock(return_value=b'test content'))
        }
        mock_s3_client.get_object = MagicMock(return_value=mock_response)
        
        storage_s3._s3_client = mock_s3_client
        storage_s3._initialized = True
        
        with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = mock_response
            
            result = await storage_s3._retrieve_from_s3('transcripts/test.html')
            
            # Verify asyncio.to_thread was called
            assert mock_to_thread.called
            
            # Verify the result
            assert result == b'test content'

    @pytest.mark.asyncio
    async def test_s3_not_available_fallback(self, storage_s3):
        """Test fallback when S3 client is not available."""
        storage_s3._s3_client = None
        storage_s3._initialized = True
        storage_s3.local_path = Path('test_transcripts_no_s3')
        storage_s3.local_path.mkdir(exist_ok=True)
        
        content = "<html><body>No S3 test</body></html>"
        content_bytes = content.encode('utf-8')
        
        path, size = await storage_s3._save_to_s3(
            filename="ticket-no-s3.html",
            content_bytes=content_bytes,
            file_size=len(content_bytes)
        )
        
        # Should fall back to local storage
        assert 'test_transcripts_no_s3' in path
        assert Path(path).exists()
        
        # Cleanup
        Path(path).unlink()
        storage_s3.local_path.rmdir()


class TestStorageInitialization:
    """Tests for storage initialization."""

    def test_local_storage_initialization(self):
        """Test local storage initializes correctly."""
        with patch.dict(os.environ, {
            'TRANSCRIPT_STORAGE_TYPE': 'local',
            'TRANSCRIPT_LOCAL_PATH': 'test_init_transcripts'
        }):
            storage = TranscriptStorage()
            storage.initialize()
            
            assert storage.storage_type == 'local'
            assert Path('test_init_transcripts').exists()
            
            # Cleanup
            Path('test_init_transcripts').rmdir()

    @pytest.mark.skipif(not BOTO3_AVAILABLE, reason="boto3 not installed")
    def test_s3_storage_initialization_missing_credentials(self):
        """Test S3 storage falls back to local when credentials are missing."""
        with patch.dict(os.environ, {
            'TRANSCRIPT_STORAGE_TYPE': 's3',
            'TRANSCRIPT_LOCAL_PATH': 'test_s3_fallback'
        }, clear=True):
            storage = TranscriptStorage()
            storage.initialize()
            
            # Should fall back to local
            assert storage.storage_type == 'local'
            
            # Cleanup
            if Path('test_s3_fallback').exists():
                Path('test_s3_fallback').rmdir()

    def test_validate_configuration_unknown_type(self):
        """Test validation catches unknown storage type and falls back to local."""
        with patch.dict(os.environ, {
            'TRANSCRIPT_STORAGE_TYPE': 'invalid_type',
        }), patch('apex_core.storage.logger') as mock_logger:
            storage = TranscriptStorage()
            
            # Should fall back to local immediately during __init__
            assert storage.storage_type == 'local'
            
            # Should log warning during __init__ (before initialize)
            mock_logger.warning.assert_called()
            warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
            assert any('Unknown storage type' in str(call) for call in warning_calls)

    def test_validate_configuration_s3_missing_credentials(self):
        """Test validation catches missing S3 credentials and falls back to local."""
        with patch.dict(os.environ, {
            'TRANSCRIPT_STORAGE_TYPE': 's3',
            # Missing all S3 credentials
        }, clear=True), patch('apex_core.storage.logger') as mock_logger:
            storage = TranscriptStorage()
            
            # Should fall back to local immediately during __init__
            assert storage.storage_type == 'local'
            
            # Should log warnings during __init__ (before initialize)
            mock_logger.warning.assert_called()
            warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
            # Check for either missing credentials warning OR boto3 not available warning
            has_missing_creds_warning = any('missing required environment variables' in str(call) for call in warning_calls)
            has_boto3_warning = any('boto3 is not installed' in str(call) for call in warning_calls)
            assert has_missing_creds_warning or has_boto3_warning, f"Expected warning about missing credentials or boto3, got: {warning_calls}"
            assert any('Falling back to local' in str(call) for call in warning_calls)
