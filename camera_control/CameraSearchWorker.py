class CameraSearchWorker:

    def __init__(self, camera_queue, timeout=0.1, update_interval=0.001):
        self.camera_queue = camera_queue
        self.running = False
        self.timeout = timeout
        self.update_interval = update_interval