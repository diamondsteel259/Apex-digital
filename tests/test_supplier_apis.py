import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from apex_core.supplier_apis import NiceSMMPanelAPI, SupplierProduct

@pytest.fixture
def api_key():
    return "test_api_key_123"

@pytest.fixture
def nice_panel_api(api_key):
    return NiceSMMPanelAPI(api_key=api_key)

@pytest.mark.asyncio
async def test_get_services_success(nice_panel_api):
    """Test successful fetching and parsing of services."""
    
    # Mock response data
    mock_response_data = [
        {
            "service": "101",
            "name": "Instagram Followers [Max 10K]",
            "type": "Default",
            "category": "Instagram",
            "rate": "0.50",
            "min": "10",
            "max": "10000",
            "refill": True,
            "cancel": True
        },
        {
            "service": "102",
            "name": "YouTube Views",
            "type": "Default",
            "category": "YouTube",
            "rate": "1.20",
            "min": "100",
            "max": "50000",
            "refill": False,
            "cancel": False
        }
    ]

    # Mock aiohttp ClientSession
    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_response_data
        
        # mock_session.post needs to be a MagicMock that returns an async context manager
        # It cannot be an AsyncMock because we don't await session.post(), we async with it
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None
        
        mock_session.post = MagicMock(return_value=mock_post_ctx)

        # Execute
        products = await nice_panel_api.get_services()

        # Verify interactions
        assert len(products) == 2
        
        # Check first product
        p1 = products[0]
        assert isinstance(p1, SupplierProduct)
        assert p1.service_id == "101"
        assert p1.name == "Instagram Followers [Max 10K]"
        assert p1.category == "Instagram"
        assert p1.price_cents == 50  # 0.50 * 100
        assert p1.min_quantity == 10
        assert p1.max_quantity == 10000
        assert p1.refill_available is True
        assert p1.cancel_available is True

        # Check second product
        p2 = products[1]
        assert p2.service_id == "102"
        assert p2.price_cents == 120 # 1.20 * 100
        assert p2.refill_available is False

@pytest.mark.asyncio
async def test_get_services_api_error(nice_panel_api):
    """Test handling of API error response."""
    
    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_response = AsyncMock()
        mock_response.status = 500 # Server error
        
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None
        
        mock_session.post = MagicMock(return_value=mock_post_ctx)

        products = await nice_panel_api.get_services()
        
        assert products == []

@pytest.mark.asyncio
async def test_get_services_parsing_error_skips_item(nice_panel_api):
    """Test that individual item parsing errors don't fail the whole batch."""
    
    mock_response_data = [
        {
            "service": "101",
            "name": "Good Service",
            "rate": "0.50"
        },
        {
            "service": "102",
            "name": "Bad Service",
            "rate": "invalid_rate" # This should cause a parsing error
        }
    ]

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_response_data
        
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None
        
        mock_session.post = MagicMock(return_value=mock_post_ctx)

        products = await nice_panel_api.get_services()
        
        # Should get 1 valid product, skip the bad one
        assert len(products) == 1
        assert products[0].service_id == "101"

@pytest.mark.asyncio
async def test_create_order_success(nice_panel_api):
    """Test successful order creation."""
    
    mock_response_data = {"order": 12345}

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_response_data
        
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None
        
        mock_session.post = MagicMock(return_value=mock_post_ctx)

        result = await nice_panel_api.create_order(
            service_id="101",
            link="https://instagram.com/user",
            quantity=1000
        )
        
        assert result["order"] == 12345
        
        # Verify call arguments
        call_args = mock_session.post.call_args
        assert call_args[1]["data"]["action"] == "add"
        assert call_args[1]["data"]["service"] == "101"
        assert call_args[1]["data"]["link"] == "https://instagram.com/user"
        assert call_args[1]["data"]["quantity"] == 1000

@pytest.mark.asyncio
async def test_get_balance_success(nice_panel_api):
    """Test successful balance retrieval."""
    
    mock_response_data = {"balance": "15.50", "currency": "USD"}

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_response_data
        
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None
        
        mock_session.post = MagicMock(return_value=mock_post_ctx)

        balance = await nice_panel_api.get_balance()
        
        assert balance == 15.50
