"""
Storage Context (通用子域)

This infrastructure context handles data persistence:
- ClickHouse integration for time-series data
- Historical data storage and retrieval
- Data archival and retention policies
- Query optimization for large datasets

Key Components:
- ClickHouseRepository: Interface to ClickHouse database
- DataWriter: High-performance batch writer
- DataReader: Optimized query interface
- RetentionManager: Manages data lifecycle and archival

Responsibilities:
- Store market data efficiently in ClickHouse
- Provide fast query access to historical data
- Manage data retention and archival
- Optimize storage for time-series patterns
"""
