import os
import h5py
import time
import logging
import threading

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
else:
    logger = logging.getLogger(__name__)

class FileWorker(threading.Thread):

    def __init__(self, file_path, image_queue, parameter_queue, update_interval=0.10):
        super().__init__(daemon=True)
        # Public attributes
        self.file_path = file_path
        self.update_interval = update_interval
        self.image_queue = image_queue
        self.parameter_queue = parameter_queue
        # Private attributes
        self._stop_event = threading.Event()


    def _save(self, images, params):
        t = time.localtime()
        timestamp = time.strftime("%H%M_%S", t)
        fname = os.path.join(self.file_path, f'{timestamp}.h5')

        with h5py.File(fname, "w") as f:
            # Save images dataset
            f.create_dataset("images", data=images, compression="gzip")

            # Create params group
            params_group = f.create_group("params")

            # Save params as attributes
            for key, value in params.items():
                params_group.attrs[key] = value

        return fname

    
    def run(self):
        while not self._stop_event.is_set():
            if not self.image_queue.empty() and not self.parameter_queue.empty():
                images, param = self.image_queue.get(), self.parameter_queue.get()
                fname = self._save(images, param)
                logger.info(f"Saved batch of images to {fname}")
            else:
                time.sleep(self.update_interval)
        return
    
    def stop(self):
        self._stop_event.set()