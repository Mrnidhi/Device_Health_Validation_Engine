"""
Configuration for Airflow device health monitoring DAG
"""

from airflow.models import Variable

# Load configuration from Airflow Variables
# These should be set in Airflow UI or via env_var in docker-compose

SNOWFLAKE_CONFIG = {
    'account': Variable.get("snowflake_account", "dev"),
    'user': Variable.get("snowflake_user", "transformer"),
    'password': Variable.get("snowflake_password"),
    'warehouse': Variable.get("snowflake_warehouse", "compute_wh"),
    'database': Variable.get("snowflake_database", "iot_telemetry_dev"),
}

SLACK_CONFIG = {
    'webhook_url': Variable.get("slack_webhook_url"),
    'channel': Variable.get("slack_channel", "#alerts"),
}

VALIDATION_CONFIG = {
    'zscore_threshold': float(Variable.get("zscore_threshold", 2.5)),
    'battery_warning_percent': int(Variable.get("battery_warning_percent", 25)),
    'battery_critical_percent': int(Variable.get("battery_critical_percent", 10)),
    'offline_threshold_minutes': int(Variable.get("offline_threshold_minutes", 15)),
    'temperature_warning_c': int(Variable.get("temperature_warning_c", 60)),
}

# DAG scheduling
SCHEDULE_INTERVAL = Variable.get("dag_schedule_interval", "*/15 * * * *")  # Every 15 minutes

# Alert thresholds
ALERT_THRESHOLDS = {
    'critical_device_count': int(Variable.get("critical_alert_threshold", 10)),
    'warning_device_count': int(Variable.get("warning_alert_threshold", 30)),
}
