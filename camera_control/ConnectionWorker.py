import socket
import pickle
import logging
from PyQt5.QtCore import QThread, pyqtSignal


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)


class ConnectionWorker(QThread):
    """QThread worker for receiving UDP messages with pickled dictionaries"""
    
    def __init__(self, address, port, parameter_queue, timeout=1.0, update_interval=100):
        """
        Initialize ConnectionWorker
        
        Args:
            address: IP address to bind to (use '' for all interfaces)
            port: Port number to listen on
            parameter_queue: Queue to put received parameter dictionaries
            timeout: Socket timeout in seconds (default 1.0)
            update_interval: Time in milliseconds to sleep between recv attempts (default 1ms)
        """
        super().__init__()
        # Public attributes
        self.address = address
        self.port = port
        self.parameter_queue = parameter_queue
        self.timeout = timeout
        self.update_interval = update_interval  # In milliseconds for msleep
        
        # Private attributes
        self.socket = None

    def run(self):
        """Main thread loop - binds to port and continuously receives UDP messages"""
        logger.info("ConnectionWorker thread started")
        
        self.start_connection()
        
        while self.isRunning():
            self.msleep(self.update_interval)
            try:
                data, addr = self.socket.recvfrom(4096)
                if data:
                    try:
                        # Deserialize the pickled dictionary
                        parameters = pickle.loads(data)
                        logger.debug(f"Received parameters from {addr}: {parameters}")
                        
                        # Put in queue and emit signal
                        self.parameter_queue.put(parameters)
                    except pickle.UnpicklingError as e:
                        logger.error(f"Failed to unpickle data: {e}")
            except socket.timeout:
                # Timeout is expected, just continue
                continue
            except socket.error as e:
                logger.error(f"Socket error: {e}")
                break
            except Exception as e:
                logger.error(f"Error in ConnectionWorker run loop: {e}")
        
        self.stop_connection()
        logger.info("ConnectionWorker thread stopped")

    def decode_data(self, data):
        """Decode received data into a parameter dictionary"""
        try:
            parameters = pickle.loads(data)
            return parameters
        except pickle.UnpicklingError as e:
            logger.error(f"Failed to unpickle data: {e}")
            return None
    
    def start_connection(self):
        """Bind UDP socket to listen for incoming messages"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.address, self.port))
            self.socket.settimeout(self.timeout)
            logger.info(f"Listening on {self.address}:{self.port}")
            return True
        except socket.error as e:
            logger.error(f"Socket binding error: {e}")
            self.socket = None
            return False
    
    def stop_connection(self):
        """Close socket connection"""
        if self.socket:
            self.socket.close()
        logger.info(f"Socket on port {self.port} closed")
    