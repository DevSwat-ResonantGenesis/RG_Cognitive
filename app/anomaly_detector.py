"""Anomaly detection engine for cognitive service."""

import math
import random
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class AnomalyDetector:
    """Simple anomaly detection using statistical methods."""

    def __init__(self):
        self.baseline_window = 100  # Number of events for baseline
        self.threshold_multiplier = 2.0  # Standard deviations for anomaly

    def calculate_score(
        self,
        current_value: float,
        historical_values: List[float],
    ) -> Tuple[float, str]:
        """Calculate anomaly score based on historical data.
        
        Returns (score, severity) where score is 0-1 and severity is low/medium/high/critical.
        """
        if not historical_values:
            return 0.0, "low"

        # Calculate mean and standard deviation
        mean = sum(historical_values) / len(historical_values)
        variance = sum((x - mean) ** 2 for x in historical_values) / len(historical_values)
        std_dev = math.sqrt(variance) if variance > 0 else 1.0

        # Calculate z-score
        z_score = abs(current_value - mean) / std_dev if std_dev > 0 else 0

        # Normalize to 0-1 score
        score = min(1.0, z_score / 5.0)  # 5 std devs = max score

        # Determine severity
        if score >= 0.8:
            severity = "critical"
        elif score >= 0.6:
            severity = "high"
        elif score >= 0.4:
            severity = "medium"
        else:
            severity = "low"

        return score, severity

    def detect_frequency_anomaly(
        self,
        events: List[datetime],
        window_minutes: int = 60,
    ) -> Tuple[float, str, str]:
        """Detect anomalies in event frequency.
        
        Returns (score, severity, description).
        """
        if len(events) < 10:
            return 0.0, "low", "Insufficient data for frequency analysis"

        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)

        # Count events in current window
        current_count = sum(1 for e in events if e >= window_start)

        # Calculate historical averages (excluding current window)
        historical_events = [e for e in events if e < window_start]
        if not historical_events:
            return 0.0, "low", "No historical data"

        # Group by window
        windows = []
        temp_start = min(historical_events)
        while temp_start < window_start:
            temp_end = temp_start + timedelta(minutes=window_minutes)
            count = sum(1 for e in historical_events if temp_start <= e < temp_end)
            windows.append(count)
            temp_start = temp_end

        if not windows:
            return 0.0, "low", "No historical windows"

        score, severity = self.calculate_score(current_count, windows)
        avg = sum(windows) / len(windows)

        if current_count > avg:
            description = f"Event frequency spike: {current_count} events vs {avg:.1f} average"
        else:
            description = f"Event frequency drop: {current_count} events vs {avg:.1f} average"

        return score, severity, description

    def detect_pattern_anomaly(
        self,
        payload: str,
        known_patterns: List[str],
    ) -> Tuple[float, str, str]:
        """Detect anomalies in event patterns/content."""
        if not payload or not known_patterns:
            return 0.0, "low", "No pattern data"

        # Simple pattern matching (in production, use ML)
        payload_lower = payload.lower()

        # Check for suspicious patterns
        suspicious_keywords = [
            "error", "failed", "exception", "unauthorized", "denied",
            "timeout", "crash", "critical", "warning", "alert"
        ]

        matches = sum(1 for kw in suspicious_keywords if kw in payload_lower)
        score = min(1.0, matches / 3.0)

        if score >= 0.8:
            severity = "critical"
        elif score >= 0.6:
            severity = "high"
        elif score >= 0.4:
            severity = "medium"
        else:
            severity = "low"

        if matches > 0:
            description = f"Suspicious pattern detected: {matches} warning indicators"
        else:
            description = "Normal pattern"

        return score, severity, description


anomaly_detector = AnomalyDetector()
