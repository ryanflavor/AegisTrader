"""Tests for risk domain models."""

from datetime import UTC, datetime

from risk_service.domain_models import Position, RiskAssessment, RiskLevel


class TestRiskDomainModels:
    """Test cases for risk domain models."""

    def test_risk_assessment_creation(self):
        """Test creating a valid risk assessment."""
        assessment = RiskAssessment(
            order_id="ORD-000001",
            symbol="AAPL",
            risk_level=RiskLevel.LOW,
            risk_score=15.5,
            risk_factors=["LOW_VOLUME", "NORMAL_PRICE"],
            position_limit=1000.0,
            current_position=100.0,
            new_position=200.0,
            assessment_time=datetime.now(UTC),
            instance_id="risk-01",
        )

        assert assessment.order_id == "ORD-000001"
        assert assessment.risk_level == RiskLevel.LOW
        assert assessment.risk_score == 15.5
        assert assessment.risk_factors == ["LOW_VOLUME", "NORMAL_PRICE"]
        assert assessment.instance_id == "risk-01"

    def test_position_creation(self):
        """Test creating a position."""
        position = Position(
            symbol="AAPL", position=150.0, timestamp=datetime.now(UTC), instance_id="risk-01"
        )

        assert position.symbol == "AAPL"
        assert position.position == 150.0
        assert position.instance_id == "risk-01"

    def test_risk_assessment_model_dump(self):
        """Test model serialization."""
        assessment = RiskAssessment(
            order_id="ORD-000002",
            symbol="TSLA",
            risk_level=RiskLevel.HIGH,
            risk_score=85.0,
            risk_factors=["HIGH_VOLUME", "VOLATILE_PRICE"],
            position_limit=500.0,
            current_position=400.0,
            new_position=500.0,
            assessment_time=datetime(2024, 1, 1, tzinfo=UTC),
            instance_id="risk-02",
        )

        data = assessment.model_dump()

        assert data["order_id"] == "ORD-000002"
        assert data["risk_level"] == "HIGH"
        assert data["risk_score"] == 85.0
        assert data["risk_factors"] == ["HIGH_VOLUME", "VOLATILE_PRICE"]
        assert data["instance_id"] == "risk-02"
