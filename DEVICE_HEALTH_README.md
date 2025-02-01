# Device Health Validation Engine

Real-time monitoring of 15,000+ daily heartbeat events with Great Expectations and rolling z-score anomaly detection.

## Features

- **Z-Score Thresholds**: Rolling z-score calculation per device for anomaly detection
- **Percentile Validation**: Great Expectations rules for battery, signal, and temperature thresholds
- **Offline Detection**: Identifies devices offline beyond configured threshold
- **Health Scoring**: Composite health score (0-100) per device
- **Airflow Integration**: Automated 15-minute checks with Slack alerts
- **Audit Trail**: All validation results logged to Snowflake

## Timeline

- **Feb 2025 - Apr 2025**: Initial development and deployment
- 150 degraded devices flagged in first month
- 95% of alerts delivered to Slack within 1 minute

## Key Metrics

- **Processing**: 15,000 heartbeat events daily
- **Alert SLA**: 95% delivery within 1 minute
- **Devices Detected**: 150 degraded devices (first month)
- **Uptime**: Production-grade monitoring

## Architecture

```
Snowflake (raw heartbeats)
    ↓
Airflow DAG (15min schedule)
    ↓
DeviceHealthValidator
    ├─ Z-Score Analysis
    ├─ Great Expectations Rules
    ├─ Offline Detection
    └─ Health Scoring
    ↓
Slack Alerts + Snowflake Audit
```

## Configuration

See `.env.example` for all environment variables.

Key configs:
- `zscore_threshold`: 2.5 (default)
- `battery_warning_percent`: 25%
- `battery_critical_percent`: 10%
- `offline_threshold_minutes`: 15

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run validation locally
python validators/health_validator.py

# Deploy Airflow DAG
airflow dags import dags/health_check_dag.py
airflow dags unpause health_check_dag
```

## Files

- `validators/health_validator.py` - Core validation logic
- `dags/health_check_dag.py` - Airflow orchestration
- `dags/config.py` - Configuration management
