"""
Comprehensive unit tests for Dashboard Configuration
Covers all models, visualizations, alerts, and export functionality
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from domain.gateway.dashboard_config import (
    AlertRule,
    AlertSeverity,
    DashboardSection,
    GatewayDashboardConfig,
    MetricPanel,
    VisualizationType,
    _map_visualization_to_grafana,
    create_default_dashboard_config,
    export_grafana_json,
)


class TestVisualizationType:
    """Test VisualizationType enum"""

    def test_all_visualization_types(self):
        """Test all visualization types are defined"""
        expected_types = [
            "gauge",
            "line_chart",
            "bar_chart",
            "heatmap",
            "stat",
            "table",
            "pie_chart",
            "histogram",
        ]

        for expected in expected_types:
            assert hasattr(VisualizationType, expected.upper())
            viz_type = getattr(VisualizationType, expected.upper())
            assert viz_type.value == expected

    def test_visualization_type_values(self):
        """Test visualization type enum values"""
        assert VisualizationType.GAUGE.value == "gauge"
        assert VisualizationType.LINE_CHART.value == "line_chart"
        assert VisualizationType.BAR_CHART.value == "bar_chart"
        assert VisualizationType.HEATMAP.value == "heatmap"
        assert VisualizationType.STAT.value == "stat"
        assert VisualizationType.TABLE.value == "table"
        assert VisualizationType.PIE_CHART.value == "pie_chart"
        assert VisualizationType.HISTOGRAM.value == "histogram"


class TestAlertSeverity:
    """Test AlertSeverity enum"""

    def test_all_severity_levels(self):
        """Test all severity levels are defined"""
        expected_levels = ["info", "warning", "error", "critical"]

        for expected in expected_levels:
            assert hasattr(AlertSeverity, expected.upper())
            severity = getattr(AlertSeverity, expected.upper())
            assert severity.value == expected

    def test_severity_values(self):
        """Test severity enum values"""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.ERROR.value == "error"
        assert AlertSeverity.CRITICAL.value == "critical"


class TestMetricPanel:
    """Test MetricPanel model"""

    def test_metric_panel_creation(self):
        """Test creating a metric panel with required fields"""
        panel = MetricPanel(
            title="Test Panel",
            description="Test Description",
            metric_name="test_metric",
            visualization=VisualizationType.GAUGE,
        )

        assert panel.title == "Test Panel"
        assert panel.description == "Test Description"
        assert panel.metric_name == "test_metric"
        assert panel.visualization == VisualizationType.GAUGE
        assert panel.unit is None
        assert panel.thresholds is None
        assert panel.refresh_interval_seconds == 30
        assert panel.width == 6
        assert panel.height == 4

    def test_metric_panel_with_optional_fields(self):
        """Test metric panel with all optional fields"""
        panel = MetricPanel(
            title="Test Panel",
            description="Test Description",
            metric_name="test_metric",
            visualization=VisualizationType.LINE_CHART,
            unit="ms",
            thresholds={"warning": 100, "critical": 500},
            refresh_interval_seconds=60,
            width=12,
            height=8,
        )

        assert panel.unit == "ms"
        assert panel.thresholds == {"warning": 100, "critical": 500}
        assert panel.refresh_interval_seconds == 60
        assert panel.width == 12
        assert panel.height == 8

    def test_metric_panel_validation(self):
        """Test metric panel validation"""
        with pytest.raises(ValidationError):
            # Missing required fields
            MetricPanel()  # type: ignore

    def test_metric_panel_dict_validation(self):
        """Test metric panel model validation with dict"""
        # Valid panel creation
        panel = MetricPanel(
            title="Test",
            description="Test",
            metric_name="test",
            visualization=VisualizationType.GAUGE,
        )
        assert panel.title == "Test"

        # Verify all fields are accessible
        assert hasattr(panel, "title")
        assert hasattr(panel, "description")
        assert hasattr(panel, "metric_name")
        assert hasattr(panel, "visualization")


class TestAlertRule:
    """Test AlertRule model"""

    def test_alert_rule_creation(self):
        """Test creating an alert rule"""
        rule = AlertRule(
            name="Test Alert",
            description="Test Description",
            metric_name="test_metric",
            condition="> 100",
            threshold=100,
            severity=AlertSeverity.WARNING,
        )

        assert rule.name == "Test Alert"
        assert rule.description == "Test Description"
        assert rule.metric_name == "test_metric"
        assert rule.condition == "> 100"
        assert rule.threshold == 100
        assert rule.severity == AlertSeverity.WARNING
        assert rule.duration_seconds == 60
        assert rule.notification_channels == []

    def test_alert_rule_with_notifications(self):
        """Test alert rule with notification channels"""
        rule = AlertRule(
            name="Critical Alert",
            description="Critical issue",
            metric_name="critical_metric",
            condition="== 0",
            threshold=0,
            severity=AlertSeverity.CRITICAL,
            duration_seconds=30,
            notification_channels=["slack", "email", "pagerduty"],
        )

        assert rule.duration_seconds == 30
        assert rule.notification_channels == ["slack", "email", "pagerduty"]

    def test_alert_rule_validation(self):
        """Test alert rule validation"""
        with pytest.raises(ValidationError):
            # Missing required fields
            AlertRule()  # type: ignore

    def test_alert_rule_dict_validation(self):
        """Test alert rule model validation with dict"""
        # Valid alert rule creation
        rule = AlertRule(
            name="Test",
            description="Test",
            metric_name="test",
            condition="> 0",
            threshold=0,
            severity=AlertSeverity.INFO,
        )
        assert rule.name == "Test"

        # Verify all fields are accessible
        assert hasattr(rule, "name")
        assert hasattr(rule, "description")
        assert hasattr(rule, "metric_name")
        assert hasattr(rule, "severity")


class TestDashboardSection:
    """Test DashboardSection model"""

    def test_dashboard_section_creation(self):
        """Test creating a dashboard section"""
        panels = [
            MetricPanel(
                title="Panel 1",
                description="Description 1",
                metric_name="metric_1",
                visualization=VisualizationType.GAUGE,
            ),
            MetricPanel(
                title="Panel 2",
                description="Description 2",
                metric_name="metric_2",
                visualization=VisualizationType.LINE_CHART,
            ),
        ]

        section = DashboardSection(
            title="Test Section",
            description="Test Description",
            panels=panels,
        )

        assert section.title == "Test Section"
        assert section.description == "Test Description"
        assert len(section.panels) == 2
        assert section.collapsed is False

    def test_dashboard_section_collapsed(self):
        """Test dashboard section with collapsed state"""
        section = DashboardSection(
            title="Collapsed Section",
            description="Initially collapsed",
            panels=[],
            collapsed=True,
        )

        assert section.collapsed is True

    def test_dashboard_section_validation(self):
        """Test dashboard section validation"""
        with pytest.raises(ValidationError):
            # Missing required fields
            DashboardSection()  # type: ignore


class TestGatewayDashboardConfig:
    """Test GatewayDashboardConfig model"""

    def test_dashboard_config_creation(self):
        """Test creating a dashboard configuration"""
        section = DashboardSection(
            title="Test Section",
            description="Test",
            panels=[
                MetricPanel(
                    title="Test Panel",
                    description="Test",
                    metric_name="test",
                    visualization=VisualizationType.GAUGE,
                )
            ],
        )

        alert = AlertRule(
            name="Test Alert",
            description="Test",
            metric_name="test",
            condition="> 0",
            threshold=0,
            severity=AlertSeverity.INFO,
        )

        config = GatewayDashboardConfig(
            sections=[section],
            alert_rules=[alert],
        )

        assert config.name == "Gateway Monitoring Dashboard"
        assert config.description == "Real-time monitoring of gateway connections and performance"
        assert config.refresh_interval_seconds == 10
        assert config.time_range_hours == 24
        assert len(config.sections) == 1
        assert len(config.alert_rules) == 1

    def test_dashboard_config_custom_values(self):
        """Test dashboard config with custom values"""
        config = GatewayDashboardConfig(
            name="Custom Dashboard",
            description="Custom Description",
            refresh_interval_seconds=30,
            time_range_hours=48,
            sections=[],
            alert_rules=[],
        )

        assert config.name == "Custom Dashboard"
        assert config.description == "Custom Description"
        assert config.refresh_interval_seconds == 30
        assert config.time_range_hours == 48


class TestCreateDefaultDashboardConfig:
    """Test create_default_dashboard_config function"""

    def test_default_dashboard_structure(self):
        """Test the structure of default dashboard"""
        config = create_default_dashboard_config()

        assert isinstance(config, GatewayDashboardConfig)
        assert config.name == "Gateway Monitoring Dashboard"
        assert len(config.sections) == 6
        assert len(config.alert_rules) == 7

    def test_default_dashboard_sections(self):
        """Test default dashboard has expected sections"""
        config = create_default_dashboard_config()

        section_titles = [s.title for s in config.sections]
        expected_titles = [
            "Connection Status",
            "Heartbeat Monitoring",
            "Failover Performance",
            "Connection Attempts",
            "Error Analysis",
            "Message Flow",
        ]

        assert section_titles == expected_titles

    def test_connection_status_section(self):
        """Test connection status section content"""
        config = create_default_dashboard_config()
        connection_section = config.sections[0]

        assert connection_section.title == "Connection Status"
        assert len(connection_section.panels) == 4

        panel_titles = [p.title for p in connection_section.panels]
        assert "Connection Status" in panel_titles
        assert "Circuit Breaker State" in panel_titles
        assert "Connection Success Rate" in panel_titles
        assert "Uptime" in panel_titles

    def test_heartbeat_monitoring_section(self):
        """Test heartbeat monitoring section"""
        config = create_default_dashboard_config()
        heartbeat_section = config.sections[1]

        assert heartbeat_section.title == "Heartbeat Monitoring"
        assert len(heartbeat_section.panels) == 3

        # Check visualization types
        visualizations = [p.visualization for p in heartbeat_section.panels]
        assert VisualizationType.LINE_CHART in visualizations
        assert VisualizationType.STAT in visualizations
        assert VisualizationType.HISTOGRAM in visualizations

    def test_alert_rules_severities(self):
        """Test alert rules have appropriate severities"""
        config = create_default_dashboard_config()

        # Check critical alerts
        critical_alerts = [r for r in config.alert_rules if r.severity == AlertSeverity.CRITICAL]
        assert len(critical_alerts) == 1
        assert critical_alerts[0].name == "Gateway Disconnected"

        # Check error alerts
        error_alerts = [r for r in config.alert_rules if r.severity == AlertSeverity.ERROR]
        assert len(error_alerts) >= 2

        # Check warning alerts
        warning_alerts = [r for r in config.alert_rules if r.severity == AlertSeverity.WARNING]
        assert len(warning_alerts) >= 3

    def test_alert_notification_channels(self):
        """Test alert notification channels"""
        config = create_default_dashboard_config()

        # Critical alert should have multiple channels
        critical_alert = next(r for r in config.alert_rules if r.name == "Gateway Disconnected")
        assert "slack" in critical_alert.notification_channels
        assert "email" in critical_alert.notification_channels
        assert "pagerduty" in critical_alert.notification_channels


class TestExportGrafanaJson:
    """Test export_grafana_json function"""

    def test_export_basic_dashboard(self):
        """Test exporting a basic dashboard to Grafana JSON"""
        section = DashboardSection(
            title="Test Section",
            description="Test",
            panels=[
                MetricPanel(
                    title="Test Panel",
                    description="Test Description",
                    metric_name="test_metric",
                    visualization=VisualizationType.GAUGE,
                    width=6,
                    height=4,
                )
            ],
        )

        config = GatewayDashboardConfig(
            name="Test Dashboard",
            description="Test Description",
            refresh_interval_seconds=30,
            time_range_hours=12,
            sections=[section],
            alert_rules=[],
        )

        result = export_grafana_json(config)

        assert "dashboard" in result
        dashboard = result["dashboard"]
        assert dashboard["title"] == "Test Dashboard"
        assert dashboard["description"] == "Test Description"
        assert dashboard["refresh"] == "30s"
        assert dashboard["time"]["from"] == "now-12h"
        assert dashboard["time"]["to"] == "now"
        assert len(dashboard["panels"]) == 2  # Section header + panel

    def test_export_panel_positions(self):
        """Test panel positioning in exported JSON"""
        panels = [
            MetricPanel(
                title=f"Panel {i}",
                description="Test",
                metric_name=f"metric_{i}",
                visualization=VisualizationType.GAUGE,
                width=6,
                height=4,
            )
            for i in range(4)
        ]

        section = DashboardSection(
            title="Test Section",
            description="Test",
            panels=panels,
        )

        config = GatewayDashboardConfig(
            sections=[section],
            alert_rules=[],
        )

        result = export_grafana_json(config)
        panels_json = result["dashboard"]["panels"]

        # First panel is section header
        assert panels_json[0]["type"] == "row"
        assert panels_json[0]["gridPos"]["y"] == 0

        # Check panel positions
        for i, panel in enumerate(panels_json[1:5], 1):
            expected_x = ((i - 1) % 4) * 6
            assert panel["gridPos"]["x"] == expected_x
            assert panel["gridPos"]["w"] == 6
            assert panel["gridPos"]["h"] == 4

    def test_export_with_thresholds(self):
        """Test exporting panels with thresholds"""
        panel = MetricPanel(
            title="Threshold Panel",
            description="Test",
            metric_name="test_metric",
            visualization=VisualizationType.GAUGE,
            unit="ms",
            thresholds={"warning": 100, "critical": 500},
        )

        section = DashboardSection(
            title="Test Section",
            description="Test",
            panels=[panel],
        )

        config = GatewayDashboardConfig(
            sections=[section],
            alert_rules=[],
        )

        result = export_grafana_json(config)
        panel_json = result["dashboard"]["panels"][1]  # Skip section header

        assert "fieldConfig" in panel_json
        field_config = panel_json["fieldConfig"]["defaults"]
        assert field_config["unit"] == "ms"
        assert "thresholds" in field_config

        steps = field_config["thresholds"]["steps"]
        assert len(steps) == 3
        assert steps[1]["value"] == 100
        assert steps[1]["color"] == "yellow"
        assert steps[2]["value"] == 500
        assert steps[2]["color"] == "red"

    def test_export_collapsed_section(self):
        """Test exporting collapsed sections"""
        section = DashboardSection(
            title="Collapsed Section",
            description="Test",
            panels=[],
            collapsed=True,
        )

        config = GatewayDashboardConfig(
            sections=[section],
            alert_rules=[],
        )

        result = export_grafana_json(config)
        section_header = result["dashboard"]["panels"][0]

        assert section_header["collapsed"] is True

    def test_export_multiple_sections(self):
        """Test exporting multiple sections"""
        sections = [
            DashboardSection(
                title=f"Section {i}",
                description="Test",
                panels=[
                    MetricPanel(
                        title=f"Panel {i}",
                        description="Test",
                        metric_name=f"metric_{i}",
                        visualization=VisualizationType.GAUGE,
                        height=4,
                        width=6,
                    )
                ],
            )
            for i in range(3)
        ]

        config = GatewayDashboardConfig(
            sections=sections,
            alert_rules=[],
        )

        result = export_grafana_json(config)
        panels = result["dashboard"]["panels"]

        # Should have 3 section headers + 3 panels = 6 total
        assert len(panels) == 6

        # Check Y positions are increasing
        y_positions = [p["gridPos"]["y"] for p in panels]
        assert y_positions == sorted(y_positions)

    def test_export_default_dashboard(self):
        """Test exporting the default dashboard configuration"""
        config = create_default_dashboard_config()
        result = export_grafana_json(config)

        assert "dashboard" in result
        dashboard = result["dashboard"]
        assert dashboard["title"] == "Gateway Monitoring Dashboard"
        assert len(dashboard["panels"]) > 0

        # Check that all panels have required fields
        for panel in dashboard["panels"]:
            assert "id" in panel
            assert "type" in panel
            assert "gridPos" in panel
            if panel["type"] != "row":
                assert "targets" in panel


class TestMapVisualizationToGrafana:
    """Test _map_visualization_to_grafana function"""

    def test_visualization_mapping(self):
        """Test mapping all visualization types to Grafana"""
        mappings = {
            VisualizationType.GAUGE: "gauge",
            VisualizationType.LINE_CHART: "timeseries",
            VisualizationType.BAR_CHART: "barchart",
            VisualizationType.HEATMAP: "heatmap",
            VisualizationType.STAT: "stat",
            VisualizationType.TABLE: "table",
            VisualizationType.PIE_CHART: "piechart",
            VisualizationType.HISTOGRAM: "histogram",
        }

        for viz_type, expected in mappings.items():
            result = _map_visualization_to_grafana(viz_type)
            assert result == expected

    def test_unknown_visualization_fallback(self):
        """Test fallback for unknown visualization type"""

        # Create a mock unknown type
        class UnknownViz:
            value = "unknown"

        result = _map_visualization_to_grafana(UnknownViz())  # type: ignore
        assert result == "graph"  # Should fallback to graph


class TestPanelWrapping:
    """Test panel wrapping behavior in export"""

    def test_panels_wrap_to_next_row(self):
        """Test that panels wrap to next row when width exceeds 24"""
        panels = [
            MetricPanel(
                title=f"Panel {i}",
                description="Test",
                metric_name=f"metric_{i}",
                visualization=VisualizationType.GAUGE,
                width=8,  # 3 panels * 8 = 24, 4th should wrap
                height=4,
            )
            for i in range(5)
        ]

        section = DashboardSection(
            title="Test Section",
            description="Test",
            panels=panels,
        )

        config = GatewayDashboardConfig(
            sections=[section],
            alert_rules=[],
        )

        result = export_grafana_json(config)
        panels_json = result["dashboard"]["panels"]

        # Skip section header (index 0)
        # First row: panels 1-3 (x=0, 8, 16, y=1)
        assert panels_json[1]["gridPos"]["x"] == 0
        assert panels_json[1]["gridPos"]["y"] == 1
        assert panels_json[2]["gridPos"]["x"] == 8
        assert panels_json[2]["gridPos"]["y"] == 1
        assert panels_json[3]["gridPos"]["x"] == 16
        assert panels_json[3]["gridPos"]["y"] == 1

        # Second row: panels 4-5 (x=0, 8, y=5)
        assert panels_json[4]["gridPos"]["x"] == 0
        assert panels_json[4]["gridPos"]["y"] == 5
        assert panels_json[5]["gridPos"]["x"] == 8
        assert panels_json[5]["gridPos"]["y"] == 5
