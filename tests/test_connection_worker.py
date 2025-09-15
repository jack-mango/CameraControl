# test_connection_worker.py
import pytest
import socket
import threading
import time
import queue

from camera_control import ConnectionWorker

HOST = "127.0.0.1"
PORT = 50010  # pick a test port


# -----------------------
# Helper TCP echo server
# -----------------------
def run_echo_server(host, port, messages, delay=0.01):
    """Start a simple TCP server that sends given messages then closes."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)
    conn, _ = server.accept()
    for msg in messages:
        time.sleep(delay)
        conn.sendall(msg.encode("ascii"))
    conn.close()
    server.close()


@pytest.fixture
def worker():
    return ConnectionWorker(
        address=HOST,
        port=PORT,
        buffer="",
        parameter_queue=queue.Queue(),
        timeout=0.1,
        update_interval=0.001,
        line_size=1024,
    )


# -----------------------
# Tests
# -----------------------

def test_start_and_stop_connection(worker):
    # Start dummy server that accepts a connection then closes
    server_thread = threading.Thread(
        target=run_echo_server, args=(HOST, PORT, []), daemon=True
    )
    server_thread.start()

    worker.start_connection()
    assert worker.running is True
    worker.stop_connection()
    assert worker.running is False
    server_thread.join()


def test_receive_and_queue_lines(worker):
    # Server sends two lines with newline separators
    server_thread = threading.Thread(
        target=run_echo_server, args=(HOST, PORT, ["line1\nline2\n"]), daemon=True
    )
    server_thread.start()

    worker.start_connection()
    worker.receive_data()
    worker.queue_lines()
    worker.stop_connection()
    server_thread.join()

    results = []
    while not worker.parameter_queue.empty():
        results.append(worker.parameter_queue.get())

    assert results == ["line1", "line2"]


def test_flush_buffer(worker):
    worker.buffer = "some leftover data"
    worker.flush_buffer()
    assert worker.buffer == ""


def test_decode_data(worker):
    raw = b"abc123"
    assert worker.decode_data(raw) == "abc123"

def test_run(worker):
    # Server sends two lines with newline separators then closes
    server_thread = threading.Thread(
        target=run_echo_server, args=(HOST, PORT, ["line1\nline2\n"], 1), daemon=True
    )
    server_thread.start()

    # Run the worker loop in its own thread
    t = threading.Thread(target=worker.run, daemon=True)
    t.start()

    # Wait for the server to finish sending
    server_thread.join(timeout=1)

    # Tell the worker to stop (otherwise it will loop forever)
    worker.running = False

    # Wait for worker to exit
    t.join(timeout=1)

    # Collect results from the queue
    results = []
    while not worker.parameter_queue.empty():
        results.append(worker.parameter_queue.get())

    assert results == ["line1", "line2"]

