"""
Device health validation engine using Great Expectations
Monitors 15,000+ daily heartbeat events
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass

import pandas as pd
import numpy as np
from great_expectations.dataset import PandasDataset

logger = logging.getLogger(__name__)


@dataclass
class ThresholdConfig:
    """Configuration for z-score thresholds"""
    zscore_threshold: float = 2.5
    lookback_samples: int = 100
    battery_warning_percent: int = 25
    battery_critical_percent: int = 10
    signal_warning_dbm: int = -80
    temperature_warning_c: int = 60
    offline_threshold_minutes: int = 15


class DeviceHealthValidator:
    """Validates device health using Great Expectations and rolling z-score thresholds"""
    
    def __init__(self, config: ThresholdConfig = ThresholdConfig()):
        self.config = config
        self.ge_context = None
    
    def compute_zscore_thresholds(self, heartbeats_df: pd.DataFrame) -> Dict[str, Tuple[float, float]]:
        """
        Compute rolling z-score thresholds per device for anomaly detection
        
        Returns:
            Dict mapping device_id to (lower_bound, upper_bound) tuples
        """
        logger.info("Computing z-score thresholds per device...")
        
        thresholds = {}
        
        for device_id in heartbeats_df['device_id'].unique():
            device_data = heartbeats_df[heartbeats_df['device_id'] == device_id]
            
            if len(device_data) < self.config.lookback_samples:
                # Not enough history, use absolute thresholds
                thresholds[device_id] = (20, 100)  # battery % bounds
                continue
            
            recent_data = device_data.tail(self.config.lookback_samples)
            
            # Compute z-scores for battery level
            battery_values = recent_data['battery_percent'].values
            battery_mean = np.mean(battery_values)
            battery_std = np.std(battery_values)
            
            lower_bound = battery_mean - (self.config.zscore_threshold * battery_std)
            upper_bound = battery_mean + (self.config.zscore_threshold * battery_std)
            
            thresholds[device_id] = (max(lower_bound, 0), min(upper_bound, 100))
        
        logger.info(f"Computed thresholds for {len(thresholds)} devices")
        return thresholds
    
    def validate_heartbeats(self, heartbeats_df: pd.DataFrame) -> Dict[str, List[Dict]]:
        """
        Validate heartbeat data using Great Expectations percentile-based rules
        
        Returns:
            Dict with validation results and flagged issues
        """
        logger.info(f"Validating {len(heartbeats_df)} heartbeat records...")
        
        validation_results = {
            "total_records": len(heartbeats_df),
            "issues": [],
            "flagged_devices": set(),
            "validation_checks": []
        }
        
        # Create Great Expectations dataset
        ge_dataset = PandasDataset(heartbeats_df)
        
        # Define validation rules using percentile thresholds
        checks = [
            {
                "name": "battery_percent_valid_range",
                "check": lambda df: ge_dataset.expect_column_values_to_be_between(
                    "battery_percent", min_value=0, max_value=100
                ),
                "severity": "high"
            },
            {
                "name": "battery_low_warning",
                "check": lambda df: df[df['battery_percent'] < self.config.battery_warning_percent],
                "severity": "warning"
            },
            {
                "name": "battery_critical",
                "check": lambda df: df[df['battery_percent'] < self.config.battery_critical_percent],
                "severity": "critical"
            },
            {
                "name": "signal_strength_warning",
                "check": lambda df: df[df['signal_strength_dbm'] < self.config.signal_warning_dbm],
                "severity": "warning"
            },
            {
                "name": "temperature_warning",
                "check": lambda df: df[df['device_temperature_c'] > self.config.temperature_warning_c],
                "severity": "warning"
            }
        ]
        
        # Execute validation checks
        for check in checks:
            try:
                result = check["check"](heartbeats_df)
                
                if isinstance(result, pd.DataFrame) and len(result) > 0:
                    validation_results["validation_checks"].append({
                        "check_name": check["name"],
                        "severity": check["severity"],
                        "failed_records": len(result)
                    })
                    
                    # Add flagged devices
                    flagged = result['device_id'].unique().tolist()
                    validation_results["flagged_devices"].update(flagged)
                    
                    validation_results["issues"].extend([
                        {
                            "device_id": row["device_id"],
                            "check": check["name"],
                            "severity": check["severity"],
                            "value": row.get("battery_percent") or row.get("signal_strength_dbm") or row.get("device_temperature_c"),
                            "timestamp": row.get("heartbeat_timestamp")
                        }
                        for _, row in result.iterrows()
                    ])
            except Exception as e:
                logger.warning(f"Check {check['name']} failed: {str(e)}")
        
        validation_results["flagged_devices"] = list(validation_results["flagged_devices"])
        
        logger.info(f"Validation complete: {len(validation_results['flagged_devices'])} devices flagged")
        return validation_results
    
    def detect_offline_devices(self, heartbeats_df: pd.DataFrame) -> List[Dict]:
        """
        Detect devices that haven't sent heartbeats recently (offline anomalies)
        
        Returns:
            List of offline device records
        """
        logger.info("Detecting offline devices...")
        
        heartbeats_df['heartbeat_timestamp'] = pd.to_datetime(heartbeats_df['heartbeat_timestamp'])
        now = pd.Timestamp.utcnow()
        
        latest_heartbeats = heartbeats_df.sort_values('heartbeat_timestamp').groupby('device_id').tail(1)
        
        latest_heartbeats['minutes_since_heartbeat'] = (
            (now - latest_heartbeats['heartbeat_timestamp']).dt.total_seconds() / 60
        )
        
        offline_devices = latest_heartbeats[
            latest_heartbeats['minutes_since_heartbeat'] > self.config.offline_threshold_minutes
        ]
        
        offline_records = offline_devices[[
            'device_id', 'heartbeat_timestamp', 'minutes_since_heartbeat'
        ]].to_dict('records')
        
        logger.info(f"Detected {len(offline_records)} offline devices")
        return offline_records
    
    def compute_device_health_score(self, heartbeats_df: pd.DataFrame) -> Dict[str, float]:
        """
        Compute overall health score per device (0-100)
        
        Returns:
            Dict mapping device_id to health_score
        """
        logger.info("Computing device health scores...")
        
        health_scores = {}
        
        for device_id in heartbeats_df['device_id'].unique():
            device_data = heartbeats_df[heartbeats_df['device_id'] == device_id]
            
            # Initialize score
            score = 100.0
            
            # Battery penalty
            avg_battery = device_data['battery_percent'].mean()
            if avg_battery < self.config.battery_critical_percent:
                score -= 30
            elif avg_battery < self.config.battery_warning_percent:
                score -= 15
            else:
                score -= (100 - avg_battery) * 0.1  # Slight penalty for aging
            
            # Signal strength penalty
            avg_signal = device_data['signal_strength_dbm'].mean()
            if avg_signal < self.config.signal_warning_dbm:
                score -= 20
            else:
                score -= max(0, (avg_signal + 50) * 0.2)
            
            # Temperature penalty
            max_temp = device_data['device_temperature_c'].max()
            if max_temp > self.config.temperature_warning_c:
                score -= 25
            elif max_temp > 50:
                score -= 10
            
            # GPS accuracy penalty
            if 'gps_accuracy_meters' in device_data.columns:
                avg_accuracy = device_data['gps_accuracy_meters'].mean()
                if avg_accuracy > 100:
                    score -= 10
            
            health_scores[device_id] = max(0, min(100, score))
        
        logger.info(f"Computed health scores for {len(health_scores)} devices")
        return health_scores
    
    def validate_all(self, heartbeats_df: pd.DataFrame) -> Dict:
        """
        Run comprehensive validation suite
        
        Returns:
            Comprehensive validation report
        """
        logger.info("Starting comprehensive device health validation...")
        
        zscore_thresholds = self.compute_zscore_thresholds(heartbeats_df)
        validation_results = self.validate_heartbeats(heartbeats_df)
        offline_devices = self.detect_offline_devices(heartbeats_df)
        health_scores = self.compute_device_health_score(heartbeats_df)
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_devices": len(heartbeats_df['device_id'].unique()),
            "total_heartbeats": len(heartbeats_df),
            "zscore_thresholds": zscore_thresholds,
            "validation_results": validation_results,
            "offline_devices": offline_devices,
            "offline_count": len(offline_devices),
            "health_scores": health_scores,
            "critical_devices": [
                device_id for device_id, score in health_scores.items() if score < 30
            ],
            "warning_devices": [
                device_id for device_id, score in health_scores.items() if 30 <= score < 70
            ]
        }
        
        logger.info(f"""
        ═══════════════════════════════════════════
        Device Health Validation Report
        ═══════════════════════════════════════════
        Total Devices: {report['total_devices']}
        Total Heartbeats: {report['total_heartbeats']}
        Offline Devices: {report['offline_count']}
        Critical Health: {len(report['critical_devices'])}
        Warning Health: {len(report['warning_devices'])}
        Issues Found: {len(validation_results['issues'])}
        ═══════════════════════════════════════════
        """)
        
        return report
