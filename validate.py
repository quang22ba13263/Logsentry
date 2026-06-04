"""
Script Validation - Đánh giá mô hình LogSentry AI chạy đúng

Script này kiểm tra:
1. Technical validation: Files, data format
2. Logic validation: Detectors hoạt động đúng
3. Performance validation: Metrics, ground truth
4. Sanity checks: Edge cases, consistency
"""
import pandas as pd
import numpy as np
import os
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
import json


class LogSentryValidator:
    """Validator cho hệ thống LogSentry AI"""

    def __init__(self):
        self.results = {
            'technical': {},
            'logic': {},
            'performance': {},
            'sanity': {},
            'passed': True,
            'errors': [],
            'warnings': []
        }

    def _log_error(self, message):
        """Log error"""
        self.results['errors'].append(message)
        self.results['passed'] = False
        print(f"[X] ERROR: {message}")

    def _log_warning(self, message):
        """Log warning"""
        self.results['warnings'].append(message)
        print(f"[!] WARNING: {message}")

    def _log_success(self, message):
        """Log success"""
        print(f"[OK] {message}")

    def _log_info(self, message):
        """Log info"""
        print(f"[i] {message}")

    # ========== TECHNICAL VALIDATION ==========

    def validate_files(self):
        """Kiểm tra các files cần thiết tồn tại"""
        print("\n" + "=" * 70)
        print("1. TECHNICAL VALIDATION - Files & Data Format")
        print("=" * 70)

        required_files = {
            'raw_logs': 'data/raw/application.log',
            'raw_metrics': 'data/raw/system_metrics.jsonl',
            'features': 'data/processed/features.csv',
            'final_results': 'data/processed/final_results.csv',
            'alerts': 'data/processed/alerts.csv',
        }

        for name, path in required_files.items():
            if os.path.exists(path):
                size = os.path.getsize(path) / 1024  # KB
                self._log_success(f"{name}: {path} ({size:.1f} KB)")
                self.results['technical'][f'{name}_exists'] = True
            else:
                self._log_error(f"File không tồn tại: {path}")
                self.results['technical'][f'{name}_exists'] = False

    def validate_data_format(self):
        """Kiểm tra format của data"""
        print("\n" + "-" * 70)
        print("Checking data format...")
        print("-" * 70)

        # Features.csv
        try:
            df_features = pd.read_csv('data/processed/features.csv')
            required_cols = ['timestamp', 'error_count', 'warn_count', 'info_count',
                           'cpu_avg', 'mem_avg', 'is_anomaly']

            missing_cols = [col for col in required_cols if col not in df_features.columns]
            if missing_cols:
                self._log_error(f"Features.csv thiếu columns: {missing_cols}")
            else:
                self._log_success(f"Features.csv có đủ {len(df_features.columns)} columns")

            self.results['technical']['features_rows'] = len(df_features)
            self._log_info(f"  Số windows: {len(df_features)}")

        except Exception as e:
            self._log_error(f"Không đọc được features.csv: {e}")

        # Final results
        try:
            df_results = pd.read_csv('data/processed/final_results.csv')
            required_cols = ['rule_anomaly', 'var_anomaly', 'if_anomaly', 'ae_anomaly',
                           'final_anomaly', 'severity', 'votes']

            missing_cols = [col for col in required_cols if col not in df_results.columns]
            if missing_cols:
                self._log_error(f"Final results thiếu columns: {missing_cols}")
            else:
                self._log_success(f"Final results có đủ {len(df_results.columns)} columns")

            self.results['technical']['results_rows'] = len(df_results)

        except Exception as e:
            self._log_error(f"Không đọc được final_results.csv: {e}")

    # ========== LOGIC VALIDATION ==========

    def validate_detectors(self):
        """Kiểm tra logic của các detectors"""
        print("\n" + "=" * 70)
        print("2. LOGIC VALIDATION - Detectors")
        print("=" * 70)

        df = pd.read_csv('data/processed/final_results.csv')

        # Test 1: Rule-based detector phải phát hiện high error count
        print("\nTest 1: Rule-based detector với high error count")
        high_error = df[df['error_count'] > 10]
        if len(high_error) > 0:
            detected = high_error['rule_anomaly'].sum()
            detection_rate = detected / len(high_error)
            if detection_rate > 0.5:  # Ít nhất 50% phải phát hiện
                self._log_success(f"Rule-based phát hiện {detection_rate:.1%} high-error windows")
                self.results['logic']['rule_high_error_detection'] = True
            else:
                self._log_warning(f"Rule-based chỉ phát hiện {detection_rate:.1%} high-error windows")
                self.results['logic']['rule_high_error_detection'] = False
        else:
            self._log_info("Không có windows với high error count")

        # Test 2: Voting logic
        print("\nTest 2: Voting logic consistency")
        for idx, row in df.sample(min(100, len(df))).iterrows():
            actual_votes = sum([
                row.get('rule_anomaly', 0),
                row.get('var_anomaly', 0),
                row.get('if_anomaly', 0),
                row.get('ae_anomaly', 0)
            ])
            reported_votes = row['votes']

            if actual_votes != reported_votes:
                self._log_error(f"Voting mismatch tại {idx}: actual={actual_votes}, reported={reported_votes}")
                self.results['logic']['voting_consistent'] = False
                break
        else:
            self._log_success("Voting logic nhất quán")
            self.results['logic']['voting_consistent'] = True

        # Test 3: Severity logic
        print("\nTest 3: Severity classification")
        severity_errors = 0
        for idx, row in df[df['final_anomaly'] == 1].iterrows():
            score = row['final_score']
            severity = row['severity']

            expected_severity = None
            if score >= 0.7:
                expected_severity = 'High'
            elif score >= 0.4:
                expected_severity = 'Medium'
            else:
                expected_severity = 'Low'

            if severity != expected_severity:
                severity_errors += 1

        if severity_errors == 0:
            self._log_success("Severity classification chính xác 100%")
            self.results['logic']['severity_correct'] = True
        else:
            self._log_warning(f"Có {severity_errors} lỗi severity classification")
            self.results['logic']['severity_correct'] = False

    def validate_fusion(self):
        """Kiểm tra fusion logic"""
        print("\nTest 4: Fusion logic")

        df = pd.read_csv('data/processed/final_results.csv')

        # Kiểm tra final_anomaly được set đúng khi có đủ votes
        min_votes = 2  # Theo config mặc định

        for idx, row in df.iterrows():
            votes = row['votes']
            final = row['final_anomaly']

            if votes >= min_votes and final != 1:
                self._log_error(f"Row {idx}: votes={votes} nhưng final_anomaly={final}")
                self.results['logic']['fusion_min_votes'] = False
                break
        else:
            self._log_success(f"Fusion logic đúng: min_votes={min_votes}")
            self.results['logic']['fusion_min_votes'] = True

    # ========== PERFORMANCE VALIDATION ==========

    def validate_performance(self):
        """Đánh giá performance với ground truth"""
        print("\n" + "=" * 70)
        print("3. PERFORMANCE VALIDATION - Metrics")
        print("=" * 70)

        df = pd.read_csv('data/processed/final_results.csv')

        if 'is_anomaly' not in df.columns:
            self._log_warning("Không có ground truth để đánh giá performance")
            return

        y_true = df['is_anomaly'].astype(int)
        y_pred = df['final_anomaly']

        # Calculate metrics
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average='binary', zero_division=0
        )

        print(f"\nOverall Performance:")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall:    {recall:.4f}")
        print(f"  F1-Score:  {f1:.4f}")

        self.results['performance']['precision'] = precision
        self.results['performance']['recall'] = recall
        self.results['performance']['f1'] = f1

        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred)
        tn, fp, fn, tp = cm.ravel()

        print(f"\nConfusion Matrix:")
        print(f"  True Negatives:  {tn:5d}")
        print(f"  False Positives: {fp:5d}")
        print(f"  False Negatives: {fn:5d}")
        print(f"  True Positives:  {tp:5d}")

        # Validate thresholds
        if f1 >= 0.6:
            self._log_success(f"F1-Score = {f1:.4f} (Good ≥ 0.6)")
        elif f1 >= 0.4:
            self._log_warning(f"F1-Score = {f1:.4f} (Acceptable ≥ 0.4)")
        else:
            self._log_error(f"F1-Score = {f1:.4f} quá thấp (< 0.4)")

        # Validate precision
        if precision >= 0.7:
            self._log_success(f"Precision = {precision:.4f} (Good ≥ 0.7)")
        elif precision >= 0.5:
            self._log_warning(f"Precision = {precision:.4f} (Acceptable ≥ 0.5)")
        else:
            self._log_error(f"Precision = {precision:.4f} quá thấp, nhiều false positives")

        # Validate recall
        if recall >= 0.7:
            self._log_success(f"Recall = {recall:.4f} (Good ≥ 0.7)")
        elif recall >= 0.5:
            self._log_warning(f"Recall = {recall:.4f} (Acceptable ≥ 0.5)")
        else:
            self._log_error(f"Recall = {recall:.4f} quá thấp, bỏ sót nhiều anomaly")

        # Compare detectors
        print("\n" + "-" * 70)
        print("Detector Comparison:")
        print("-" * 70)

        detectors = {
            'Rule-based': 'rule_anomaly',
            'VAR': 'var_anomaly',
            'Isolation Forest': 'if_anomaly',
            'Autoencoder': 'ae_anomaly',
            'Fusion': 'final_anomaly'
        }

        best_f1 = 0
        best_detector = None

        for name, col in detectors.items():
            if col not in df.columns:
                continue

            y_pred_det = df[col]
            p, r, f, _ = precision_recall_fscore_support(
                y_true, y_pred_det, average='binary', zero_division=0
            )

            print(f"{name:20s} | P={p:.3f} | R={r:.3f} | F1={f:.3f}")

            if f > best_f1:
                best_f1 = f
                best_detector = name

        print(f"\nBest detector: {best_detector} (F1={best_f1:.3f})")

        # Fusion phải tốt hơn hoặc bằng best individual detector
        if self.results['performance']['f1'] >= best_f1:
            self._log_success(f"Fusion (F1={self.results['performance']['f1']:.3f}) ≥ Best detector (F1={best_f1:.3f})")
            self.results['performance']['fusion_improves'] = True
        else:
            self._log_warning(f"Fusion (F1={self.results['performance']['f1']:.3f}) < Best detector (F1={best_f1:.3f})")
            self.results['performance']['fusion_improves'] = False

    # ========== SANITY CHECKS ==========

    def validate_sanity(self):
        """Sanity checks - kiểm tra các điều bất thường"""
        print("\n" + "=" * 70)
        print("4. SANITY CHECKS")
        print("=" * 70)

        df = pd.read_csv('data/processed/final_results.csv')

        # Check 1: Không có NaN trong critical columns
        print("\nCheck 1: Missing values")
        critical_cols = ['final_anomaly', 'final_score', 'votes', 'severity']
        nan_counts = df[critical_cols].isna().sum()

        if nan_counts.sum() > 0:
            self._log_error(f"Có NaN values trong critical columns:\n{nan_counts[nan_counts > 0]}")
            self.results['sanity']['no_nan'] = False
        else:
            self._log_success("Không có missing values trong critical columns")
            self.results['sanity']['no_nan'] = True

        # Check 2: Scores trong range [0, 1]
        print("\nCheck 2: Score ranges")
        score_cols = [col for col in df.columns if 'score' in col]
        invalid_scores = 0

        for col in score_cols:
            if col in df.columns:
                out_of_range = ((df[col] < 0) | (df[col] > 1)).sum()
                if out_of_range > 0:
                    self._log_error(f"{col} có {out_of_range} giá trị ngoài [0, 1]")
                    invalid_scores += 1

        if invalid_scores == 0:
            self._log_success("Tất cả scores trong range [0, 1]")
            self.results['sanity']['scores_in_range'] = True
        else:
            self.results['sanity']['scores_in_range'] = False

        # Check 3: Anomaly columns chỉ có 0 hoặc 1
        print("\nCheck 3: Anomaly binary values")
        anomaly_cols = [col for col in df.columns if 'anomaly' in col and 'type' not in col]
        invalid_binary = 0

        for col in anomaly_cols:
            if col in df.columns:
                unique_vals = df[col].dropna().unique()
                if not set(unique_vals).issubset({0, 1, 0.0, 1.0}):
                    self._log_error(f"{col} có giá trị không phải 0/1: {unique_vals}")
                    invalid_binary += 1

        if invalid_binary == 0:
            self._log_success("Tất cả anomaly columns là binary (0/1)")
            self.results['sanity']['binary_anomalies'] = True
        else:
            self.results['sanity']['binary_anomalies'] = False

        # Check 4: Severity values hợp lệ
        print("\nCheck 4: Severity values")
        valid_severities = {'Normal', 'Low', 'Medium', 'High'}
        invalid_severities = set(df['severity'].unique()) - valid_severities

        if invalid_severities:
            self._log_error(f"Có severity values không hợp lệ: {invalid_severities}")
            self.results['sanity']['valid_severities'] = False
        else:
            self._log_success("Tất cả severity values hợp lệ")
            self.results['sanity']['valid_severities'] = True

        # Check 5: Alerts.csv chỉ chứa anomalies
        print("\nCheck 5: Alerts file consistency")
        try:
            alerts = pd.read_csv('data/processed/alerts.csv')
            if len(alerts) == df['final_anomaly'].sum():
                self._log_success(f"Alerts.csv có đúng {len(alerts)} anomalies")
                self.results['sanity']['alerts_count'] = True
            else:
                self._log_error(f"Alerts.csv có {len(alerts)} rows nhưng final_results có {df['final_anomaly'].sum()} anomalies")
                self.results['sanity']['alerts_count'] = False
        except Exception as e:
            self._log_error(f"Không đọc được alerts.csv: {e}")
            self.results['sanity']['alerts_count'] = False

        # Check 6: Distribution hợp lý
        print("\nCheck 6: Anomaly distribution")
        anomaly_rate = df['final_anomaly'].mean()
        print(f"  Anomaly rate: {anomaly_rate:.2%}")

        if anomaly_rate < 0.01:
            self._log_warning(f"Anomaly rate quá thấp ({anomaly_rate:.2%}), có thể bỏ sót nhiều")
        elif anomaly_rate > 0.3:
            self._log_warning(f"Anomaly rate quá cao ({anomaly_rate:.2%}), có thể nhiều false positives")
        else:
            self._log_success(f"Anomaly rate hợp lý ({anomaly_rate:.2%})")

        self.results['sanity']['anomaly_rate'] = anomaly_rate

    # ========== SUMMARY ==========

    def print_summary(self):
        """In tổng kết"""
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)

        total_tests = 0
        passed_tests = 0

        for category in ['technical', 'logic', 'performance', 'sanity']:
            category_results = self.results[category]
            if not category_results:
                continue

            # Count boolean results
            bool_results = {k: v for k, v in category_results.items() if isinstance(v, bool)}
            if bool_results:
                total = len(bool_results)
                passed = sum(bool_results.values())

                total_tests += total
                passed_tests += passed

                print(f"\n{category.upper():20s}: {passed}/{total} passed")

        print(f"\n{'OVERALL':20s}: {passed_tests}/{total_tests} tests passed")

        # Performance metrics
        if self.results['performance']:
            print(f"\nPerformance Metrics:")
            for key in ['precision', 'recall', 'f1']:
                if key in self.results['performance']:
                    print(f"  {key.capitalize():12s}: {self.results['performance'][key]:.4f}")

        # Errors and warnings
        if self.results['errors']:
            print(f"\n[!] {len(self.results['errors'])} ERRORS found:")
            for err in self.results['errors'][:5]:  # Show first 5
                print(f"  - {err}")

        if self.results['warnings']:
            print(f"\n[!] {len(self.results['warnings'])} WARNINGS:")
            for warn in self.results['warnings'][:5]:
                print(f"  - {warn}")

        # Final verdict
        print("\n" + "=" * 70)
        if self.results['passed'] and passed_tests / total_tests >= 0.8:
            print("[OK] VALIDATION PASSED - He thong chay dung!")
            print("=" * 70)
        elif passed_tests / total_tests >= 0.6:
            print("[!] VALIDATION PARTIAL - He thong co mot so van de nho")
            print("=" * 70)
        else:
            print("[X] VALIDATION FAILED - He thong co van de nghiem trong")
            print("=" * 70)

    def save_report(self, output_file='validation_report.json'):
        """Lưu báo cáo validation"""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n[i] Bao cao validation da luu vao: {output_file}")

    def run_all(self):
        """Chạy tất cả validation tests"""
        print("\n")
        print("=" * 70)
        print(" " * 18 + "LOGSENTRY AI VALIDATION")
        print("=" * 70)

        self.validate_files()
        self.validate_data_format()
        self.validate_detectors()
        self.validate_fusion()
        self.validate_performance()
        self.validate_sanity()
        self.print_summary()
        self.save_report()


if __name__ == '__main__':
    validator = LogSentryValidator()
    validator.run_all()
