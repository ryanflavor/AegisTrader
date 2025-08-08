#!/bin/bash
# 便捷脚本：运行 aegis-sdk-dev CLI 命令

AEGIS_SDK_DEV_DIR="/home/ryan/workspace/github/AegisTrader/packages/aegis-sdk-dev"

# 检查参数
if [ $# -eq 0 ]; then
    echo "Usage: ./run-aegis-cli.sh <command> [options]"
    echo ""
    echo "Available commands:"
    echo "  bootstrap        - Bootstrap a new AegisSDK service"
    echo "  config-validator - Validate configuration and troubleshoot"
    echo "  quickstart       - Launch quickstart wizard"
    echo "  test-runner      - Run tests"
    echo ""
    echo "Examples:"
    echo "  ./run-aegis-cli.sh bootstrap"
    echo "  ./run-aegis-cli.sh config-validator --service-name test --nats-url nats://localhost:4222"
    exit 1
fi

COMMAND=$1
shift

# 根据命令运行相应的 CLI
case $COMMAND in
    bootstrap)
        cd "$AEGIS_SDK_DEV_DIR" && uv run python -m aegis_sdk_dev.cli.bootstrap "$@"
        ;;
    config-validator)
        cd "$AEGIS_SDK_DEV_DIR" && uv run python -m aegis_sdk_dev.cli.config_validator "$@"
        ;;
    quickstart)
        cd "$AEGIS_SDK_DEV_DIR" && uv run python -m aegis_sdk_dev.cli.quickstart "$@"
        ;;
    test-runner)
        cd "$AEGIS_SDK_DEV_DIR" && uv run python -m aegis_sdk_dev.cli.test_runner "$@"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Run './run-aegis-cli.sh' without arguments to see available commands"
        exit 1
        ;;
esac
