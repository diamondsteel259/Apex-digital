"""Supplier API integration for automatic product import."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
import aiohttp
import json

from apex_core.logger import get_logger

logger = get_logger()


@dataclass
class SupplierProduct:
    """Product data from supplier API."""
    supplier_id: str
    supplier_name: str
    service_id: str
    name: str
    category: str
    price_cents: int  # Price from supplier in cents
    subcategory: Optional[str] = None
    min_quantity: Optional[int] = None
    max_quantity: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    refill_available: bool = False
    cancel_available: bool = True
    service_type: Optional[str] = None
    api_data: Optional[Dict[str, Any]] = None  # Raw API response for reference


class SupplierAPI:
    """Base class for supplier API integrations."""
    
    def __init__(self, api_key: str, api_url: str, supplier_name: str):
        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
        self.supplier_name = supplier_name
        self.supplier_id = supplier_name.lower().replace(' ', '_')
    
    async def get_services(self) -> List[SupplierProduct]:
        """Fetch all services from supplier API."""
        raise NotImplementedError
    
    async def create_order(self, service_id: str, link: str, quantity: int, **kwargs) -> Dict[str, Any]:
        """Create an order with the supplier."""
        raise NotImplementedError
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status from supplier."""
        raise NotImplementedError
    
    async def get_balance(self) -> float:
        """Get account balance from supplier."""
        raise NotImplementedError


class NiceSMMPanelAPI(SupplierAPI):
    """NiceSMMPanel API integration."""
    
    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            api_url="https://nicesmmpanel.com/api/v2",
            supplier_name="NiceSMMPanel"
        )
    
    async def get_services(self) -> List[SupplierProduct]:
        """Fetch services from NiceSMMPanel."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "services"
                }
                async with session.post(self.api_url, data=data) as response:
                    if response.status != 200:
                        logger.error(f"NiceSMMPanel API error: {response.status}")
                        return []
                    
                    services_data = await response.json()
                    products = []
                    
                    for service in services_data:
                        try:
                            # Parse price (rate is per 1000 or per unit, convert to cents)
                            rate = float(service.get("rate", "0"))
                            price_cents = int(rate * 100)  # Convert to cents (assuming rate is in dollars)
                            
                            # Parse category
                            category = service.get("category", "Uncategorized")
                            
                            products.append(SupplierProduct(
                                supplier_id=self.supplier_id,
                                supplier_name=self.supplier_name,
                                service_id=str(service.get("service", "")),
                                name=service.get("name", "Unknown Service"),
                                category=category,
                                subcategory=service.get("type", None),
                                price_cents=price_cents,
                                min_quantity=int(service.get("min", 0)) if service.get("min") else None,
                                max_quantity=int(service.get("max", 0)) if service.get("max") else None,
                                refill_available=service.get("refill", False),
                                cancel_available=service.get("cancel", True),
                                service_type=service.get("type", None),
                                api_data=service
                            ))
                        except Exception as e:
                            logger.error(f"Error parsing NiceSMMPanel service: {e}")
                            continue
                    
                    logger.info(f"Fetched {len(products)} products from {self.supplier_name}")
                    return products
                    
        except Exception as e:
            logger.error(f"Error fetching services from NiceSMMPanel: {e}", exc_info=True)
            return []
    
    async def create_order(self, service_id: str, link: str, quantity: int, **kwargs) -> Dict[str, Any]:
        """Create order with NiceSMMPanel."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "add",
                    "service": service_id,
                    "link": link,
                    "quantity": quantity
                }
                data.update(kwargs)
                
                async with session.post(self.api_url, data=data) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error creating order with NiceSMMPanel: {e}")
            return {"error": str(e)}
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status from NiceSMMPanel."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "status",
                    "order": order_id
                }
                async with session.post(self.api_url, data=data) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error getting order status from NiceSMMPanel: {e}")
            return {"error": str(e)}
    
    async def get_balance(self) -> float:
        """Get balance from NiceSMMPanel."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "balance"
                }
                async with session.post(self.api_url, data=data) as response:
                    result = await response.json()
                    return float(result.get("balance", 0))
        except Exception as e:
            logger.error(f"Error getting balance from NiceSMMPanel: {e}")
            return 0.0


class JustAnotherPanelAPI(SupplierAPI):
    """Just Another Panel API integration."""
    
    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            api_url="https://justanotherpanel.com/api/v2",
            supplier_name="Just Another Panel"
        )
    
    async def get_services(self) -> List[SupplierProduct]:
        """Fetch services from Just Another Panel."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "services"
                }
                async with session.post(self.api_url, data=data) as response:
                    if response.status != 200:
                        logger.error(f"Just Another Panel API error: {response.status}")
                        return []
                    
                    services_data = await response.json()
                    products = []
                    
                    for service in services_data:
                        try:
                            rate = float(service.get("rate", "0"))
                            price_cents = int(rate * 100)
                            
                            category = service.get("category", "Uncategorized")
                            
                            products.append(SupplierProduct(
                                supplier_id=self.supplier_id,
                                supplier_name=self.supplier_name,
                                service_id=str(service.get("service", "")),
                                name=service.get("name", "Unknown Service"),
                                category=category,
                                subcategory=service.get("type", None),
                                price_cents=price_cents,
                                min_quantity=int(service.get("min", 0)) if service.get("min") else None,
                                max_quantity=int(service.get("max", 0)) if service.get("max") else None,
                                refill_available=service.get("refill", False),
                                cancel_available=service.get("cancel", True),
                                service_type=service.get("type", None),
                                api_data=service
                            ))
                        except Exception as e:
                            logger.error(f"Error parsing Just Another Panel service: {e}")
                            continue
                    
                    logger.info(f"Fetched {len(products)} products from {self.supplier_name}")
                    return products
                    
        except Exception as e:
            logger.error(f"Error fetching services from Just Another Panel: {e}", exc_info=True)
            return []
    
    async def create_order(self, service_id: str, link: str, quantity: int, **kwargs) -> Dict[str, Any]:
        """Create order with Just Another Panel."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "add",
                    "service": service_id,
                    "link": link,
                    "quantity": quantity
                }
                data.update(kwargs)
                
                async with session.post(self.api_url, data=data) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error creating order with Just Another Panel: {e}")
            return {"error": str(e)}
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status from Just Another Panel."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "status",
                    "order": order_id
                }
                async with session.post(self.api_url, data=data) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error getting order status from Just Another Panel: {e}")
            return {"error": str(e)}
    
    async def get_balance(self) -> float:
        """Get balance from Just Another Panel."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "balance"
                }
                async with session.post(self.api_url, data=data) as response:
                    result = await response.json()
                    return float(result.get("balance", 0))
        except Exception as e:
            logger.error(f"Error getting balance from Just Another Panel: {e}")
            return 0.0


class MagicSMMAPI(SupplierAPI):
    """MagicSMM API integration."""
    
    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            api_url="https://magicsmm.com/api",
            supplier_name="MagicSMM"
        )
    
    async def get_services(self) -> List[SupplierProduct]:
        """Fetch services from MagicSMM."""
        # Similar structure to NiceSMMPanel
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "services"
                }
                async with session.post(self.api_url, data=data) as response:
                    if response.status != 200:
                        logger.error(f"MagicSMM API error: {response.status}")
                        return []
                    
                    services_data = await response.json()
                    products = []
                    
                    for service in services_data:
                        try:
                            rate = float(service.get("rate", "0"))
                            price_cents = int(rate * 100)
                            
                            category = service.get("category", "Uncategorized")
                            
                            products.append(SupplierProduct(
                                supplier_id=self.supplier_id,
                                supplier_name=self.supplier_name,
                                service_id=str(service.get("service", "")),
                                name=service.get("name", "Unknown Service"),
                                category=category,
                                subcategory=service.get("type", None),
                                price_cents=price_cents,
                                min_quantity=int(service.get("min", 0)) if service.get("min") else None,
                                max_quantity=int(service.get("max", 0)) if service.get("max") else None,
                                refill_available=service.get("refill", False),
                                cancel_available=service.get("cancel", True),
                                service_type=service.get("type", None),
                                api_data=service
                            ))
                        except Exception as e:
                            logger.error(f"Error parsing MagicSMM service: {e}")
                            continue
                    
                    logger.info(f"Fetched {len(products)} products from {self.supplier_name}")
                    return products
                    
        except Exception as e:
            logger.error(f"Error fetching services from MagicSMM: {e}", exc_info=True)
            return []
    
    async def create_order(self, service_id: str, link: str, quantity: int, **kwargs) -> Dict[str, Any]:
        """Create order with MagicSMM."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "add",
                    "service": service_id,
                    "link": link,
                    "quantity": quantity
                }
                data.update(kwargs)
                
                async with session.post(self.api_url, data=data) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error creating order with MagicSMM: {e}")
            return {"error": str(e)}
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status from MagicSMM."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "status",
                    "order": order_id
                }
                async with session.post(self.api_url, data=data) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error getting order status from MagicSMM: {e}")
            return {"error": str(e)}
    
    async def get_balance(self) -> float:
        """Get balance from MagicSMM."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "key": self.api_key,
                    "action": "balance"
                }
                async with session.post(self.api_url, data=data) as response:
                    result = await response.json()
                    return float(result.get("balance", 0))
        except Exception as e:
            logger.error(f"Error getting balance from MagicSMM: {e}")
            return 0.0


class PlatiMarketAPI(SupplierAPI):
    """Plati.market API integration."""
    
    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            api_url="https://plati.market/api",
            supplier_name="Plati.market"
        )
    
    async def get_services(self) -> List[SupplierProduct]:
        """Fetch services from Plati.market."""
        try:
            async with aiohttp.ClientSession() as session:
                # Plati.market typically uses GET with API key in headers or params
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                params = {"key": self.api_key}
                
                async with session.get(f"{self.api_url}/products", headers=headers, params=params) as response:
                    if response.status != 200:
                        # Try alternative endpoint
                        async with session.get(f"{self.api_url}/items", headers=headers, params=params) as alt_response:
                            if alt_response.status != 200:
                                logger.error(f"Plati.market API error: {response.status}")
                                return []
                            services_data = await alt_response.json()
                    else:
                        services_data = await response.json()
                    
                    products = []
                    
                    # Handle different response formats
                    if isinstance(services_data, dict):
                        if "data" in services_data:
                            services_data = services_data["data"]
                        elif "items" in services_data:
                            services_data = services_data["items"]
                        elif "products" in services_data:
                            services_data = services_data["products"]
                    
                    if not isinstance(services_data, list):
                        logger.warning(f"Plati.market returned unexpected format: {type(services_data)}")
                        return []
                    
                    for service in services_data:
                        try:
                            # Try different price field names
                            price = service.get("price") or service.get("cost") or service.get("rate") or "0"
                            try:
                                price_cents = int(float(price) * 100)
                            except (ValueError, TypeError):
                                price_cents = 0
                            
                            category = service.get("category") or service.get("type") or "Uncategorized"
                            name = service.get("name") or service.get("title") or service.get("product_name") or "Unknown Service"
                            service_id = str(service.get("id") or service.get("product_id") or service.get("item_id") or "")
                            
                            products.append(SupplierProduct(
                                supplier_id=self.supplier_id,
                                supplier_name=self.supplier_name,
                                service_id=service_id,
                                name=name,
                                category=category,
                                subcategory=service.get("subcategory") or service.get("sub_type"),
                                price_cents=price_cents,
                                min_quantity=service.get("min_quantity") or service.get("min"),
                                max_quantity=service.get("max_quantity") or service.get("max"),
                                description=service.get("description") or service.get("details"),
                                image_url=service.get("image") or service.get("image_url"),
                                refill_available=service.get("refill", False),
                                cancel_available=service.get("cancel", True),
                                service_type=service.get("type"),
                                api_data=service
                            ))
                        except Exception as e:
                            logger.error(f"Error parsing Plati.market service: {e}")
                            continue
                    
                    logger.info(f"Fetched {len(products)} products from {self.supplier_name}")
                    return products
                    
        except Exception as e:
            logger.error(f"Error fetching services from Plati.market: {e}", exc_info=True)
            return []
    
    async def create_order(self, service_id: str, link: str, quantity: int, **kwargs) -> Dict[str, Any]:
        """Create order with Plati.market."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                data = {
                    "key": self.api_key,
                    "product_id": service_id,
                    "link": link,
                    "quantity": quantity
                }
                data.update(kwargs)
                
                async with session.post(f"{self.api_url}/order", headers=headers, json=data) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error creating order with Plati.market: {e}")
            return {"error": str(e)}
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status from Plati.market."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                params = {"key": self.api_key, "order_id": order_id}
                
                async with session.get(f"{self.api_url}/order/status", headers=headers, params=params) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error getting order status from Plati.market: {e}")
            return {"error": str(e)}
    
    async def get_balance(self) -> float:
        """Get balance from Plati.market."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                params = {"key": self.api_key}
                
                async with session.get(f"{self.api_url}/balance", headers=headers, params=params) as response:
                    result = await response.json()
                    # Try different balance field names
                    balance = result.get("balance") or result.get("amount") or result.get("funds") or 0
                    return float(balance)
        except Exception as e:
            logger.error(f"Error getting balance from Plati.market: {e}")
            return 0.0


class KinguinAPI(SupplierAPI):
    """Kinguin API integration."""
    
    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            api_url="https://api.kinguin.net/v1",
            supplier_name="Kinguin"
        )
    
    async def get_services(self) -> List[SupplierProduct]:
        """Fetch products from Kinguin."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "X-Api-Key": self.api_key,
                    "Content-Type": "application/json"
                }
                
                # Kinguin uses pagination, fetch first page
                params = {"page": 0, "limit": 100}
                
                async with session.get(f"{self.api_url}/products", headers=headers, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Kinguin API error: {response.status}")
                        return []
                    
                    result = await response.json()
                    
                    # Handle Kinguin response format
                    if isinstance(result, dict):
                        products_data = result.get("items") or result.get("data") or result.get("products") or []
                    else:
                        products_data = result
                    
                    if not isinstance(products_data, list):
                        logger.warning(f"Kinguin returned unexpected format: {type(products_data)}")
                        return []
                    
                    products = []
                    
                    for item in products_data:
                        try:
                            # Kinguin price format
                            price = item.get("price") or item.get("minPrice") or item.get("priceMin") or "0"
                            try:
                                if isinstance(price, dict):
                                    price_cents = int(float(price.get("amount", 0)) * 100)
                                else:
                                    price_cents = int(float(price) * 100)
                            except (ValueError, TypeError):
                                price_cents = 0
                            
                            category = item.get("category") or item.get("categoryName") or "Uncategorized"
                            name = item.get("name") or item.get("productName") or item.get("title") or "Unknown Product"
                            service_id = str(item.get("id") or item.get("productId") or item.get("kinguinId") or "")
                            
                            products.append(SupplierProduct(
                                supplier_id=self.supplier_id,
                                supplier_name=self.supplier_name,
                                service_id=service_id,
                                name=name,
                                category=category,
                                subcategory=item.get("subcategory") or item.get("platform"),
                                price_cents=price_cents,
                                min_quantity=item.get("minQuantity") or 1,
                                max_quantity=item.get("maxQuantity") or item.get("stock"),
                                description=item.get("description") or item.get("shortDescription"),
                                image_url=item.get("image") or item.get("imageUrl") or item.get("coverImage"),
                                refill_available=False,  # Kinguin typically doesn't have refills
                                cancel_available=True,
                                service_type=item.get("type") or item.get("platform"),
                                api_data=item
                            ))
                        except Exception as e:
                            logger.error(f"Error parsing Kinguin product: {e}")
                            continue
                    
                    logger.info(f"Fetched {len(products)} products from {self.supplier_name}")
                    return products
                    
        except Exception as e:
            logger.error(f"Error fetching products from Kinguin: {e}", exc_info=True)
            return []
    
    async def create_order(self, service_id: str, link: str, quantity: int, **kwargs) -> Dict[str, Any]:
        """Create order with Kinguin."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "X-Api-Key": self.api_key,
                    "Content-Type": "application/json"
                }
                data = {
                    "productId": service_id,
                    "quantity": quantity,
                    "email": kwargs.get("email", ""),
                    "currency": kwargs.get("currency", "USD")
                }
                
                async with session.post(f"{self.api_url}/orders", headers=headers, json=data) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error creating order with Kinguin: {e}")
            return {"error": str(e)}
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status from Kinguin."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"X-Api-Key": self.api_key}
                
                async with session.get(f"{self.api_url}/orders/{order_id}", headers=headers) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Error getting order status from Kinguin: {e}")
            return {"error": str(e)}
    
    async def get_balance(self) -> float:
        """Get balance from Kinguin."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"X-Api-Key": self.api_key}
                
                async with session.get(f"{self.api_url}/account/balance", headers=headers) as response:
                    result = await response.json()
                    balance = result.get("balance") or result.get("amount") or 0
                    return float(balance)
        except Exception as e:
            logger.error(f"Error getting balance from Kinguin: {e}")
            return 0.0


def get_supplier_api(supplier_name: str, api_key: str) -> Optional[SupplierAPI]:
    """Factory function to get supplier API instance."""
    suppliers = {
        "nicesmmpanel": NiceSMMPanelAPI,
        "justanotherpanel": JustAnotherPanelAPI,
        "magicsmm": MagicSMMAPI,
        "platimarket": PlatiMarketAPI,
        "plati.market": PlatiMarketAPI,
        "kinguin": KinguinAPI,
    }
    
    supplier_class = suppliers.get(supplier_name.lower().replace(' ', '').replace('.', ''))
    if supplier_class:
        return supplier_class(api_key)
    return None

