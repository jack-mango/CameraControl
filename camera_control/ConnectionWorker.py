import socket
import time
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
else:
    logger = logging.getLogger(__name__)

class ConnectionWorker:

    def __init__(self, address, port, buffer, parameter_queue, timeout=0.1, update_interval=0.001, line_size=1024):
        self.address = address
        self.port = port
        self.running = False
        self.buffer = buffer
        self.parameter_queue = parameter_queue
        self.socket = None

        self.timeout = timeout
        self.update_interval = update_interval
        self.line_size = line_size

    def run(self):
        self.start_connection()
        while self.running:
            time.sleep(self.update_interval)
            try:
                self.receive_data()
                self.queue_lines()
            except socket.timeout:
                continue
            except socket.error as e:
                logger.error(f"Socket error: {e}")
                break
        self.stop_connection()
        return
    
    def start_connection(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.address, self.port))
            self.socket.settimeout(0.1)
            self.running = True
            logger.info(f"Connected to {self.address}:{self.port}")
        except socket.error as e:
            logger.error(f"Socket creation error: {e}")
        return
    
    def stop_connection(self):
        self.socket.close()
        self.running = False
        logger.info(f"Connection to {self.address}:{self.port} closed")
        return
    
    def receive_data(self):
        data = self.socket.recv(self.line_size)
        decoded = self.decode_data(data)
        if data:
            self.buffer = self.buffer + decoded
            logger.debug(f"Received data: {decoded}")
        return
    
    def decode_data(self, line):
        return line.decode('ascii')
    
    def flush_buffer(self):
        self.buffer=''

    def queue_lines(self):
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            line = line.replace('\r', '')
            self.parameter_queue.put(line)
        self.flush_buffer()
        return