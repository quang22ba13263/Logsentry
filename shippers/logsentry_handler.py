"""
LogSentry AI - Python Logging Handler
Tích hợp trực tiếp vào Python application logging

Cài đặt:
    pip install requests

Sử dụng:
    import logging
    from logsentry_handler import LogSentryHandler

    # Thêm handler vào logger
    handler = LogSentryHandler(
        api_url='http://logsentry-server:5000',
        api_key='your-api-key',
        service='my-app'
    )
    logging.getLogger().addHandler(handler)

    # Logging như bình thường
    logging.error('Something went wrong!')
"""
import logging
import requests
import threading
import queue
import time
from datetime import datetime
import socket
import json


class LogSentryHandler(logging.Handler):
    """
    Logging handler gửi logs tới LogSentry AI

    Sử dụng background thread và queue để không block application
    """

    def __init__(self, api_url, api_key, service, host=None,
                 batch_size=100, batch_interval=5, level=logging.NOTSET):
        """
        Args:
            api_url: URL của LogSentry API
            api_key: API key
            service: Tên service
            host: Hostname (default: auto-detect)
            batch_size: Số logs trong một batch
            batch_interval: Khoảng thời gian gửi batch (giây)
            level: Log level tối thiểu
        """
        super().__init__(level)
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.service = service
        self.host = host or socket.gethostname()

        self.batch_size = batch_size
        self.batch_interval = batch_interval

        # Queue for async processing
        self.queue = queue.Queue(maxsize=10000)
        self.batch = []
        self.last_flush = time.time()

        # Background thread
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def emit(self, record):
        """
        Gọi khi có log mới
        """
        try:
            # Convert LogRecord to dict
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'message': self.format(record),
                'service': self.service,
                'host': self.host,
                'logger': record.name,
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }

            # Add exception info if present
            if record.exc_info:
                log_entry['exception'] = self.formatException(record.exc_info)

            # Put in queue (non-blocking)
            try:
                self.queue.put_nowait(log_entry)
            except queue.Full:
                # Queue full, drop log
                pass

        except Exception:
            self.handleError(record)

    def _worker(self):
        """Background worker thread"""
        while self.running:
            try:
                # Get log from queue with timeout
                try:
                    log_entry = self.queue.get(timeout=1)
                    self.batch.append(log_entry)
                except queue.Empty:
                    pass

                # Flush batch if needed
                if (len(self.batch) >= self.batch_size or
                    time.time() - self.last_flush >= self.batch_interval):
                    self._flush_batch()

            except Exception as e:
                # Log to stderr to avoid recursion
                import sys
                print(f"LogSentryHandler error: {e}", file=sys.stderr)

    def _flush_batch(self):
        """Gửi batch lên server"""
        if not self.batch:
            return

        try:
            response = requests.post(
                f"{self.api_url}/api/logs",
                json={'logs': self.batch},
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': self.api_key
                },
                timeout=10
            )

            if response.status_code == 201:
                self.batch = []
                self.last_flush = time.time()

        except Exception:
            # Silently fail to avoid log loops
            pass

    def close(self):
        """Cleanup khi đóng handler"""
        self.running = False
        self.thread.join(timeout=5)
        self._flush_batch()
        super().close()


# Helper function để setup dễ dàng
def setup_logsentry(api_url, api_key, service, level=logging.INFO,
                    console=True, file=None):
    """
    Setup LogSentry handler với cấu hình đơn giản

    Args:
        api_url: LogSentry API URL
        api_key: API key
        service: Service name
        level: Log level (default: INFO)
        console: Có log ra console không (default: True)
        file: File path để log ra file (optional)

    Returns:
        Logger instance

    Example:
        logger = setup_logsentry(
            api_url='http://localhost:5000',
            api_key='my-key',
            service='my-app',
            level=logging.INFO,
            console=True,
            file='/var/log/myapp.log'
        )

        logger.info('Application started')
        logger.error('Something went wrong!')
    """
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers = []

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # LogSentry handler
    logsentry_handler = LogSentryHandler(
        api_url=api_url,
        api_key=api_key,
        service=service,
        level=level
    )
    logsentry_handler.setFormatter(formatter)
    logger.addHandler(logsentry_handler)

    # Console handler
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler
    if file:
        file_handler = logging.FileHandler(file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Example application
def example_app():
    """Example application sử dụng LogSentry handler"""

    # Setup logging
    logger = setup_logsentry(
        api_url='http://localhost:5000',
        api_key='logsentry-api-key-change-in-production',
        service='example-app',
        level=logging.INFO,
        console=True
    )

    logger.info("Application started")
    logger.info("Processing request...")

    # Simulate some work
    for i in range(10):
        if i % 3 == 0:
            logger.warning(f"Warning: iteration {i}")
        elif i % 7 == 0:
            logger.error(f"Error: iteration {i}")
        else:
            logger.info(f"Processing item {i}")
        time.sleep(1)

    # Simulate exception
    try:
        result = 1 / 0
    except Exception as e:
        logger.exception("An error occurred")

    logger.info("Application finished")

    # Cleanup
    logging.shutdown()


if __name__ == '__main__':
    print("LogSentry Handler - Example Application")
    print("=" * 60)
    print("\nMake sure LogSentry server is running at http://localhost:5000")
    print("\nStarting example app...\n")

    example_app()

    print("\nExample completed!")
    print("Check LogSentry dashboard for logs")
