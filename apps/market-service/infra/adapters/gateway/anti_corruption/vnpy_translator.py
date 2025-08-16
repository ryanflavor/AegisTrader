"""
Translator between vnpy objects and domain models.

This is the core of the Anti-Corruption Layer, providing clean
translation between vnpy's data structures and our domain models.
"""

import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from vnpy.trader.constant import Direction, Exchange, OrderType, Status
from vnpy.trader.object import (
    AccountData,
    ContractData,
    OrderData,
    PositionData,
    TickData,
    TradeData,
)

from domain.market_data import (
    InstrumentType,
    MarketDepth,
    OrderSide,
    Price,
    Symbol,
    Tick,
    Volume,
)
from domain.market_data import (
    OrderType as DomainOrderType,
)

# Constants
MAX_FLOAT = sys.float_info.max  # vnpy uses this for invalid prices


class VnpyTranslator:
    """Translates between vnpy objects and domain models."""

    def __init__(self):
        """Initialize translator with exchange mappings."""
        # Exchange mappings
        self.exchange_to_string = {
            Exchange.CFFEX: "CFFEX",  # 中金所
            Exchange.SHFE: "SHFE",  # 上期所
            Exchange.DCE: "DCE",  # 大商所
            Exchange.CZCE: "CZCE",  # 郑商所
            Exchange.INE: "INE",  # 能源中心
            Exchange.GFEX: "GFEX",  # 广期所
            Exchange.SSE: "SSE",  # 上交所
            Exchange.SZSE: "SZSE",  # 深交所
        }

        self.string_to_exchange = {v: k for k, v in self.exchange_to_string.items()}

        # Direction mappings
        self.direction_to_side = {
            Direction.LONG: OrderSide.BUY,
            Direction.SHORT: OrderSide.SELL,
        }

        self.side_to_direction = {v: k for k, v in self.direction_to_side.items()}

        # Order type mappings (only map supported types)
        self.vnpy_to_domain_order_type = {
            OrderType.LIMIT: DomainOrderType.LIMIT,
            OrderType.MARKET: DomainOrderType.MARKET,
            OrderType.STOP: DomainOrderType.STOP,
            # FAK/FOK not supported in domain model yet
            # OrderType.FAK: DomainOrderType.FAK,
            # OrderType.FOK: DomainOrderType.FOK,
        }

    def adjust_price(self, price: float) -> Decimal:
        """
        Adjust invalid price data from vnpy.

        vnpy uses MAX_FLOAT for invalid prices, convert to 0.
        """
        if price == MAX_FLOAT or price < 0:
            return Decimal("0")
        return Decimal(str(price))

    def to_domain_tick(self, vnpy_tick: TickData) -> tuple[Tick, MarketDepth | None]:
        """
        Convert vnpy TickData to domain Tick and MarketDepth.

        Args:
            vnpy_tick: vnpy TickData object

        Returns:
            Tuple of (Tick, MarketDepth or None)
        """
        # Create symbol
        symbol = Symbol(
            value=vnpy_tick.symbol,
            exchange=self.exchange_to_string.get(vnpy_tick.exchange, "UNKNOWN"),
        )

        # Adjust prices
        last_price = self.adjust_price(vnpy_tick.last_price)

        # Create tick
        tick = Tick(
            symbol=symbol,
            price=Price(value=last_price),
            volume=Volume(value=vnpy_tick.volume),
            timestamp=vnpy_tick.datetime if vnpy_tick.datetime else datetime.now(UTC),
            sequence_number=0,  # vnpy doesn't provide sequence numbers
        )

        # Create market depth if available (only level 1 for now)
        depth = None
        if hasattr(vnpy_tick, "bid_price_1") and vnpy_tick.bid_price_1:
            depth = MarketDepth(
                bid_price=Price(value=self.adjust_price(vnpy_tick.bid_price_1)),
                bid_volume=Volume(value=vnpy_tick.bid_volume_1),
                ask_price=Price(value=self.adjust_price(vnpy_tick.ask_price_1)),
                ask_volume=Volume(value=vnpy_tick.ask_volume_1),
                timestamp=vnpy_tick.datetime if vnpy_tick.datetime else datetime.now(UTC),
            )

        return tick, depth

    def from_domain_symbol(self, symbol: Symbol) -> tuple[str, Exchange]:
        """
        Convert domain Symbol to vnpy format.

        Args:
            symbol: Domain Symbol

        Returns:
            Tuple of (symbol_code, vnpy_exchange)
        """
        exchange = self.string_to_exchange.get(symbol.exchange, Exchange.SHFE)
        return symbol.value, exchange

    def to_domain_contract(self, vnpy_contract: ContractData) -> dict[str, Any]:
        """
        Convert vnpy ContractData to domain contract info.

        Args:
            vnpy_contract: vnpy ContractData

        Returns:
            Dictionary with contract information
        """
        return {
            "symbol": vnpy_contract.symbol,
            "exchange": self.exchange_to_string.get(vnpy_contract.exchange, "UNKNOWN"),
            "name": vnpy_contract.name,
            "product": vnpy_contract.product.value if vnpy_contract.product else "UNKNOWN",
            "size": vnpy_contract.size,
            "pricetick": float(vnpy_contract.pricetick),
            "min_volume": vnpy_contract.min_volume,
            "instrument_type": self._get_instrument_type(vnpy_contract),
        }

    def _get_instrument_type(self, contract: ContractData) -> InstrumentType:
        """Determine instrument type from contract."""
        product = str(contract.product).upper() if contract.product else ""

        if "FUTURE" in product:
            return InstrumentType.FUTURES
        elif "OPTION" in product:
            return InstrumentType.OPTIONS
        elif "SPOT" in product or "STOCK" in product:
            return InstrumentType.STOCK
        else:
            return InstrumentType.FUTURES  # Default for CTP

    def to_domain_order(self, vnpy_order: OrderData) -> dict[str, Any]:
        """
        Convert vnpy OrderData to domain order info.

        Args:
            vnpy_order: vnpy OrderData

        Returns:
            Dictionary with order information
        """
        return {
            "order_id": vnpy_order.orderid,
            "symbol": vnpy_order.symbol,
            "exchange": self.exchange_to_string.get(vnpy_order.exchange, "UNKNOWN"),
            "side": self.direction_to_side.get(vnpy_order.direction, OrderSide.BUY),
            "order_type": self.vnpy_to_domain_order_type.get(
                vnpy_order.type, DomainOrderType.LIMIT
            ),
            "price": float(vnpy_order.price),
            "volume": vnpy_order.volume,
            "traded": vnpy_order.traded,
            "status": self._convert_order_status(vnpy_order.status),
            "datetime": vnpy_order.datetime if vnpy_order.datetime else datetime.now(UTC),
            "reference": vnpy_order.reference if hasattr(vnpy_order, "reference") else None,
        }

    def _convert_order_status(self, vnpy_status: Status) -> str:
        """Convert vnpy order status to domain status."""
        status_map = {
            Status.SUBMITTING: "SUBMITTING",
            Status.NOTTRADED: "PENDING",
            Status.PARTTRADED: "PARTIAL",
            Status.ALLTRADED: "FILLED",
            Status.CANCELLED: "CANCELLED",
            Status.REJECTED: "REJECTED",
        }
        return status_map.get(vnpy_status, "UNKNOWN")

    def to_domain_position(self, vnpy_position: PositionData) -> dict[str, Any]:
        """
        Convert vnpy PositionData to domain position info.

        Args:
            vnpy_position: vnpy PositionData

        Returns:
            Dictionary with position information
        """
        return {
            "symbol": vnpy_position.symbol,
            "exchange": self.exchange_to_string.get(vnpy_position.exchange, "UNKNOWN"),
            "direction": self.direction_to_side.get(vnpy_position.direction, OrderSide.BUY),
            "volume": vnpy_position.volume,
            "frozen": vnpy_position.frozen,
            "price": float(vnpy_position.price),
            "pnl": float(vnpy_position.pnl),
            "yd_volume": vnpy_position.yd_volume,
        }

    def to_domain_account(self, vnpy_account: AccountData) -> dict[str, Any]:
        """
        Convert vnpy AccountData to domain account info.

        Args:
            vnpy_account: vnpy AccountData

        Returns:
            Dictionary with account information
        """
        return {
            "account_id": vnpy_account.accountid,
            "balance": float(vnpy_account.balance),
            "available": float(vnpy_account.available),
            "frozen": float(vnpy_account.frozen),
            "margin": float(getattr(vnpy_account, "margin", 0)),
            "commission": float(getattr(vnpy_account, "commission", 0)),
        }

    def to_domain_trade(self, vnpy_trade: TradeData) -> dict[str, Any]:
        """
        Convert vnpy TradeData to domain trade info.

        Args:
            vnpy_trade: vnpy TradeData

        Returns:
            Dictionary with trade information
        """
        return {
            "trade_id": vnpy_trade.tradeid,
            "order_id": vnpy_trade.orderid,
            "symbol": vnpy_trade.symbol,
            "exchange": self.exchange_to_string.get(vnpy_trade.exchange, "UNKNOWN"),
            "side": self.direction_to_side.get(vnpy_trade.direction, OrderSide.BUY),
            "offset": vnpy_trade.offset.value if vnpy_trade.offset else "NONE",
            "price": float(vnpy_trade.price),
            "volume": vnpy_trade.volume,
            "datetime": vnpy_trade.datetime if vnpy_trade.datetime else datetime.now(UTC),
        }
