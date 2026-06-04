"""
Log Processor Worker

Processes logs in background:
1. Aggregates logs into time windows
2. Extracts features
3. Runs anomaly detectors
4. Generates alerts
5. Sends real-time updates via SSE
"""
import time
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np
from app import db
from app.models import LogEntry, MetricEntry, Feature, DetectionResult, Alert
from app.workers import worker_status


class LogProcessor:
    """Background worker to process logs and detect anomalies"""

    def __init__(self, app, log_queue):
        """
        Initialize processor

        Args:
            app: Flask app instance
            log_queue: Queue to receive events
        """
        self.app = app
        self.queue = log_queue
        self.window_minutes = app.config.get('WINDOW_MINUTES', 5)
        self.running = False

        # Cache for current window data
        self.current_window = None
        self.window_logs = []
        self.window_metrics = []

        # Load or initialize detectors
        self.detectors_ready = False
        self.rule_detector = None
        self.if_detector = None
        self.var_detector = None
        self.deeplog_detector = None

    def run(self):
        """Main worker loop"""
        self.running = True

        with self.app.app_context():
            self.app.logger.info("Log processor started")

            # Initialize detectors
            self._init_detectors()

            # Start processing loop
            last_window_check = datetime.utcnow()

            while self.running:
                try:
                    # Process queue events
                    try:
                        event = self.queue.get(timeout=1)
                        self._handle_event(event)
                    except:
                        pass  # Queue empty, continue

                    # Check if time to process window
                    now = datetime.utcnow()
                    check_interval = self.app.config.get('WINDOW_CHECK_INTERVAL', 10)  # Default 10 seconds
                    if (now - last_window_check).total_seconds() >= check_interval:
                        self._check_and_process_windows()
                        last_window_check = now

                except Exception as e:
                    self.app.logger.error(f"Error in processor loop: {e}")
                    worker_status['errors'] += 1
                    time.sleep(1)

            self.app.logger.info("Log processor stopped")

    def _handle_event(self, event):
        """Handle queue event"""
        event_type = event.get('type')

        if event_type == 'shutdown':
            self.running = False
        elif event_type == 'logs_received':
            # Trigger processing check
            pass
        elif event_type == 'metrics_received':
            # Trigger processing check
            pass

    def _init_detectors(self):
        """Initialize detection models"""
        try:
            from detectors.rule_based import RuleBasedDetector
            from detectors.ml_models import IsolationForestDetector
            from detectors.statistical import VARDetector
            from detectors.deeplog import DeepLogDetector

            # Rule-based detector
            self.rule_detector = RuleBasedDetector()
            self.app.logger.info("[OK] Rule-based detector initialized")

            # Isolation Forest detector
            self.if_detector = IsolationForestDetector()
            try:
                self.if_detector.load_model('data/models/isolation_forest.pkl')
                self.app.logger.info("[OK] Loaded Isolation Forest model")
            except:
                self.app.logger.warning("[WARN] Isolation Forest model not found, will train on first batch")

            # VAR detector
            self.var_detector = VARDetector()
            self.app.logger.info("[OK] VAR detector initialized")

            # DeepLog detector
            self.deeplog_detector = DeepLogDetector()
            try:
                self.deeplog_detector.load_model('data/models/deeplog')
                if self.deeplog_detector.model is not None:
                    self.app.logger.info("[OK] Loaded DeepLog model")
                else:
                    self.app.logger.warning("[WARN] DeepLog model not found, will train on first batch")
            except Exception as e:
                self.app.logger.warning(f"[WARN] DeepLog model load failed: {e}")

            self.detectors_ready = True
            self.app.logger.info("[OK] All 4 detectors initialized (Rule-based, IF, VAR, DeepLog)")

        except Exception as e:
            self.app.logger.error(f"Error initializing detectors: {e}")
            self.detectors_ready = False

    def _check_and_process_windows(self):
        """Check if there are complete windows to process"""
        try:
            # Get the latest processed window
            latest_feature = Feature.query.order_by(Feature.timestamp.desc()).first()

            if latest_feature:
                start_time = latest_feature.timestamp + timedelta(minutes=self.window_minutes)
            else:
                # First window, start from earliest log
                earliest_log = LogEntry.query.order_by(LogEntry.timestamp).first()
                if not earliest_log:
                    return  # No logs yet
                start_time = self._round_to_window(earliest_log.timestamp)

            # Process all complete windows
            now = datetime.utcnow()
            current_window = self._round_to_window(now)

            window_time = start_time
            while window_time < current_window:
                self._process_window(window_time)
                window_time += timedelta(minutes=self.window_minutes)

        except Exception as e:
            self.app.logger.error(f"Error checking windows: {e}")

    def _round_to_window(self, dt):
        """Round datetime to window boundary"""
        minutes = (dt.minute // self.window_minutes) * self.window_minutes
        return dt.replace(minute=minutes, second=0, microsecond=0)

    def _process_window(self, window_start):
        """Process a single time window"""
        try:
            window_end = window_start + timedelta(minutes=self.window_minutes)

            self.app.logger.info(f"Processing window: {window_start}")

            # Extract features
            features = self._extract_features(window_start, window_end)
            if features is None:
                return

            # Check if feature already exists (avoid UNIQUE constraint error)
            existing_feature = Feature.query.filter_by(timestamp=window_start).first()
            if existing_feature:
                self.app.logger.info(f"Feature for {window_start} already exists, skipping")
                return

            # Save features
            feature_obj = Feature(
                timestamp=window_start,
                error_count=features['error_count'],
                warn_count=features['warn_count'],
                info_count=features['info_count'],
                total_logs=features['total_logs'],
                error_rate=features['error_rate'],
                cpu_avg=features['cpu_avg'],
                mem_avg=features['mem_avg'],
                disk_io_avg=features.get('disk_io_avg'),
                network_in=features.get('network_in'),
                network_out=features.get('network_out')
            )
            db.session.add(feature_obj)
            db.session.commit()

            # Run detection if detectors ready
            if self.detectors_ready:
                self._run_detection(window_start, features)

            # Update worker status
            worker_status['processed_windows'] += 1
            worker_status['last_processing_time'] = datetime.utcnow().isoformat()

        except Exception as e:
            self.app.logger.error(f"Error processing window {window_start}: {e}")
            db.session.rollback()

    def _extract_features(self, start_time, end_time):
        """Extract features from logs and metrics in time window"""
        try:
            # Get logs in window
            logs = LogEntry.query.filter(
                LogEntry.timestamp >= start_time,
                LogEntry.timestamp < end_time
            ).all()

            # Get metrics in window
            metrics = MetricEntry.query.filter(
                MetricEntry.timestamp >= start_time,
                MetricEntry.timestamp < end_time
            ).all()

            # Count logs by level
            error_count = sum(1 for log in logs if log.level == 'ERROR')
            warn_count = sum(1 for log in logs if log.level == 'WARN' or log.level == 'WARNING')
            info_count = sum(1 for log in logs if log.level == 'INFO')
            total_logs = len(logs)

            error_rate = error_count / total_logs if total_logs > 0 else 0.0

            # Average metrics
            cpu_avg = np.mean([m.cpu for m in metrics if m.cpu is not None]) if metrics else 0.0
            mem_avg = np.mean([m.memory for m in metrics if m.memory is not None]) if metrics else 0.0
            disk_io_avg = np.mean([m.disk_io for m in metrics if m.disk_io is not None]) if metrics else 0.0
            network_in = np.sum([m.network_in for m in metrics if m.network_in is not None]) if metrics else 0.0
            network_out = np.sum([m.network_out for m in metrics if m.network_out is not None]) if metrics else 0.0

            return {
                'error_count': error_count,
                'warn_count': warn_count,
                'info_count': info_count,
                'total_logs': total_logs,
                'error_rate': float(error_rate),
                'cpu_avg': float(cpu_avg) if not np.isnan(cpu_avg) else 0.0,
                'mem_avg': float(mem_avg) if not np.isnan(mem_avg) else 0.0,
                'disk_io_avg': float(disk_io_avg) if not np.isnan(disk_io_avg) else 0.0,
                'network_in': float(network_in),
                'network_out': float(network_out)
            }

        except Exception as e:
            self.app.logger.error(f"Error extracting features: {e}")
            return None

    def _run_detection(self, window_start, features):
        """Run anomaly detection on features using all 4 detectors"""
        try:
            # Create DataFrame for detectors
            df = pd.DataFrame([features])
            df['timestamp'] = window_start

            # Initialize results
            rule_anomaly = 0
            rule_score = 0.0
            if_anomaly = 0
            if_score = 0.0
            var_anomaly = 0
            var_score = 0.0
            deeplog_anomaly = 0
            deeplog_score = 0.0

            # 1. Rule-based detection
            if self.rule_detector:
                try:
                    result = self.rule_detector.detect(df)
                    rule_anomaly = int(result['rule_anomaly'].iloc[0])
                    rule_score = float(result['rule_score'].iloc[0])
                except Exception as e:
                    self.app.logger.warning(f"Rule detection failed: {e}")

            # 2. Isolation Forest detection
            if self.if_detector and self.if_detector.model is not None:
                try:
                    # Use ALL 10 features (same as training)
                    feature_cols = ['error_count', 'warn_count', 'info_count', 'total_logs',
                                    'error_rate', 'cpu_avg', 'mem_avg', 'disk_io_avg',
                                    'network_in', 'network_out']
                    X = df[feature_cols].fillna(0)

                    # Scale features if scaler exists
                    if self.if_detector.scaler is not None:
                        X_scaled = self.if_detector.scaler.transform(X)
                    else:
                        X_scaled = X

                    predictions = self.if_detector.model.predict(X_scaled)
                    scores = self.if_detector.model.score_samples(X_scaled)

                    if_anomaly = 1 if predictions[0] == -1 else 0
                    # Normalize score to 0-1 range
                    if_score = float(min(abs(scores[0]) / 0.5, 1.0))
                except Exception as e:
                    self.app.logger.warning(f"IF detection failed: {e}")

            # 3. VAR detection
            if self.var_detector:
                try:
                    # VAR needs historical data, so get recent features
                    window_end = window_start + timedelta(minutes=self.window_minutes)
                    recent_features = Feature.query.filter(
                        Feature.timestamp <= window_start
                    ).order_by(Feature.timestamp.desc()).limit(50).all()

                    if len(recent_features) >= 10:
                        # Create DataFrame from recent features
                        hist_df = pd.DataFrame([{
                            'error_count': f.error_count,
                            'warn_count': f.warn_count,
                            'error_rate': f.error_rate,
                            'cpu_avg': f.cpu_avg,
                            'mem_avg': f.mem_avg,
                            'total_logs': f.total_logs
                        } for f in reversed(recent_features)])

                        # Add current window
                        hist_df = pd.concat([hist_df, df], ignore_index=True)

                        # Detect
                        result = self.var_detector.detect(hist_df, train=False)
                        var_anomaly = int(result['var_anomaly'].iloc[-1])
                        var_score = float(result['var_score'].iloc[-1])
                except Exception as e:
                    self.app.logger.warning(f"VAR detection failed: {e}")

            # 4. DeepLog detection
            if self.deeplog_detector:
                try:
                    # DeepLog needs log sequences, get recent logs
                    window_end = window_start + timedelta(minutes=self.window_minutes)
                    recent_logs = LogEntry.query.filter(
                        LogEntry.timestamp <= window_end
                    ).order_by(LogEntry.timestamp.desc()).limit(100).all()

                    if len(recent_logs) >= 20:
                        logs_df = pd.DataFrame([{
                            'timestamp': log.timestamp,
                            'message': log.message,
                            'level': log.level
                        } for log in reversed(recent_logs)])

                        # Detect (use features as fallback)
                        result = self.deeplog_detector.detect(df, logs_df, train=False)
                        deeplog_anomaly = int(result['deeplog_anomaly'].iloc[0])
                        deeplog_score = float(result['deeplog_score'].iloc[0])
                except Exception as e:
                    self.app.logger.warning(f"DeepLog detection failed: {e}")

            # Fusion: Weighted voting
            # Rule-based: 20%, IF: 30%, VAR: 25%, DeepLog: 25%
            votes = rule_anomaly + if_anomaly + var_anomaly + deeplog_anomaly
            final_score = (
                rule_score * 0.20 +
                if_score * 0.30 +
                var_score * 0.25 +
                deeplog_score * 0.25
            )

            # Anomaly nếu có >= 2 detectors đồng ý hoặc score cao
            final_anomaly = 1 if (votes >= 2 or final_score >= 0.6) else 0

            # Determine severity
            if final_score >= 0.7:
                severity = 'High'
            elif final_score >= 0.4:
                severity = 'Medium'
            else:
                severity = 'Low'

            # Build detector agreement string
            detectors = []
            if rule_anomaly:
                detectors.append('rule')
            if if_anomaly:
                detectors.append('if')
            if var_anomaly:
                detectors.append('var')
            if deeplog_anomaly:
                detectors.append('deeplog')

            # Save detection result
            detection = DetectionResult(
                timestamp=window_start,
                rule_anomaly=rule_anomaly,
                rule_score=rule_score,
                if_anomaly=if_anomaly,
                if_score=if_score,
                var_anomaly=var_anomaly,
                var_score=var_score,
                deeplog_anomaly=deeplog_anomaly,
                deeplog_score=deeplog_score,
                final_anomaly=final_anomaly,
                final_score=final_score,
                severity=severity if final_anomaly else 'Normal',
                votes=votes,
                detector_agreement=','.join(detectors)
            )
            db.session.add(detection)
            db.session.commit()

            # Generate alert if anomaly detected
            if final_anomaly:
                self._generate_alert(window_start, features, final_score, severity, votes, detectors)

        except Exception as e:
            self.app.logger.error(f"Error in detection: {e}")
            db.session.rollback()

    def _generate_alert(self, timestamp, features, score, severity, votes, detectors):
        """Generate and emit alert"""
        try:
            # Create alert message
            parts = []
            if features['error_count'] > 0:
                parts.append(f"Errors: {features['error_count']}")
            if features['cpu_avg'] > 80:
                parts.append(f"High CPU: {features['cpu_avg']:.1f}%")
            if features['mem_avg'] > 85:
                parts.append(f"High Memory: {features['mem_avg']:.1f}%")

            message = " | ".join(parts) if parts else "Anomaly detected"

            # Save alert to database
            alert = Alert(
                timestamp=timestamp,
                severity=severity,
                final_score=score,
                votes=votes,
                detector_agreement=','.join(detectors),
                error_count=features['error_count'],
                cpu_avg=features['cpu_avg'],
                mem_avg=features['mem_avg'],
                message=message,
                is_resolved=0
            )
            db.session.add(alert)
            db.session.commit()

            # Update worker status
            worker_status['alerts_generated'] += 1

            # Send SSE event
            self._send_sse_alert(alert)

            self.app.logger.warning(f"[ALERT] {severity} - {message}")

        except Exception as e:
            self.app.logger.error(f"Error generating alert: {e}")
            db.session.rollback()

    def _send_sse_alert(self, alert):
        """Send alert via SSE to connected clients"""
        try:
            from app.api.stream import send_sse_event

            send_sse_event('alert', alert.to_dict())

        except Exception as e:
            self.app.logger.error(f"Error sending SSE event: {e}")
