"""
Migration script để thêm DeepLog columns vào database

Chạy script này để cập nhật database schema:
    python migrate_add_deeplog.py
"""
from app import create_app, db
from sqlalchemy import text


def migrate_add_deeplog_columns():
    """Thêm deeplog_anomaly và deeplog_score columns vào detection_results table"""

    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("Migration: Add DeepLog columns to detection_results")
        print("=" * 60)

        try:
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('detection_results')]

            # Add deeplog_anomaly column
            if 'deeplog_anomaly' not in columns:
                print("\n[1/2] Adding column 'deeplog_anomaly'...")
                with db.engine.connect() as conn:
                    conn.execute(text(
                        "ALTER TABLE detection_results ADD COLUMN deeplog_anomaly INTEGER"
                    ))
                    conn.commit()
                print("  [OK] Added column 'deeplog_anomaly'")
            else:
                print("\n[1/2] Column 'deeplog_anomaly' already exists, skipping")

            # Add deeplog_score column
            if 'deeplog_score' not in columns:
                print("\n[2/2] Adding column 'deeplog_score'...")
                with db.engine.connect() as conn:
                    conn.execute(text(
                        "ALTER TABLE detection_results ADD COLUMN deeplog_score FLOAT"
                    ))
                    conn.commit()
                print("  [OK] Added column 'deeplog_score'")
            else:
                print("\n[2/2] Column 'deeplog_score' already exists, skipping")

            print("\n" + "=" * 60)
            print("[SUCCESS] Migration completed!")
            print("=" * 60)

            # Show current schema
            print("\nCurrent detection_results schema:")
            inspector = db.inspect(db.engine)
            columns = inspector.get_columns('detection_results')
            for col in columns:
                print(f"  - {col['name']}: {col['type']}")

        except Exception as e:
            print(f"\n[ERROR] Migration failed: {e}")
            print("\nIf you encounter errors, you can:")
            print("1. Delete old database and recreate: rm instance/logsentry.db")
            print("2. Or create migration suitable for your database engine")
            return False

    return True


if __name__ == '__main__':
    migrate_add_deeplog_columns()
