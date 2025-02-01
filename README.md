# IoT Telemetry Platform

A comprehensive data platform for IoT device management, driver behavior analytics, and natural language query capabilities.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   IoT Data Sources                           │
│           (Telematics, Sensors, Trip Events)                │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────▼────────┐
        │ Snowflake Cloud │
        └────────┬────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌────────┐ ┌──────────┐ ┌──────────┐
│  dbt   │ │  Spark   │ │ Airflow  │
│Semantic│ │  Driver  │ │ Device   │
│ Layer  │ │Behavior  │ │  Health  │
└────┬───┘ └────┬─────┘ └────┬─────┘
     │          │            │
     └────┬─────┴────┬───────┘
          │          │
     ┌────▼──┐  ┌───▼───────┐
     │Claude │  │  Serving   │
     │ API   │  │   Layer    │
     └───────┘  └────────────┘
```

## Projects

### 1. **dbt-semantic-layer** - Natural Language Query Foundation
- Semantic models with explicit column metadata
- YAML-based semantic graph definitions
- Trip history and device telemetry views
- Metadata constraints for LLM accuracy

### 2. **spark-driver-behavior** - Real-time Behavior Analytics  
- Dynamic schema evolution for varying device payloads
- Aggregates 50,000+ daily trip events
- Computes braking/acceleration features
- Drift detection with window functions

### 3. **device-health-validation** - Proactive Device Monitoring
- Rolling z-score threshold detection
- Great Expectations validation rules
- Airflow orchestration with Slack alerts
- 15,000 daily heartbeat events processing

### 4. **claude-api-integration** - NL Query Interface
- Token usage and latency tracking
- Prompt injection detection
- Context window optimization
- Query result caching

## Quick Start

```bash
# Install dependencies
make setup

# Run dbt semantic layer
cd dbt-semantic-layer && dbt run

# Deploy Spark jobs to Databricks
cd ../spark-driver-behavior && python jobs/aggregate_trips.py

# Deploy Airflow DAGs
cd ../device-health-validation && airflow dags backfill health_check_dag

# Start Claude API service
cd ../claude-api-integration && python app.py
```

## Data Flow

1. **Ingestion**: Raw IoT events → Snowflake raw tables
2. **Transformation**: dbt models + Spark aggregations
3. **Validation**: Great Expectations + Airflow checks
4. **Semantic Layer**: dbt semantic definitions + Claude context
5. **Serving**: API layer with NL query capability

## Key Metrics

- **Semantic Query Accuracy**: 92% (vs 65% baseline)
- **Pipeline Reliability**: 98% consistency (vs 86% baseline)
- **Device Health Detection**: 150 devices flagged in first month
- **Alert SLA**: 95% within 1 minute to Slack

## Configuration Files

- `config/` - Environment configs and secrets
- `docker-compose.yml` - Local dev environment
- `Makefile` - Common tasks
- `requirements.txt` - Python dependencies
