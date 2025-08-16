"""
Tests for connection state persistence to NATS KV
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.gateway.connection_manager import (
    ConnectionManager,
    ConnectionStateData,
    ConnectionStatePersistence,
)
from domain.gateway.value_objects import ConnectionConfig, HeartbeatConfig


@pytest.fixture
def mock_kv_store():
    """Mock NATS KV store"""
    kv_store = AsyncMock()
    kv_store.put = AsyncMock()
    kv_store.get = AsyncMock()
    kv_store.delete = AsyncMock()
    return kv_store


@pytest.fixture
def connection_state_data():
    """Sample connection state data"""
    return ConnectionStateData(
        gateway_id="test-gateway",
        connection_state="CONNECTED",
        last_successful_config={"test": "config"},
        connection_attempts=5,
        last_heartbeat=datetime.now(),
        last_connection_time=datetime.now(),
        failure_count=2,
    )


class TestConnectionStatePersistence:
    """Test connection state persistence functionality"""

    async def test_save_state(self, mock_kv_store, connection_state_data):
        """Test saving connection state to KV store"""
        # Arrange
        persistence = ConnectionStatePersistence(mock_kv_store, "test-gateway")

        # Act
        await persistence.save_state(connection_state_data)

        # Assert
        mock_kv_store.put.assert_called_once()
        call_args = mock_kv_store.put.call_args
        assert call_args.kwargs["key"] == "gateway:state:test-gateway"
        assert call_args.kwargs["ttl"] == 86400  # 24 hours

        # Verify JSON serialization
        saved_value = json.loads(call_args.kwargs["value"].decode())
        assert saved_value["gateway_id"] == "test-gateway"
        assert saved_value["connection_state"] == "CONNECTED"
        assert saved_value["connection_attempts"] == 5

    async def test_save_state_handles_errors(self, mock_kv_store, connection_state_data):
        """Test save state handles KV store errors gracefully"""
        # Arrange
        mock_kv_store.put.side_effect = Exception("KV store error")
        persistence = ConnectionStatePersistence(mock_kv_store, "test-gateway")

        # Act - should not raise
        await persistence.save_state(connection_state_data)

        # Assert
        mock_kv_store.put.assert_called_once()

    async def test_load_state(self, mock_kv_store, connection_state_data):
        """Test loading connection state from KV store"""
        # Arrange
        state_dict = connection_state_data.model_dump(mode="json")
        mock_entry = MagicMock()
        mock_entry.value = json.dumps(state_dict).encode()
        mock_kv_store.get.return_value = mock_entry

        persistence = ConnectionStatePersistence(mock_kv_store, "test-gateway")

        # Act
        loaded_state = await persistence.load_state()

        # Assert
        mock_kv_store.get.assert_called_once_with("gateway:state:test-gateway")
        assert loaded_state.gateway_id == "test-gateway"
        assert loaded_state.connection_state == "CONNECTED"
        assert loaded_state.connection_attempts == 5

    async def test_load_state_returns_none_when_not_found(self, mock_kv_store):
        """Test load state returns None when no state exists"""
        # Arrange
        mock_kv_store.get.return_value = None
        persistence = ConnectionStatePersistence(mock_kv_store, "test-gateway")

        # Act
        loaded_state = await persistence.load_state()

        # Assert
        assert loaded_state is None

    async def test_load_state_handles_errors(self, mock_kv_store):
        """Test load state handles KV store errors gracefully"""
        # Arrange
        mock_kv_store.get.side_effect = Exception("KV store error")
        persistence = ConnectionStatePersistence(mock_kv_store, "test-gateway")

        # Act
        loaded_state = await persistence.load_state()

        # Assert
        assert loaded_state is None

    async def test_delete_state(self, mock_kv_store):
        """Test deleting connection state from KV store"""
        # Arrange
        persistence = ConnectionStatePersistence(mock_kv_store, "test-gateway")

        # Act
        await persistence.delete_state()

        # Assert
        mock_kv_store.delete.assert_called_once_with("gateway:state:test-gateway")

    async def test_delete_state_handles_errors(self, mock_kv_store):
        """Test delete state handles KV store errors gracefully"""
        # Arrange
        mock_kv_store.delete.side_effect = Exception("KV store error")
        persistence = ConnectionStatePersistence(mock_kv_store, "test-gateway")

        # Act - should not raise
        await persistence.delete_state()

        # Assert
        mock_kv_store.delete.assert_called_once()


class TestConnectionManagerWithPersistence:
    """Test ConnectionManager with state persistence"""

    @pytest.fixture
    def mock_adapter(self):
        """Mock gateway adapter"""
        adapter = AsyncMock()
        adapter.connect = AsyncMock()
        adapter.disconnect = AsyncMock()
        adapter.send_heartbeat = AsyncMock()
        adapter.is_connected = MagicMock(return_value=True)
        return adapter

    @pytest.fixture
    def connection_config(self):
        """Connection configuration"""
        return ConnectionConfig(
            heartbeat_config=HeartbeatConfig(enabled=False),
            reconnect_delay=1,
            max_reconnect_attempts=3,
        )

    async def test_connection_manager_with_kv_store(
        self, mock_adapter, connection_config, mock_kv_store
    ):
        """Test ConnectionManager initializes with KV store"""
        # Act
        manager = ConnectionManager(
            adapter=mock_adapter,
            config=connection_config,
            kv_store=mock_kv_store,
            gateway_id="test-gateway",
        )

        # Assert
        assert manager.state_persistence is not None
        assert manager.state_persistence.gateway_id == "test-gateway"

    async def test_connection_persists_state(self, mock_adapter, connection_config, mock_kv_store):
        """Test successful connection persists state"""
        # Arrange
        manager = ConnectionManager(
            adapter=mock_adapter,
            config=connection_config,
            kv_store=mock_kv_store,
            gateway_id="test-gateway",
        )

        # Act
        await manager.connect()

        # Assert
        mock_kv_store.put.assert_called()
        call_args = mock_kv_store.put.call_args
        saved_value = json.loads(call_args.kwargs["value"].decode())
        assert saved_value["connection_state"] == "CONNECTED"
        assert saved_value["last_successful_config"] is not None

    async def test_disconnection_persists_state(
        self, mock_adapter, connection_config, mock_kv_store
    ):
        """Test disconnection persists state"""
        # Arrange
        manager = ConnectionManager(
            adapter=mock_adapter,
            config=connection_config,
            kv_store=mock_kv_store,
            gateway_id="test-gateway",
        )
        await manager.connect()
        mock_kv_store.put.reset_mock()

        # Act
        await manager.disconnect()

        # Assert
        mock_kv_store.put.assert_called()
        call_args = mock_kv_store.put.call_args
        saved_value = json.loads(call_args.kwargs["value"].decode())
        assert saved_value["connection_state"] == "DISCONNECTED"

    async def test_restore_state(self, mock_adapter, connection_config, mock_kv_store):
        """Test restoring connection state from KV store"""
        # Arrange
        saved_state = ConnectionStateData(
            gateway_id="test-gateway",
            connection_state="DISCONNECTED",
            connection_attempts=10,
            last_successful_config={"restored": "config"},
        )
        mock_entry = MagicMock()
        mock_entry.value = json.dumps(saved_state.model_dump(mode="json")).encode()
        mock_kv_store.get.return_value = mock_entry

        manager = ConnectionManager(
            adapter=mock_adapter,
            config=connection_config,
            kv_store=mock_kv_store,
            gateway_id="test-gateway",
        )

        # Act
        restored = await manager.restore_state()

        # Assert
        assert restored is True
        assert manager.connection_attempts == 10
        assert manager.last_successful_config == {"restored": "config"}

    async def test_shutdown_clears_state(self, mock_adapter, connection_config, mock_kv_store):
        """Test shutdown clears persisted state"""
        # Arrange
        manager = ConnectionManager(
            adapter=mock_adapter,
            config=connection_config,
            kv_store=mock_kv_store,
            gateway_id="test-gateway",
        )

        # Act
        await manager.shutdown()

        # Assert
        mock_kv_store.delete.assert_called_once_with("gateway:state:test-gateway")

    async def test_heartbeat_persists_state(self, mock_adapter, connection_config, mock_kv_store):
        """Test heartbeat response persists state"""
        # Arrange
        manager = ConnectionManager(
            adapter=mock_adapter,
            config=connection_config,
            kv_store=mock_kv_store,
            gateway_id="test-gateway",
        )
        await manager.connect()
        mock_kv_store.put.reset_mock()

        # Act
        manager.handle_heartbeat_response()
        await manager._persist_state()  # Wait for async task

        # Assert
        mock_kv_store.put.assert_called()
        call_args = mock_kv_store.put.call_args
        saved_value = json.loads(call_args.kwargs["value"].decode())
        assert saved_value["last_heartbeat"] is not None
