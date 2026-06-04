"""
Background Workers for LogSentry AI

Workers process logs in real-time, extract features, run detection,
and generate alerts.
"""
import threading
import queue as queue_module
from datetime import datetime

# Global queue for log processing
log_queue = queue_module.Queue(maxsize=10000)

# Worker thread reference
worker_thread = None

# Worker status
worker_status = {
    'running': False,
    'processed_windows': 0,
    'alerts_generated': 0,
    'last_processing_time': None,
    'errors': 0
}


def start_worker(app):
    """
    Start background worker thread

    Args:
        app: Flask app instance
    """
    global worker_thread

    if worker_thread is not None and worker_thread.is_alive():
        app.logger.info("Worker thread already running")
        return

    from app.workers.processor import LogProcessor

    # Create and start worker
    processor = LogProcessor(app, log_queue)
    worker_thread = threading.Thread(
        target=processor.run,
        daemon=True,
        name='LogProcessor'
    )
    worker_thread.start()

    worker_status['running'] = True
    app.logger.info("[OK] Background worker started")


def get_worker_status():
    """Get current worker status"""
    return worker_status.copy()


def stop_worker():
    """Stop background worker (graceful shutdown)"""
    global worker_thread

    if worker_thread and worker_thread.is_alive():
        log_queue.put({'type': 'shutdown'})
        worker_thread.join(timeout=5)
        worker_status['running'] = False
