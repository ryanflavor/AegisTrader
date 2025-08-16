"""
Gateway Protocol Translators.

Translates between external gateway protocols and domain models.
Each gateway (CTP, IB, Binance, etc.) has its own data format and quirks.
This layer ensures our domain remains clean and gateway-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from domain.market_data import Price, Symbol, Tick, Volume


class GatewayTranslator(ABC):
    """Base translator for gateway protocols."""

    @abstractmethod
    def translate_tick(self, raw_data: Any) -> Tick:
        """Translate raw gateway tick data to domain Tick."""
        pass

    @abstractmethod
    def translate_symbol(self, raw_symbol: Any) -> Symbol:
        """Translate raw gateway symbol to domain Symbol."""
        pass

    @abstractmethod
    def translate_order_request(self, domain_order: Any) -> dict:
        """Translate domain order to gateway-specific format."""
        pass


class CTPTranslator(GatewayTranslator):
    """Translator for CTP (Comprehensive Transaction Platform) protocol."""

    def translate_tick(self, raw_data: dict) -> Tick:
        """
        Translate CTP tick data to domain Tick.

        CTP specific fields:
        - LastPrice: 最新价
        - Volume: 成交量
        - OpenInterest: 持仓量
        - UpdateTime: 更新时间
        - UpdateMillisec: 更新毫秒
        """
        # Handle CTP's specific timestamp format
        update_time = raw_data.get("UpdateTime", "")  # Format: "09:30:00"
        update_date = raw_data.get("TradingDay", "")  # Format: "20240112"
        update_millisec = raw_data.get("UpdateMillisec", 0)

        # Combine date, time and milliseconds
        timestamp_str = f"{update_date} {update_time}"
        timestamp = datetime.strptime(timestamp_str, "%Y%m%d %H:%M:%S")
        timestamp = timestamp.replace(tzinfo=UTC, microsecond=update_millisec * 1000)

        return Tick(
            symbol=self.translate_symbol(raw_data.get("InstrumentID")),
            price=Price(value=Decimal(str(raw_data.get("LastPrice", 0)))),
            volume=Volume(value=raw_data.get("Volume", 0)),
            timestamp=timestamp,
            sequence_number=raw_data.get("UpdateMillisec", 0),  # Use millisec as sequence
        )

    def translate_symbol(self, raw_symbol: str) -> Symbol:
        """
        Translate CTP instrument ID to domain Symbol.

        CTP format: "rb2405" (螺纹钢2024年5月合约)
        """
        # CTP symbols include product code and expiry
        # For futures, extract base symbol and determine exchange
        exchange = self._determine_exchange(raw_symbol)

        return Symbol(
            value=raw_symbol.upper(),
            exchange=exchange,
        )

    def translate_order_request(self, domain_order: Any) -> dict:
        """Translate domain order to CTP order format."""
        # CTP specific order fields
        return {
            "InstrumentID": domain_order.symbol.value,
            "Direction": self._translate_direction(domain_order.side),
            "CombOffsetFlag": self._translate_offset(domain_order.order_type),
            "LimitPrice": float(domain_order.price),
            "VolumeTotalOriginal": domain_order.quantity,
            # CTP specific fields
            "CombHedgeFlag": "1",  # 投机
            "TimeCondition": "3",  # 当日有效
            "VolumeCondition": "1",  # 任意数量
            "MinVolume": 1,
            "ContingentCondition": "1",  # 立即
            "ForceCloseReason": "0",  # 非强平
        }

    def _determine_exchange(self, instrument_id: str) -> str:
        """Determine exchange from CTP instrument ID."""
        # Mapping of product prefixes to exchanges
        prefix_exchange_map = {
            "rb": "SHFE",  # 上期所 - 螺纹钢
            "IF": "CFFEX",  # 中金所 - 沪深300股指
            "m": "DCE",  # 大商所 - 豆粕
            "SR": "CZCE",  # 郑商所 - 白糖
        }

        for prefix, exchange in prefix_exchange_map.items():
            if instrument_id.startswith(prefix):
                return exchange

        return "UNKNOWN"

    def _translate_direction(self, side: str) -> str:
        """Translate order side to CTP direction."""
        return "0" if side.upper() == "BUY" else "1"

    def _translate_offset(self, order_type: str) -> str:
        """Translate order type to CTP offset flag."""
        offset_map = {
            "OPEN": "0",  # 开仓
            "CLOSE": "1",  # 平仓
            "CLOSE_TODAY": "3",  # 平今
            "CLOSE_YESTERDAY": "4",  # 平昨
        }
        return offset_map.get(order_type, "0")


class SOPTTranslator(GatewayTranslator):
    """Translator for SOPT (Stock Options Trading Platform) protocol."""

    def translate_tick(self, raw_data: Any) -> Tick:
        """
        Translate SOPT tick data to domain Tick.

        SOPT uses similar format to CTP but for stock options:
        - InstrumentID: 期权合约代码 (e.g., "10004731" for 50ETF期权)
        - LastPrice: 最新价
        - Volume: 成交量
        - UpdateTime: 更新时间
        """
        # Handle vnpy TickData object
        if hasattr(raw_data, "__dict__"):
            # It's a vnpy TickData object
            timestamp = raw_data.datetime if hasattr(raw_data, "datetime") else datetime.now(UTC)

            return Tick(
                symbol=self.translate_symbol(raw_data.symbol),
                price=Price(value=Decimal(str(raw_data.last_price))),
                volume=Volume(value=raw_data.volume),
                timestamp=timestamp,
                sequence_number=0,  # SOPT doesn't provide sequence number
            )
        else:
            # It's a dict from SOPT API
            update_time = raw_data.get("UpdateTime", "")
            update_date = raw_data.get("TradingDay", "")
            update_millisec = raw_data.get("UpdateMillisec", 0)

            # Combine date and time
            if update_date and update_time:
                timestamp_str = f"{update_date} {update_time}"
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d %H:%M:%S")
                timestamp = timestamp.replace(tzinfo=UTC, microsecond=update_millisec * 1000)
            else:
                timestamp = datetime.now(UTC)

            return Tick(
                symbol=self.translate_symbol(raw_data.get("InstrumentID", "")),
                price=Price(value=Decimal(str(raw_data.get("LastPrice", 0)))),
                volume=Volume(value=raw_data.get("Volume", 0)),
                timestamp=timestamp,
                sequence_number=update_millisec,
            )

    def translate_symbol(self, raw_symbol: Any) -> Symbol:
        """
        Translate SOPT instrument ID to domain Symbol.

        SOPT format:
        - ETF options: "10004731" (numerical code)
        - ETF underlying: "510050" (50ETF), "510300" (300ETF)
        """
        if hasattr(raw_symbol, "__str__"):
            symbol_str = str(raw_symbol)
        else:
            symbol_str = raw_symbol

        # Determine exchange based on symbol
        if symbol_str.startswith("5") or symbol_str.startswith("6"):
            exchange = "SSE"  # Shanghai Stock Exchange
        elif symbol_str.startswith("0") or symbol_str.startswith("3"):
            exchange = "SZSE"  # Shenzhen Stock Exchange
        elif symbol_str.startswith("1"):
            # Options typically start with 1
            exchange = "SSE"  # Most options are on SSE
        else:
            exchange = "UNKNOWN"

        return Symbol(
            value=symbol_str,
            exchange=exchange,
        )

    def translate_order_request(self, domain_order: Any) -> dict:
        """Translate domain order to SOPT order format."""
        return {
            "InstrumentID": domain_order.symbol.value,
            "Direction": self._translate_direction(domain_order.side),
            "CombOffsetFlag": self._translate_offset(domain_order.order_type),
            "LimitPrice": float(domain_order.price),
            "VolumeTotalOriginal": domain_order.quantity,
            # SOPT specific fields for options
            "CombHedgeFlag": "1",  # 投机
            "TimeCondition": "3",  # 当日有效
            "VolumeCondition": "1",  # 任意数量
            "MinVolume": 1,
            "ContingentCondition": "1",  # 立即
            "ForceCloseReason": "0",  # 非强平
        }

    def _translate_direction(self, side: str) -> str:
        """Translate order side to SOPT direction."""
        return "0" if side.upper() == "BUY" else "1"

    def _translate_offset(self, order_type: str) -> str:
        """Translate order type to SOPT offset flag."""
        offset_map = {
            "OPEN": "0",  # 开仓
            "CLOSE": "1",  # 平仓
            "CLOSE_TODAY": "3",  # 平今
            "CLOSE_YESTERDAY": "4",  # 平昨
        }
        return offset_map.get(order_type, "0")


class IBTranslator(GatewayTranslator):
    """Translator for Interactive Brokers TWS API."""

    def translate_tick(self, raw_data: dict) -> Tick:
        """
        Translate IB tick data to domain Tick.

        IB tick types:
        - 1: BID
        - 2: ASK
        - 4: LAST
        - 5: LAST_SIZE
        """
        tick_type = raw_data.get("tickType", 4)

        # IB uses Unix timestamp in milliseconds
        timestamp_ms = raw_data.get("time", 0) * 1000
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)

        # Get price based on tick type
        if tick_type in [1, 2, 4]:  # Price ticks
            price = raw_data.get("price", 0)
        else:
            price = raw_data.get("lastPrice", 0)

        return Tick(
            symbol=self.translate_symbol(raw_data.get("contract")),
            price=Price(value=Decimal(str(price))),
            volume=Volume(value=raw_data.get("size", 0)),
            timestamp=timestamp,
            sequence_number=raw_data.get("tickerId", 0),
        )

    def translate_symbol(self, contract: dict) -> Symbol:
        """
        Translate IB contract to domain Symbol.

        IB contract structure:
        - symbol: Base symbol (e.g., "AAPL")
        - exchange: Exchange (e.g., "SMART", "NASDAQ")
        - secType: Security type (STK, OPT, FUT, etc.)
        """
        if isinstance(contract, dict):
            symbol = contract.get("symbol", "")
            exchange = contract.get("exchange", "SMART")
        else:
            symbol = str(contract)
            exchange = "SMART"

        return Symbol(
            value=symbol,
            exchange=exchange,
        )

    def translate_order_request(self, domain_order: Any) -> dict:
        """Translate domain order to IB order format."""
        return {
            "action": domain_order.side.upper(),
            "totalQuantity": domain_order.quantity,
            "orderType": self._translate_order_type(domain_order.order_type),
            "lmtPrice": float(domain_order.price) if domain_order.price else 0,
            "tif": "DAY",  # Time in force
            "transmit": True,
        }

    def _translate_order_type(self, order_type: str) -> str:
        """Translate to IB order type."""
        type_map = {
            "LIMIT": "LMT",
            "MARKET": "MKT",
            "STOP": "STP",
            "STOP_LIMIT": "STP LMT",
        }
        return type_map.get(order_type, "LMT")


class BinanceTranslator(GatewayTranslator):
    """Translator for Binance Exchange API."""

    def translate_tick(self, raw_data: dict) -> Tick:
        """
        Translate Binance tick data to domain Tick.

        Binance WebSocket tick structure:
        - s: Symbol
        - p: Price
        - q: Quantity
        - T: Trade time
        """
        # Binance uses millisecond timestamps
        timestamp = datetime.fromtimestamp(raw_data.get("T", 0) / 1000, tz=UTC)

        return Tick(
            symbol=self.translate_symbol(raw_data.get("s", "")),
            price=Price(value=Decimal(raw_data.get("p", "0"))),
            volume=Volume(value=int(float(raw_data.get("q", "0")))),
            timestamp=timestamp,
            sequence_number=raw_data.get("t", 0),  # Trade ID
        )

    def translate_symbol(self, raw_symbol: str) -> Symbol:
        """
        Translate Binance symbol to domain Symbol.

        Binance format: "BTCUSDT", "ETHBTC"
        """
        return Symbol(
            value=raw_symbol,
            exchange="BINANCE",
        )

    def translate_order_request(self, domain_order: Any) -> dict:
        """Translate domain order to Binance order format."""
        return {
            "symbol": domain_order.symbol.value,
            "side": domain_order.side.upper(),
            "type": self._translate_order_type(domain_order.order_type),
            "quantity": str(domain_order.quantity),
            "price": str(domain_order.price) if domain_order.price else None,
            "timeInForce": "GTC",  # Good till cancelled
        }

    def _translate_order_type(self, order_type: str) -> str:
        """Translate to Binance order type."""
        type_map = {
            "LIMIT": "LIMIT",
            "MARKET": "MARKET",
            "STOP": "STOP_LOSS",
            "STOP_LIMIT": "STOP_LOSS_LIMIT",
        }
        return type_map.get(order_type, "LIMIT")


class TranslatorFactory:
    """Factory for creating gateway translators."""

    _translators = {
        "CTP": CTPTranslator,
        "IB": IBTranslator,
        "BINANCE": BinanceTranslator,
        "SOPT": SOPTTranslator,
    }

    @classmethod
    def create(cls, gateway_type: str) -> GatewayTranslator:
        """Create translator for specified gateway type."""
        translator_class = cls._translators.get(gateway_type.upper())
        if not translator_class:
            raise ValueError(f"Unsupported gateway type: {gateway_type}")
        return translator_class()

    @classmethod
    def register(cls, gateway_type: str, translator_class: type[GatewayTranslator]) -> None:
        """Register a new translator type."""
        cls._translators[gateway_type.upper()] = translator_class
