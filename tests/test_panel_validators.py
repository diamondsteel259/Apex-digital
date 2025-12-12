import unittest
from unittest.mock import Mock, MagicMock
import discord
from cogs.setup import SetupCog

class TestPanelValidators(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_bot = Mock()
        # Mocking config and loop as they are accessed in __init__
        self.mock_bot.config = Mock()
        self.mock_bot.loop = Mock()
        self.mock_bot.loop.create_task = Mock()
        self.cog = SetupCog(self.mock_bot)

    def _create_mock_message(self, embed_title=None, components=None):
        message = Mock(spec=discord.Message)
        
        # Mock Embeds
        if embed_title:
            embed = Mock(spec=discord.Embed)
            embed.title = embed_title
            # Add fields attribute for stricter validation tests
            embed.fields = []
            message.embeds = [embed]
        else:
            message.embeds = []

        # Mock Components
        message.components = []
        if components:
            for comp_children in components:
                component = Mock()
                children = []
                for child_attrs in comp_children:
                    child = Mock()
                    for k, v in child_attrs.items():
                        setattr(child, k, v)
                    children.append(child)
                component.children = children
                message.components.append(component)
        
        return message

    async def test_validate_support_panel_success_custom_ids(self):
        """Test validation succeeds with correct custom_ids."""
        components = [[
            {"label": "General Support", "custom_id": "ticket_panel:support"},
            {"label": "Refund Support", "custom_id": "ticket_panel:refund"}
        ]]
        message = self._create_mock_message(embed_title="🛟 Support Options", components=components)
        
        result = await self.cog._validate_support_panel(message)
        self.assertTrue(result["valid"], f"Validation failed: {result['issues']}")

    async def test_validate_support_panel_success_labels(self):
        """Test validation succeeds with correct labels (fallback)."""
        components = [[
            {"label": "General Support", "custom_id": "other"},
            {"label": "Refund Support", "custom_id": "other"}
        ]]
        message = self._create_mock_message(embed_title="🛟 Support Options", components=components)
        
        result = await self.cog._validate_support_panel(message)
        # This is expected to FAIL with current implementation because "Refund Support" contains "Support"
        # but the logic uses if/elif.
        # But wait, in the test I put them in one component list.
        # Logic:
        # for component in message.components:
        #   for child in component.children:
        #      if "support" in label: support_found = True
        #      elif "refund" in label: refund_found = True
        #
        # Child 1: "General Support" -> "support" found.
        # Child 2: "Refund Support" -> "support" in label -> support_found=True. elif skipped.
        # refund_found remains False.
        # So this test should FAIL currently.
        
        # We'll assert it matches the *expected* behavior (which is success)
        # so this test will fail until we fix the code.
        self.assertTrue(result["valid"], f"Validation failed: {result['issues']}")

    async def test_validate_support_panel_failure_missing_refund(self):
        """Test validation fails when refund button is missing."""
        components = [[
            {"label": "General Support", "custom_id": "ticket_panel:support"}
        ]]
        message = self._create_mock_message(embed_title="🛟 Support Options", components=components)
        
        result = await self.cog._validate_support_panel(message)
        self.assertFalse(result["valid"])
        self.assertIn("Missing refund button", result["issues"])

    async def test_validate_help_panel_success_structure(self):
        """Test validation based on embed structure (New Logic)."""
        # This test anticipates the NEW logic.
        # Current logic checks for buttons.
        # We need to construct a message that matches the NEW expectation:
        # Embed with fields: "How to Browse Products", etc.
        # And NO buttons (since _create_help_panel makes empty view).
        
        message = self._create_mock_message(embed_title="❓ How to Use Apex Core")
        # Add required fields
        # Required: ["browse products", "make purchases", "open tickets", "refunds"]
        
        fields = []
        for name in ["How to Browse Products", "How to Make Purchases", "Need Help?", "How to Open Tickets", "How to Request Refunds"]:
            f = Mock()
            f.name = name
            fields.append(f)
        message.embeds[0].fields = fields

        result = await self.cog._validate_help_panel(message)
        
        self.assertTrue(result["valid"], f"Validation failed: {result['issues']}")

    async def test_validate_reviews_panel_success_structure(self):
        """Test validation based on embed structure (New Logic)."""
        # Matches NEW expectation:
        # Embed with fields: "How to Leave a Review", etc.
        # No buttons.
        
        message = self._create_mock_message(embed_title="⭐ Share Your Experience")
        # Required: ["leave a review", "rating system", "earn rewards"]
        
        fields = []
        for name in ["How to Leave a Review", "Rating System", "Earn Rewards"]:
            f = Mock()
            f.name = name
            fields.append(f)
        message.embeds[0].fields = fields

        result = await self.cog._validate_reviews_panel(message)
        
        self.assertTrue(result["valid"], f"Validation failed: {result['issues']}")

