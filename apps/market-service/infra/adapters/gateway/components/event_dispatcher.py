"""
Event Dispatcher for vnpy events.

Routes vnpy events to appropriate handlers and manages event flow.
"""

import logging
from collections.abc import Callable
from typing import Any

from vnpy.event import Event, EventEngine
from vnpy.trader.event import (
    EVENT_ACCOUNT,
    EVENT_CONTRACT,
    EVENT_LOG,
    EVENT_ORDER,
    EVENT_POSITION,
    EVENT_TICK,
    EVENT_TIMER,
    EVENT_TRADE,
)

from ..anti_corruption import VnpyEventAdapter, VnpyTranslator

logger = logging.getLogger(__name__)


class EventDispatcher:
    """
    Dispatches vnpy events to appropriate handlers.

    Responsibilities:
    - Register event handlers with EventEngine
    - Route events to domain handlers
    - Track event statistics
    - Buffer events during initialization
    """

    def __init__(
        self,
        event_adapter: VnpyEventAdapter,
        translator: VnpyTranslator,
    ):
        """
        Initialize event dispatcher.

        Args:
            event_adapter: Event adapter for async queue
            translator: Object translator
        """
        self.event_adapter = event_adapter
        self.translator = translator

        # Event callbacks
        self.tick_callbacks: list[Callable] = []
        self.order_callbacks: list[Callable] = []
        self.trade_callbacks: list[Callable] = []
        self.position_callbacks: list[Callable] = []
        self.account_callbacks: list[Callable] = []

        # Buffered data during initialization
        self.order_buffer: list[dict] = []
        self.trade_buffer: list[dict] = []

        # Contract initialization tracking
        self.contract_count = 0
        self.contract_inited = False
        self.contracts: dict[str, Any] = {}

    def register_with_engine(self, event_engine: EventEngine) -> None:
        """
        Register event handlers with EventEngine.

        Args:
            event_engine: vnpy EventEngine
        """
        event_engine.register(EVENT_CONTRACT, self._handle_contract)
        event_engine.register(EVENT_TICK, self._handle_tick)
        event_engine.register(EVENT_ORDER, self._handle_order)
        event_engine.register(EVENT_TRADE, self._handle_trade)
        event_engine.register(EVENT_POSITION, self._handle_position)
        event_engine.register(EVENT_ACCOUNT, self._handle_account)
        event_engine.register(EVENT_LOG, self._handle_log)
        event_engine.register(EVENT_TIMER, self._handle_timer)

        logger.info("Registered all event handlers with EventEngine")

    def _handle_contract(self, event: Event) -> None:
        """Handle contract event."""
        contract = event.data

        # Store contract
        self.contracts[contract.vt_symbol] = contract
        self.contract_count += 1

        # Mark contracts as initialized when we have enough
        if not self.contract_inited and self.contract_count > 100:
            self.contract_inited = True
            logger.info(f"Contract initialization complete: {self.contract_count} contracts")
            self._process_buffered_data()

        # Forward to event adapter
        self.event_adapter.handle_event(event)

        logger.debug(f"Contract: {contract.symbol} ({contract.name})")

    def _handle_tick(self, event: Event) -> None:
        """Handle tick event."""
        tick = event.data

        # Translate to domain model (returns tuple of tick and optional depth)
        domain_tick, market_depth = self.translator.to_domain_tick(tick)

        # Call registered callbacks with the tick (depth can be handled separately if needed)
        for callback in self.tick_callbacks:
            try:
                callback(domain_tick)
            except Exception as e:
                logger.error(f"Error in tick callback: {e}")

        # Forward to event adapter
        self.event_adapter.handle_event(event)

        logger.debug(f"Tick: {tick.symbol} @ {tick.last_price}")

    def _handle_order(self, event: Event) -> None:
        """Handle order event."""
        order = event.data

        # Buffer if contracts not initialized
        if not self.contract_inited:
            self.order_buffer.append(order.__dict__)
            return

        # Translate to domain format
        domain_order = self.translator.to_domain_order(order)

        # Call registered callbacks
        for callback in self.order_callbacks:
            try:
                callback(domain_order)
            except Exception as e:
                logger.error(f"Error in order callback: {e}")

        # Forward to event adapter
        self.event_adapter.handle_event(event)

        logger.info(f"Order: {order.orderid} - {order.status}")

    def _handle_trade(self, event: Event) -> None:
        """Handle trade event."""
        trade = event.data

        # Buffer if contracts not initialized
        if not self.contract_inited:
            self.trade_buffer.append(trade.__dict__)
            return

        # Translate to domain format
        domain_trade = self.translator.to_domain_trade(trade)

        # Call registered callbacks
        for callback in self.trade_callbacks:
            try:
                callback(domain_trade)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}")

        # Forward to event adapter
        self.event_adapter.handle_event(event)

        logger.info(f"Trade: {trade.tradeid} @ {trade.price}")

    def _handle_position(self, event: Event) -> None:
        """Handle position event."""
        position = event.data

        # Translate to domain format
        domain_position = self.translator.to_domain_position(position)

        # Call registered callbacks
        for callback in self.position_callbacks:
            try:
                callback(domain_position)
            except Exception as e:
                logger.error(f"Error in position callback: {e}")

        # Forward to event adapter
        self.event_adapter.handle_event(event)

        logger.debug(f"Position: {position.symbol} vol:{position.volume}")

    def _handle_account(self, event: Event) -> None:
        """Handle account event."""
        account = event.data

        # Translate to domain format
        domain_account = self.translator.to_domain_account(account)

        # Call registered callbacks
        for callback in self.account_callbacks:
            try:
                callback(domain_account)
            except Exception as e:
                logger.error(f"Error in account callback: {e}")

        # Forward to event adapter
        self.event_adapter.handle_event(event)

        logger.info(f"Account: balance={account.balance:.2f}")

    def _handle_log(self, event: Event) -> None:
        """Handle log event."""
        log = event.data
        msg = log.msg if hasattr(log, "msg") else str(log)
        logger.info(f"Gateway: {msg}")

    def _handle_timer(self, event: Event) -> None:
        """Handle timer event."""
        # Forward to event adapter for heartbeat tracking
        self.event_adapter.handle_event(event)
        logger.debug("Timer event")

    def _process_buffered_data(self) -> None:
        """Process buffered orders and trades after contract initialization."""
        logger.info(
            f"Processing {len(self.order_buffer)} buffered orders "
            f"and {len(self.trade_buffer)} buffered trades"
        )

        # Process buffered orders
        for order_dict in self.order_buffer:
            # Create mock event
            event = Event(EVENT_ORDER, order_dict)
            self._handle_order(event)
        self.order_buffer.clear()

        # Process buffered trades
        for trade_dict in self.trade_buffer:
            # Create mock event
            event = Event(EVENT_TRADE, trade_dict)
            self._handle_trade(event)
        self.trade_buffer.clear()

    def register_tick_callback(self, callback: Callable) -> None:
        """Register callback for tick events."""
        self.tick_callbacks.append(callback)
        logger.debug("Registered tick callback")

    def register_order_callback(self, callback: Callable) -> None:
        """Register callback for order events."""
        self.order_callbacks.append(callback)
        logger.debug("Registered order callback")

    def register_trade_callback(self, callback: Callable) -> None:
        """Register callback for trade events."""
        self.trade_callbacks.append(callback)
        logger.debug("Registered trade callback")

    def register_position_callback(self, callback: Callable) -> None:
        """Register callback for position events."""
        self.position_callbacks.append(callback)
        logger.debug("Registered position callback")

    def register_account_callback(self, callback: Callable) -> None:
        """Register callback for account events."""
        self.account_callbacks.append(callback)
        logger.debug("Registered account callback")

    def clear_callbacks(self) -> None:
        """Clear all registered callbacks."""
        self.tick_callbacks.clear()
        self.order_callbacks.clear()
        self.trade_callbacks.clear()
        self.position_callbacks.clear()
        self.account_callbacks.clear()
        logger.debug("Cleared all callbacks")

    def clear_buffers(self) -> None:
        """Clear all buffered data."""
        self.order_buffer.clear()
        self.trade_buffer.clear()
        self.contracts.clear()
        self.contract_count = 0
        self.contract_inited = False
        logger.debug("Cleared all buffers")
