class FileWorker:

    def __init__(self, file_path, image_queue, parameter_queue, update_interval=0.10):
        self.file_path = file_path
        self.image_queue = image_queue
        self.parameter_queue = parameter_queue
        self.update_interval = update_interval

    def save(self, images, params):
        return
    
    def run(self):
        while True:
            # Check that both image_queue and parameter_queue have data
            # If no data sleep for an update_interval
            # If there is data, pop off images data and parameter and do a save
            images, param = self.image_queue.get(), self.parameter_queue.get()
        return