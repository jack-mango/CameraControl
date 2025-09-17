import os
import h5py
import time
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
else:
    logger = logging.getLogger(__name__)

class FileWorker:

    def __init__(self, file_path, image_queue, parameter_queue, update_interval=0.10):
        self.file_path = file_path
        self.image_queue = image_queue
        self.parameter_queue = parameter_queue
        self.update_interval = update_interval

    def save(self, images, params):
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
        while True:
            images, param = self.image_queue.get(), self.parameter_queue.get()
            fname = self.save(images, param)
            logger.info(f"Saved batch of images to {fname}")
        return