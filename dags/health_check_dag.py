"""
Airflow DAG for device health monitoring and validation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.slack_webhook import SlackWebhookOperator
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
import pandas as pd

from health_validator import DeviceHealthValidator, ThresholdConfig

logger = logging.getLogger(__name__)

# DAG Configuration
default_args = {
    'owner': 'iot-platform',
    'depends_on_past': False,
    'start_date': datetime(2025, 2, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'health_check_dag',
    default_args=default_args,
    description='Device health monitoring with Great Expectations',
    schedule_interval='*/15 * * * *',  # Every 15 minutes
    catchup=False,
    max_active_runs=1,
)


def load_heartbeat_data(**context: Dict[str, Any]) -> str:
    """Load latest heartbeat data from Snowflake"""
    logger.info("Loading heartbeat data...")
    
    import snowflake.connector
    
    conn = snowflake.connector.connect(
        user=Variable.get("snowflake_user"),
        password=Variable.get("snowflake_password"),
        account=Variable.get("snowflake_account"),
        warehouse=Variable.get("snowflake_warehouse"),
        database=Variable.get("snowflake_database"),
    )
    
    query = """
    SELECT 
        heartbeat_id,
        device_id,
        heartbeat_timestamp,
        signal_strength_dbm,
        battery_percent,
        gps_accuracy_meters,
        device_temperature_c
    FROM raw.sensor_heartbeats
    WHERE heartbeat_timestamp >= DATEADD(HOUR, -1, CURRENT_TIMESTAMP())
    ORDER BY heartbeat_timestamp DESC
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    logger.info(f"Loaded {len(df)} heartbeat records")
    
    # Push to XCom for downstream tasks
    context['task_instance'].xcom_push(key='heartbeats_df', value=df.to_json())
    
    return f"Loaded {len(df)} records"


def validate_device_health(**context: Dict[str, Any]) -> Dict[str, Any]:
    """Validate device health and detect anomalies"""
    logger.info("Validating device health...")
    
    # Retrieve heartbeat data from XCom
    ti = context['task_instance']
    heartbeats_json = ti.xcom_pull(task_ids='load_heartbeat_data', key='heartbeats_df')
    heartbeats_df = pd.read_json(heartbeats_json)
    
    # Run validation
    config = ThresholdConfig(
        zscore_threshold=2.5,
        battery_warning_percent=int(Variable.get("battery_warning_percent", 25)),
        offline_threshold_minutes=int(Variable.get("offline_threshold_minutes", 15))
    )
    
    validator = DeviceHealthValidator(config)
    report = validator.validate_all(heartbeats_df)
    
    # Push report to XCom
    ti.xcom_push(key='validation_report', value=report)
    
    return report


def flag_degraded_devices(**context: Dict[str, Any]) -> Dict[str, Any]:
    """Identify and flag degraded devices for operational triage"""
    logger.info("Flagging degraded devices...")
    
    ti = context['task_instance']
    report = ti.xcom_pull(task_ids='validate_device_health', key='validation_report')
    
    degraded_summary = {
        'timestamp': datetime.utcnow().isoformat(),
        'critical_devices': report.get('critical_devices', []),
        'warning_devices': report.get('warning_devices', []),
        'offline_devices': report.get('offline_devices', []),
        'total_issues': len(report.get('critical_devices', [])) + 
                       len(report.get('warning_devices', [])) +
                       len(report.get('offline_devices', []))
    }
    
    # Log summary
    logger.info(f"Degraded devices summary: {degraded_summary}")
    
    # Push to XCom
    ti.xcom_push(key='degraded_summary', value=degraded_summary)
    
    return degraded_summary


def send_slack_alert(**context: Dict[str, Any]) -> None:
    """Send Slack alert with validation results"""
    logger.info("Preparing Slack alert...")
    
    ti = context['task_instance']
    report = ti.xcom_pull(task_ids='validate_device_health', key='validation_report')
    summary = ti.xcom_pull(task_ids='flag_degraded_devices', key='degraded_summary')
    
    # Only send if there are issues
    if summary['total_issues'] == 0:
        logger.info("No issues detected, skipping Slack alert")
        return
    
    # Format message
    message_blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚨 Device Health Alert"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Total Devices:*\n{report['total_devices']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Critical:*\n{len(summary['critical_devices'])}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Warning:*\n{len(summary['warning_devices'])}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Offline:*\n{len(summary['offline_devices'])}"
                }
            ]
        }
    ]
    
    # Add critical devices if any
    if summary['critical_devices']:
        message_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Critical Devices:*\n{', '.join(summary['critical_devices'][:5])}"
            }
        })
    
    context['task_instance'].xcom_push(key='slack_message', value=message_blocks)


def write_validation_results(**context: Dict[str, Any]) -> None:
    """Write validation results to Snowflake for audit trail"""
    logger.info("Writing validation results to Snowflake...")
    
    ti = context['task_instance']
    report = ti.xcom_pull(task_ids='validate_device_health', key='validation_report')
    
    import snowflake.connector
    import json
    
    conn = snowflake.connector.connect(
        user=Variable.get("snowflake_user"),
        password=Variable.get("snowflake_password"),
        account=Variable.get("snowflake_account"),
        warehouse=Variable.get("snowflake_warehouse"),
        database=Variable.get("snowflake_database"),
    )
    
    cur = conn.cursor()
    
    insert_query = """
    INSERT INTO analytics.validation_audit_log 
    (validation_timestamp, total_devices, critical_count, warning_count, offline_count, validation_report)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    
    cur.execute(insert_query, (
        datetime.utcnow(),
        report['total_devices'],
        len(report.get('critical_devices', [])),
        len(report.get('warning_devices', [])),
        report.get('offline_count', 0),
        json.dumps(report)
    ))
    
    conn.commit()
    cur.close()
    conn.close()
    
    logger.info("Validation results written to Snowflake")


# Define DAG tasks
with dag:
    
    with TaskGroup("data_preparation") as data_prep:
        load_task = PythonOperator(
            task_id='load_heartbeat_data',
            python_callable=load_heartbeat_data,
            provide_context=True,
        )
    
    with TaskGroup("validation") as validation:
        validate_task = PythonOperator(
            task_id='validate_device_health',
            python_callable=validate_device_health,
            provide_context=True,
        )
        
        flag_task = PythonOperator(
            task_id='flag_degraded_devices',
            python_callable=flag_degraded_devices,
            provide_context=True,
        )
        
        validate_task >> flag_task
    
    with TaskGroup("alerting") as alerting:
        slack_task = PythonOperator(
            task_id='prepare_slack_alert',
            python_callable=send_slack_alert,
            provide_context=True,
        )
        
        write_task = PythonOperator(
            task_id='write_validation_results',
            python_callable=write_validation_results,
            provide_context=True,
        )
    
    # Task dependencies
    data_prep >> validation >> alerting
