"""
Server-Sent Events (SSE) endpoint for real-time updates
"""
from flask import Response, current_app, stream_with_context
from flask_login import login_required
from app.api import api_bp
import json
import time
import queue


# Global queue for SSE events
sse_queue = queue.Queue(maxsize=1000)


def send_sse_event(event_type, data):
    """
    Send SSE event to all connected clients

    Args:
        event_type: Type of event (alert, status, etc.)
        data: Event data (dict)
    """
    try:
        sse_queue.put({
            'event': event_type,
            'data': data
        }, block=False)
    except queue.Full:
        current_app.logger.warning("SSE queue is full, dropping event")


@api_bp.route('/stream/alerts')
@login_required
def stream_alerts():
    """
    Server-Sent Events stream for real-time alerts

    Clients can connect to this endpoint to receive real-time updates
    when new alerts are detected
    """

    def generate():
        """Generator function for SSE stream"""
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to alert stream'})}\n\n"

        # Keep connection alive and send events
        last_heartbeat = time.time()

        while True:
            try:
                # Try to get event from queue with timeout
                try:
                    event = sse_queue.get(timeout=1)

                    # Format SSE message
                    message = f"event: {event['event']}\n"
                    message += f"data: {json.dumps(event['data'])}\n\n"

                    yield message

                except queue.Empty:
                    # No event, check if need heartbeat
                    pass

                # Send heartbeat every 30 seconds to keep connection alive
                current_time = time.time()
                if current_time - last_heartbeat > 30:
                    yield f": heartbeat\n\n"
                    last_heartbeat = current_time

            except GeneratorExit:
                # Client disconnected
                break
            except Exception as e:
                current_app.logger.error(f"Error in SSE stream: {e}")
                break

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable buffering for nginx
            'Connection': 'keep-alive'
        }
    )


@api_bp.route('/stream/status')
@login_required
def stream_status():
    """
    Server-Sent Events stream for system status updates

    Sends periodic updates about system health
    """

    def generate():
        """Generator function for status stream"""
        yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to status stream'})}\n\n"

        while True:
            try:
                # Get current system status
                from app.workers import get_worker_status

                status = get_worker_status()

                message = f"event: status\n"
                message += f"data: {json.dumps(status)}\n\n"

                yield message

                # Wait 10 seconds before next update
                time.sleep(10)

            except GeneratorExit:
                break
            except Exception as e:
                current_app.logger.error(f"Error in status stream: {e}")
                break

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )
