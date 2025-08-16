"""
Data Quality Checker for Anti-Corruption Layer.

Validates and sanitizes data from external sources before it enters the domain.
Ensures data integrity, completeness, and consistency.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DataQualityIssue(BaseModel):
    """Represents a data quality issue found during validation."""

    model_config = ConfigDict(strict=True)

    field: str
    issue_type: str
    message: str
    severity: str = Field(default="warning")  # warning, error, critical
    raw_value: Any = None
    expected_value: Any = None


class DataQualityReport(BaseModel):
    """Report of data quality check results."""

    model_config = ConfigDict(strict=True)

    passed: bool
    issues: list[DataQualityIssue] = Field(default_factory=list)
    warnings_count: int = 0
    errors_count: int = 0
    critical_count: int = 0
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def add_issue(self, issue: DataQualityIssue) -> None:
        """Add an issue to the report."""
        self.issues.append(issue)

        if issue.severity == "warning":
            self.warnings_count += 1
        elif issue.severity == "error":
            self.errors_count += 1
            self.passed = False
        elif issue.severity == "critical":
            self.critical_count += 1
            self.passed = False


class TickDataQualityChecker:
    """Validates tick data quality from external sources."""

    def __init__(self):
        """Initialize with validation rules."""
        self.max_price_change_percent = 20.0  # Max 20% price change
        self.max_spread_percent = 5.0  # Max 5% bid-ask spread
        self.max_time_drift_seconds = 60  # Max 1 minute time drift
        self.min_price = Decimal("0.0001")  # Minimum valid price
        self.max_price = Decimal("1000000")  # Maximum valid price

    def check_tick_data(
        self, tick_data: dict, previous_tick: dict | None = None
    ) -> DataQualityReport:
        """
        Comprehensive tick data quality check.

        Validates:
        - Price sanity (positive, within bounds)
        - Volume validity
        - Timestamp accuracy
        - Sequence consistency
        - Price continuity (if previous tick provided)
        """
        report = DataQualityReport(passed=True)

        # Check price validity
        self._check_price(tick_data, report)

        # Check volume validity
        self._check_volume(tick_data, report)

        # Check timestamp validity
        self._check_timestamp(tick_data, report)

        # Check bid-ask spread if available
        self._check_spread(tick_data, report)

        # Check price continuity if previous tick provided
        if previous_tick:
            self._check_price_continuity(tick_data, previous_tick, report)
            self._check_sequence_continuity(tick_data, previous_tick, report)

        return report

    def _check_price(self, tick_data: dict, report: DataQualityReport) -> None:
        """Validate price data."""
        price = tick_data.get("price") or tick_data.get("LastPrice")

        if price is None:
            report.add_issue(
                DataQualityIssue(
                    field="price",
                    issue_type="missing_field",
                    message="Price field is missing",
                    severity="critical",
                )
            )
            return

        try:
            price_decimal = Decimal(str(price))

            if price_decimal <= 0:
                report.add_issue(
                    DataQualityIssue(
                        field="price",
                        issue_type="invalid_value",
                        message="Price must be positive",
                        severity="error",
                        raw_value=price,
                    )
                )

            if price_decimal < self.min_price:
                report.add_issue(
                    DataQualityIssue(
                        field="price",
                        issue_type="out_of_bounds",
                        message=f"Price below minimum threshold {self.min_price}",
                        severity="warning",
                        raw_value=price,
                    )
                )

            if price_decimal > self.max_price:
                report.add_issue(
                    DataQualityIssue(
                        field="price",
                        issue_type="out_of_bounds",
                        message=f"Price above maximum threshold {self.max_price}",
                        severity="warning",
                        raw_value=price,
                    )
                )

        except (ValueError, TypeError) as e:
            report.add_issue(
                DataQualityIssue(
                    field="price",
                    issue_type="invalid_format",
                    message=f"Invalid price format: {e}",
                    severity="critical",
                    raw_value=price,
                )
            )

    def _check_volume(self, tick_data: dict, report: DataQualityReport) -> None:
        """Validate volume data."""
        volume = tick_data.get("volume") or tick_data.get("Volume")

        if volume is None:
            # Volume can be optional for some tick types
            return

        try:
            volume_int = int(volume)

            if volume_int < 0:
                report.add_issue(
                    DataQualityIssue(
                        field="volume",
                        issue_type="invalid_value",
                        message="Volume cannot be negative",
                        severity="error",
                        raw_value=volume,
                    )
                )

            if volume_int > 1_000_000_000:  # Sanity check
                report.add_issue(
                    DataQualityIssue(
                        field="volume",
                        issue_type="suspicious_value",
                        message="Unusually high volume detected",
                        severity="warning",
                        raw_value=volume,
                    )
                )

        except (ValueError, TypeError) as e:
            report.add_issue(
                DataQualityIssue(
                    field="volume",
                    issue_type="invalid_format",
                    message=f"Invalid volume format: {e}",
                    severity="error",
                    raw_value=volume,
                )
            )

    def _check_timestamp(self, tick_data: dict, report: DataQualityReport) -> None:
        """Validate timestamp data."""
        timestamp = tick_data.get("timestamp") or tick_data.get("UpdateTime")

        if timestamp is None:
            report.add_issue(
                DataQualityIssue(
                    field="timestamp",
                    issue_type="missing_field",
                    message="Timestamp field is missing",
                    severity="critical",
                )
            )
            return

        try:
            # Handle different timestamp formats
            if isinstance(timestamp, int | float):
                # Unix timestamp
                if timestamp > 1e10:  # Milliseconds
                    timestamp = timestamp / 1000
                tick_time = datetime.fromtimestamp(timestamp, tz=UTC)
            elif isinstance(timestamp, str):
                # ISO format or other string format
                tick_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            else:
                tick_time = timestamp

            # Check for future timestamps
            now = datetime.now(UTC)
            if tick_time > now + timedelta(seconds=self.max_time_drift_seconds):
                report.add_issue(
                    DataQualityIssue(
                        field="timestamp",
                        issue_type="future_timestamp",
                        message="Timestamp is in the future",
                        severity="error",
                        raw_value=timestamp,
                    )
                )

            # Check for stale timestamps (older than 1 hour)
            if tick_time < now - timedelta(hours=1):
                report.add_issue(
                    DataQualityIssue(
                        field="timestamp",
                        issue_type="stale_timestamp",
                        message="Timestamp is older than 1 hour",
                        severity="warning",
                        raw_value=timestamp,
                    )
                )

        except Exception as e:
            report.add_issue(
                DataQualityIssue(
                    field="timestamp",
                    issue_type="invalid_format",
                    message=f"Invalid timestamp format: {e}",
                    severity="critical",
                    raw_value=timestamp,
                )
            )

    def _check_spread(self, tick_data: dict, report: DataQualityReport) -> None:
        """Check bid-ask spread if both are available."""
        bid = tick_data.get("bid") or tick_data.get("BidPrice")
        ask = tick_data.get("ask") or tick_data.get("AskPrice")

        if bid is None or ask is None:
            return

        try:
            bid_decimal = Decimal(str(bid))
            ask_decimal = Decimal(str(ask))

            if bid_decimal > ask_decimal:
                report.add_issue(
                    DataQualityIssue(
                        field="spread",
                        issue_type="inverted_spread",
                        message="Bid price is higher than ask price",
                        severity="critical",
                        raw_value=f"bid={bid}, ask={ask}",
                    )
                )

            if ask_decimal > 0:
                spread_percent = ((ask_decimal - bid_decimal) / ask_decimal) * 100

                if spread_percent > self.max_spread_percent:
                    report.add_issue(
                        DataQualityIssue(
                            field="spread",
                            issue_type="excessive_spread",
                            message=(
                                f"Spread {spread_percent:.2f}% exceeds maximum "
                                f"{self.max_spread_percent}%"
                            ),
                            severity="warning",
                            raw_value=f"bid={bid}, ask={ask}",
                        )
                    )

        except Exception as e:
            report.add_issue(
                DataQualityIssue(
                    field="spread",
                    issue_type="calculation_error",
                    message=f"Failed to calculate spread: {e}",
                    severity="warning",
                )
            )

    def _check_price_continuity(
        self, tick_data: dict, previous_tick: dict, report: DataQualityReport
    ) -> None:
        """Check for suspicious price jumps."""
        current_price = tick_data.get("price") or tick_data.get("LastPrice")
        previous_price = previous_tick.get("price") or previous_tick.get("LastPrice")

        if current_price is None or previous_price is None:
            return

        try:
            current_decimal = Decimal(str(current_price))
            previous_decimal = Decimal(str(previous_price))

            if previous_decimal > 0:
                change_percent = abs((current_decimal - previous_decimal) / previous_decimal) * 100

                if change_percent > self.max_price_change_percent:
                    report.add_issue(
                        DataQualityIssue(
                            field="price",
                            issue_type="excessive_change",
                            message=(
                                f"Price changed {change_percent:.2f}% "
                                f"(exceeds {self.max_price_change_percent}%)"
                            ),
                            severity="warning",
                            raw_value=current_price,
                            expected_value=(
                                f"within {self.max_price_change_percent}% of {previous_price}"
                            ),
                        )
                    )

        except Exception as e:
            report.add_issue(
                DataQualityIssue(
                    field="price_continuity",
                    issue_type="calculation_error",
                    message=f"Failed to check price continuity: {e}",
                    severity="warning",
                )
            )

    def _check_sequence_continuity(
        self, tick_data: dict, previous_tick: dict, report: DataQualityReport
    ) -> None:
        """Check for sequence gaps or duplicates."""
        current_seq = tick_data.get("sequence_number") or tick_data.get("UpdateMillisec")
        previous_seq = previous_tick.get("sequence_number") or previous_tick.get("UpdateMillisec")

        if current_seq is None or previous_seq is None:
            return

        try:
            if current_seq <= previous_seq:
                report.add_issue(
                    DataQualityIssue(
                        field="sequence_number",
                        issue_type="sequence_error",
                        message=(
                            f"Sequence not increasing "
                            f"(current={current_seq}, previous={previous_seq})"
                        ),
                        severity="warning",
                        raw_value=current_seq,
                        expected_value=f"> {previous_seq}",
                    )
                )

            # Check for large gaps (might indicate missing data)
            if current_seq - previous_seq > 1000:
                report.add_issue(
                    DataQualityIssue(
                        field="sequence_number",
                        issue_type="sequence_gap",
                        message=f"Large sequence gap detected ({current_seq - previous_seq} ticks)",
                        severity="warning",
                        raw_value=current_seq,
                        expected_value=f"close to {previous_seq}",
                    )
                )

        except Exception as e:
            report.add_issue(
                DataQualityIssue(
                    field="sequence_continuity",
                    issue_type="calculation_error",
                    message=f"Failed to check sequence continuity: {e}",
                    severity="warning",
                )
            )
