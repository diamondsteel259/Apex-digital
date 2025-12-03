import pytest
import pytest_asyncio

from apex_core.config import (
    Config,
    LoggingChannels,
    OperatingHours,
    PaymentMethod,
    PaymentSettings,
    RateLimitRule,
    RefundSettings,
    Role,
    RoleIDs,
    TicketCategories,
)
from apex_core.database import Database


class MockDiscordRole:
    def __init__(self, role_id: int, name: str = "Role") -> None:
        self.id = role_id
        self.name = name


class MockDiscordMember:
    def __init__(self, member_id: int, name: str = "Member") -> None:
        self.id = member_id
        self.display_name = name
        self.roles_added: list[tuple[MockDiscordRole, str | None]] = []
        self.sent_messages: list[dict] = []

    async def add_roles(self, role: MockDiscordRole, *, reason: str | None = None) -> None:
        self.roles_added.append((role, reason))

    async def send(self, *, content: str | None = None, embed=None) -> None:
        self.sent_messages.append({"content": content, "embed": embed})


class MockTextChannel:
    def __init__(self, channel_id: int) -> None:
        self.id = channel_id
        self.messages: list[dict] = []

    async def send(self, *, content: str | None = None, embed=None) -> None:
        self.messages.append({"content": content, "embed": embed})


class MockGuild:
    def __init__(self, guild_id: int = 987654321) -> None:
        self.id = guild_id
        self._members: dict[int, MockDiscordMember] = {}
        self._roles: dict[int, MockDiscordRole] = {}
        self._channels: dict[int, MockTextChannel] = {}

    def add_member(self, member: MockDiscordMember) -> None:
        self._members[member.id] = member

    def get_member(self, member_id: int) -> MockDiscordMember | None:
        return self._members.get(member_id)

    def add_role(self, role: MockDiscordRole) -> None:
        self._roles[role.id] = role

    def get_role(self, role_id: int) -> MockDiscordRole | None:
        return self._roles.get(role_id)

    def add_channel(self, channel: MockTextChannel) -> None:
        self._channels[channel.id] = channel

    def get_channel(self, channel_id: int) -> MockTextChannel | None:
        return self._channels.get(channel_id)


class MockInteractionResponse:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, *, content: str, ephemeral: bool = False) -> None:
        self.messages.append({"content": content, "ephemeral": ephemeral})


class MockInteraction:
    def __init__(self, user: MockDiscordMember, guild: MockGuild, channel: MockTextChannel) -> None:
        self.user = user
        self.guild = guild
        self.channel = channel
        self.response = MockInteractionResponse()


class MockBot:
    def __init__(self, guild: MockGuild) -> None:
        self.guilds = [guild]
        self.sent_messages: list[dict] = []

    async def send(self, channel: MockTextChannel, *, content: str | None = None, embed=None) -> None:
        self.sent_messages.append({"channel": channel.id, "content": content, "embed": embed})
        await channel.send(content=content, embed=embed)


@pytest.fixture
def mock_guild() -> MockGuild:
    guild = MockGuild()
    guild.add_role(MockDiscordRole(2001, name="Apex VIP"))
    guild.add_channel(MockTextChannel(999001))
    return guild


@pytest.fixture
def mock_bot(mock_guild: MockGuild) -> MockBot:
    return MockBot(mock_guild)


@pytest.fixture
def mock_interaction(mock_guild: MockGuild) -> MockInteraction:
    member = MockDiscordMember(123456789, "IntegrationTester")
    channel = MockTextChannel(888001)
    mock_guild.add_member(member)
    mock_guild.add_channel(channel)
    return MockInteraction(member, mock_guild, channel)


@pytest.fixture
def sample_roles() -> list[Role]:
    return [
        Role(
            name="Client",
            role_id=1001,
            assignment_mode="automatic_spend",
            unlock_condition=0,
            discount_percent=0.0,
            tier_priority=5,
        ),
        Role(
            name="Apex VIP",
            role_id=1002,
            assignment_mode="automatic_spend",
            unlock_condition=5_000,
            discount_percent=1.5,
            tier_priority=4,
        ),
        Role(
            name="Apex Elite",
            role_id=1003,
            assignment_mode="automatic_spend",
            unlock_condition=20_000,
            discount_percent=2.5,
            tier_priority=3,
        ),
        Role(
            name="Legendary Donor",
            role_id=1004,
            assignment_mode="manual",
            unlock_condition="owner",
            discount_percent=4.0,
            tier_priority=1,
        ),
    ]


@pytest.fixture
def sample_config(sample_roles: list[Role]) -> Config:
    payment_methods = [
        PaymentMethod(
            name="Wallet",
            instructions="Use your Apex wallet for instant checkout.",
            emoji="💼",
            metadata={"type": "internal", "is_enabled": True},
        ),
        PaymentMethod(
            name="Binance",
            instructions="Send payment via Binance Pay.",
            emoji="🟡",
            metadata={"pay_id": "123456789", "is_enabled": True},
        ),
    ]

    return Config(
        token="TEST",
        guild_ids=[987654321],
        role_ids=RoleIDs(admin=42),
        ticket_categories=TicketCategories(support=111, billing=222, sales=333),
        operating_hours=OperatingHours(start_hour_utc=0, end_hour_utc=23),
        payment_methods=payment_methods,
        payment_settings=PaymentSettings(
            payment_methods=list(payment_methods),
            order_confirmation_template=(
                "Order #{order_id} for {service_name} {variant_name} costs {price} ETA {eta}"
            ),
            refund_policy="3 days from completion | 10% handling fee",
        ),
        logging_channels=LoggingChannels(
            audit=555001,
            payments=555002,
            tickets=555003,
            errors=555004,
        ),
        refund_settings=RefundSettings(enabled=True, max_days=3, handling_fee_percent=10.0),
        rate_limits={"balance": RateLimitRule(cooldown=60, max_uses=2, per="user")},
        roles=sample_roles,
    )


@pytest_asyncio.fixture
async def db():
    database = Database(":memory:")
    await database.connect()

    await database._connection.execute(
        """
        INSERT INTO products (
            id, main_category, sub_category, service_name, variant_name, price_cents
        ) VALUES (0, 'Manual', 'Manual', 'Manual', 'Manual Placeholder', 0)
        ON CONFLICT(id) DO NOTHING
        """
    )
    await database._connection.commit()

    yield database
    await database.close()


@pytest_asyncio.fixture
async def user_factory(db: Database):
    async def _factory(discord_id: int, *, balance: int = 0) -> int:
        await db.ensure_user(discord_id)
        if balance:
            await db.update_wallet_balance(discord_id, balance)
        return discord_id

    return _factory


@pytest_asyncio.fixture
async def product_factory(db: Database):
    async def _factory(**overrides) -> int:
        payload = {
            "main_category": "Store",
            "sub_category": "Default",
            "service_name": "Service",
            "variant_name": "Variant",
            "price_cents": 1_000,
            "start_time": "Instant",
            "duration": "1h",
            "refill_period": "30 day",
            "additional_info": "",
        }
        payload.update(overrides)
        return await db.create_product(**payload)

    return _factory
