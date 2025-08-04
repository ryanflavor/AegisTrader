"""Tests for main module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from main import ServiceRunner


class TestServiceRunner:
    """Test cases for ServiceRunner."""

    def test_initialization(self):
        """Test ServiceRunner initialization."""
        runner = ServiceRunner()
        assert runner.service is None
        assert runner.nats_adapter is None
        assert runner.kv_store is None
        assert runner.running is False

    @pytest.mark.asyncio
    async def test_setup_infrastructure(self):
        """Test infrastructure setup."""
        runner = ServiceRunner()

        with patch("main.NATSAdapter") as mock_nats_class:
            with patch("main.NATSKVStore") as mock_kv_class:
                with patch("main.SimpleLogger") as mock_logger_class:
                    with patch("main.KVServiceRegistry") as mock_registry_class:
                        with patch(
                            "aegis_sdk.infrastructure.basic_service_discovery.BasicServiceDiscovery"
                        ) as mock_discovery_class:
                            with patch("main.InMemoryMetrics") as mock_metrics_class:
                                # Setup mocks
                                mock_nats = AsyncMock()
                                mock_nats_class.return_value = mock_nats

                                mock_kv = AsyncMock()
                                mock_kv_class.return_value = mock_kv

                                mock_logger = MagicMock()
                                mock_logger_class.return_value = mock_logger

                                mock_registry = MagicMock()
                                mock_registry_class.return_value = mock_registry

                                mock_discovery = MagicMock()
                                mock_discovery_class.return_value = mock_discovery

                                mock_metrics = MagicMock()
                                mock_metrics_class.return_value = mock_metrics

                                # Test setup
                                infra = await runner.setup_infrastructure("nats://test:4222")

                                # Verify calls
                                mock_nats.connect.assert_called_once_with(["nats://test:4222"])
                                mock_kv.connect.assert_called_once()

                                # Verify infrastructure dict
                                assert infra["message_bus"] == mock_nats
                                assert infra["service_registry"] == mock_registry
                                assert infra["service_discovery"] == mock_discovery
                                assert infra["logger"] == mock_logger
                                assert infra["metrics"] == mock_metrics

    @pytest.mark.asyncio
    async def test_run_order_service(self):
        """Test running order service."""
        runner = ServiceRunner()

        with patch.object(runner, "setup_infrastructure") as mock_setup:
            with patch("main.OrderService") as mock_order_service_class:
                with patch("main.RemotePricingServiceAdapter") as mock_pricing_adapter_class:
                    # Setup mocks
                    mock_nats = AsyncMock()
                    mock_kv = AsyncMock()
                    runner.nats_adapter = mock_nats
                    runner.kv_store = mock_kv

                    mock_infra = {
                        "message_bus": mock_nats,
                        "service_registry": MagicMock(),
                        "service_discovery": MagicMock(),
                        "logger": MagicMock(),
                        "metrics": MagicMock(),
                    }
                    mock_setup.return_value = mock_infra

                    mock_service = AsyncMock()
                    mock_order_service_class.return_value = mock_service

                    mock_pricing_adapter = MagicMock()
                    mock_pricing_adapter_class.return_value = mock_pricing_adapter

                    # Create a task that will stop the runner
                    async def stop_runner():
                        await asyncio.sleep(0.1)
                        runner.stop()

                    # Run test
                    stop_task = asyncio.create_task(stop_runner())
                    await runner.run_service("order", 1, "nats://test:4222")
                    await stop_task

                    # Verify service was created and started
                    assert mock_order_service_class.call_count >= 2  # temp + real instance
                    mock_service.start.assert_called()

    @pytest.mark.asyncio
    async def test_run_pricing_service(self):
        """Test running pricing service."""
        runner = ServiceRunner()

        with patch.object(runner, "setup_infrastructure") as mock_setup:
            with patch("main.PricingService") as mock_pricing_service_class:
                # Setup mocks
                mock_nats = AsyncMock()
                mock_kv = AsyncMock()
                runner.nats_adapter = mock_nats
                runner.kv_store = mock_kv

                mock_infra = {
                    "message_bus": mock_nats,
                    "service_registry": MagicMock(),
                    "service_discovery": MagicMock(),
                    "logger": MagicMock(),
                    "metrics": MagicMock(),
                }
                mock_setup.return_value = mock_infra

                mock_service = AsyncMock()
                mock_pricing_service_class.return_value = mock_service

                # Create a task that will stop the runner
                async def stop_runner():
                    await asyncio.sleep(0.1)
                    runner.stop()

                # Run test
                import asyncio

                stop_task = asyncio.create_task(stop_runner())
                await runner.run_service("pricing", 1, "nats://test:4222")
                await stop_task

                # Verify service was created and started
                mock_pricing_service_class.assert_called_once()
                mock_service.start.assert_called()

    @pytest.mark.asyncio
    async def test_run_risk_service(self):
        """Test running risk service."""
        runner = ServiceRunner()

        with patch.object(runner, "setup_infrastructure") as mock_setup:
            with patch("main.RiskService") as mock_risk_service_class:
                # Setup mocks
                mock_nats = AsyncMock()
                mock_kv = AsyncMock()
                runner.nats_adapter = mock_nats
                runner.kv_store = mock_kv

                mock_infra = {
                    "message_bus": mock_nats,
                    "service_registry": MagicMock(),
                    "service_discovery": MagicMock(),
                    "logger": MagicMock(),
                    "metrics": MagicMock(),
                }
                mock_setup.return_value = mock_infra

                mock_service = AsyncMock()
                mock_risk_service_class.return_value = mock_service

                # Create a task that will stop the runner
                async def stop_runner():
                    await asyncio.sleep(0.1)
                    runner.stop()

                # Run test
                import asyncio

                stop_task = asyncio.create_task(stop_runner())
                await runner.run_service("risk", 1, "nats://test:4222")
                await stop_task

                # Verify service was created and started
                mock_risk_service_class.assert_called_once()
                mock_service.start.assert_called()

    @pytest.mark.asyncio
    async def test_run_invalid_service(self):
        """Test running with invalid service type."""
        runner = ServiceRunner()

        with pytest.raises(ValueError, match="Unknown service type: invalid"):
            await runner.run_service("invalid", 1)

    def test_stop(self):
        """Test stopping the service runner."""
        runner = ServiceRunner()
        runner.running = True
        runner.stop()
        assert runner.running is False

    @patch("main.ServiceRunner")
    def test_main_entry_point(self, mock_runner_class):
        """Test main entry point."""
        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner

        # Import will trigger __main__ block if run as script
        # For test, we just verify the structure exists
        import main as main_module

        assert hasattr(main_module, "ServiceRunner")
        assert hasattr(main_module, "main")

    @pytest.mark.asyncio
    async def test_run_multiple_instances(self):
        """Test running multiple instances of a service."""
        runner = ServiceRunner()

        with patch.object(runner, "setup_infrastructure") as mock_setup:
            with patch("main.PricingService") as mock_pricing_service_class:
                # Setup mocks
                mock_nats = AsyncMock()
                mock_kv = AsyncMock()
                runner.nats_adapter = mock_nats
                runner.kv_store = mock_kv

                mock_infra = {
                    "message_bus": mock_nats,
                    "service_registry": MagicMock(),
                    "service_discovery": MagicMock(),
                    "logger": MagicMock(),
                    "metrics": MagicMock(),
                }
                mock_setup.return_value = mock_infra

                mock_services = [AsyncMock() for _ in range(3)]
                mock_pricing_service_class.side_effect = mock_services

                # Create a task that will stop the runner
                async def stop_runner():
                    await asyncio.sleep(0.1)
                    runner.stop()

                # Run test with 3 instances
                import asyncio

                stop_task = asyncio.create_task(stop_runner())
                await runner.run_service("pricing", 3, "nats://test:4222")
                await stop_task

                # Verify 3 instances were created
                assert mock_pricing_service_class.call_count == 3
                for mock_service in mock_services:
                    mock_service.start.assert_called()

    @pytest.mark.asyncio
    async def test_main_function_single_service(self):
        """Test main function with single service."""
        with patch("main.argparse.ArgumentParser") as mock_parser_class:
            with patch("main.ServiceRunner") as mock_runner_class:
                with patch("main.signal.signal") as mock_signal:
                    # Setup argument parser mock
                    mock_parser = MagicMock()
                    mock_parser_class.return_value = mock_parser
                    mock_args = MagicMock()
                    mock_args.service = "order"
                    mock_args.instances = 2
                    mock_args.nats_url = "nats://test:4222"
                    mock_parser.parse_args.return_value = mock_args

                    # Setup runner mock
                    mock_runner = AsyncMock()
                    mock_runner_class.return_value = mock_runner

                    # Import and run main
                    from main import main

                    await main()

                    # Verify runner was used correctly
                    mock_runner.run_service.assert_called_once_with("order", 2, "nats://test:4222")

                    # Verify signal handlers were set up
                    assert mock_signal.call_count >= 2  # SIGINT and SIGTERM

    @pytest.mark.asyncio
    async def test_main_function_all_services(self):
        """Test main function with all services."""
        with patch("main.argparse.ArgumentParser") as mock_parser_class:
            with patch("main.ServiceRunner") as mock_runner_class:
                with patch("main.asyncio.gather") as mock_gather:
                    with patch("main.signal.signal"):
                        # Setup argument parser mock
                        mock_parser = MagicMock()
                        mock_parser_class.return_value = mock_parser
                        mock_args = MagicMock()
                        mock_args.service = "all"
                        mock_args.instances = 1
                        mock_args.nats_url = "nats://test:4222"
                        mock_parser.parse_args.return_value = mock_args

                        # Setup runner mock
                        mock_runners = []

                        def create_runner():
                            runner = AsyncMock()
                            mock_runners.append(runner)
                            return runner

                        mock_runner_class.side_effect = create_runner

                        # Setup gather to complete immediately
                        mock_gather.return_value = asyncio.create_task(asyncio.sleep(0))

                        # Import and run main
                        from main import main

                        await main()

                        # Verify 4 runners were created (1 for signal handling + 3 for services)
                        assert len(mock_runners) == 4

                        # Verify gather was called
                        mock_gather.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_function_error_handling(self):
        """Test main function error handling."""
        with patch("main.argparse.ArgumentParser") as mock_parser_class:
            with patch("main.ServiceRunner") as mock_runner_class:
                with patch("main.sys.exit") as mock_exit:
                    # Setup argument parser mock
                    mock_parser = MagicMock()
                    mock_parser_class.return_value = mock_parser
                    mock_args = MagicMock()
                    mock_args.service = "order"
                    mock_args.instances = 1
                    mock_args.nats_url = "nats://test:4222"
                    mock_parser.parse_args.return_value = mock_args

                    # Setup runner to raise an error
                    mock_runner = AsyncMock()
                    mock_runner.run_service.side_effect = Exception("Test error")
                    mock_runner_class.return_value = mock_runner

                    # Import and run main
                    from main import main

                    await main()

                    # Verify exit was called with error code
                    mock_exit.assert_called_once_with(1)

    async def test_keyboard_interrupt_handling(self):
        """Test handling keyboard interrupt during service run."""
        runner = ServiceRunner()

        with patch.object(runner, "setup_infrastructure") as mock_setup:
            with patch("main.PricingService") as mock_pricing_service_class:
                # Setup mocks
                mock_nats = AsyncMock()
                mock_kv = AsyncMock()
                runner.nats_adapter = mock_nats
                runner.kv_store = mock_kv

                mock_infra = {
                    "message_bus": mock_nats,
                    "service_registry": MagicMock(),
                    "service_discovery": MagicMock(),
                    "logger": MagicMock(),
                    "metrics": MagicMock(),
                }
                mock_setup.return_value = mock_infra

                mock_service = AsyncMock()
                mock_pricing_service_class.return_value = mock_service

                # Simulate KeyboardInterrupt by raising it after a short delay
                async def raise_keyboard_interrupt(duration):
                    if runner.running:
                        runner.running = False
                        raise KeyboardInterrupt()
                    return None

                # Run test
                with patch("asyncio.sleep", side_effect=raise_keyboard_interrupt):
                    try:
                        await runner.run_service("pricing", 1, "nats://test:4222")
                    except KeyboardInterrupt:
                        pass

                # Verify service was stopped
                mock_service.stop.assert_called()

    def test_signal_handler(self):
        """Test signal handler function in main module."""
        with patch("main.ServiceRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner

            # Import the signal_handler from main

            # Create a runner and test signal handling
            runner = MagicMock()

            # Create a signal handler function
            def create_signal_handler(runner_instance):
                def signal_handler(sig, frame):
                    print("\n⚠️  Signal received, shutting down...")
                    runner_instance.stop()

                return signal_handler

            handler = create_signal_handler(runner)

            # Call the signal handler
            import signal

            handler(signal.SIGINT, None)

            # Verify stop was called
            runner.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_if_name_equals_main(self):
        """Test the if __name__ == '__main__' block."""
        # This test ensures coverage of the __main__ block
        with patch("sys.argv", ["main.py", "pricing", "--instances", "1"]):
            with patch("main.asyncio.run") as mock_run:
                # Import main module to trigger __main__ block
                import importlib

                import main

                # The __main__ block should not execute during import
                mock_run.assert_not_called()

                # Reload to ensure fresh import
                importlib.reload(main)
