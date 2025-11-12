import os
import h5py
import time
import logging
import numpy as np
from queue import Queue
from scipy.io import savemat
from PyQt5.QtCore import QThread, pyqtSignal


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

# TODO: Sometimes the fileworker gets stuck saving the last shot or two left in the buffer if acquisition is halted early. Correct this!

class FileWorker(QThread):
    """QThread worker for saving image data to files"""
    
    # Signals
    save_complete_signal = pyqtSignal(str)  # Emits filename when save completes
    save_error_signal = pyqtSignal(str)     # Emits error message if save fails

    def __init__(self, file_path, file_extension, shots_per_parameter=1, auto_shots_per_parameter=False):
        """
        Initialize FileWorker
        
        Args:
            file_path: Directory path where files will be saved
            file_extension: File format extension (.hdf5, .npz, .mat)
            shots_per_parameter: Number of shots to buffer before saving
            auto_shots_per_parameter: If True, auto-detect when to save based on parameter changes
        """
        super().__init__()
        # Public attributes
        self.file_path = file_path
        self.save_format = file_extension
        self.shots_per_parameter = shots_per_parameter
        self.auto_shots_per_parameter = auto_shots_per_parameter
        
        # Internal buffers using Queue (thread-safe)
        self.image_buffer = Queue()
        self.parameter_buffer = Queue() 
        self.last_parameter_value = None
        
        # Shot counter
        self._shot_count = 0
        
        # Private attributes
        self._running = False


    def _save(self, images, params):
        """
        Save images and parameters to file in specified format
        
        Args:
            images: Image data array (numpy array)
            params: Dictionary of parameters to save as metadata
            
        Returns:
            str: Full path of saved file
            
        Raises:
            Exception: If file saving fails
        """
        # Create timestamp for filename
        t = time.localtime()
        date_dir = time.strftime("%Y\\%m\\%d\\", t)
        timestamp = time.strftime("%H%M_%S", t)
        
        # Ensure directory exists
        date_dir_full_path = os.path.join(self.file_path, date_dir)
        os.makedirs(date_dir_full_path, exist_ok=True)
        
        # Route to appropriate save method based on format
        if self.save_format == '.hdf5' or self.save_format == '.h5':
            return self._save_hdf5(images, params, timestamp)
        elif self.save_format == '.npz':
            return self._save_npz(images, params, timestamp)
        elif self.save_format == '.mat':
            return self._save_mat(images, params, timestamp)
        else:
            raise ValueError(f"Unsupported file format: {self.save_format}")

    
    def on_new_data(self, images, parameters):
        """
        Slot to receive new data from Controller's new_data_signal.
        Buffers data and saves when shots_per_parameter is reached.
        
        Args:
            images: numpy array of image data
            parameters: dict of parameters
        """
        # Add to buffers
        self.image_buffer.put(images)

        if self.auto_shots_per_parameter:
            curr_shot_number = parameters.pop('AAAreps')
            prev_shot_number = self._shot_count
            self._shot_count = curr_shot_number


        else:
            prev_shot_number = self._shot_count % self.shots_per_parameter
            self._shot_count += 1
            curr_shot_number = self._shot_count % self.shots_per_parameter
            

        if curr_shot_number < prev_shot_number:
            self.parameter_buffer.put(parameters)
            self.shots_per_parameter = prev_shot_number + 1
            self._save_buffered_data()
    
            

    def _save_buffered_data(self):
        """Save the buffered images and parameters to file"""
        if self.image_buffer.empty():
            logger.warning("No data in buffer to save")
            return
        
        try:
            # Pull only shots_per_parameter items from the queues
            images_list = []
            items_to_pull = min(self.shots_per_parameter, self.image_buffer.qsize())
            
            for _ in range(items_to_pull):
                images_list.append(self.image_buffer.get())
            params = self.parameter_buffer.get()
            params['array_axes'] = ('shots_per_parameter', 'frames_per_shot', 'y_pixels', 'x_pixels')
            
            # Stack all buffered images into single array
            stacked_images = np.stack(images_list, axis=0)
            
            # Save to file
            fname = self._save(stacked_images, params)
            self.save_complete_signal.emit(fname)
            logger.info(f"Saved {len(images_list)} shots to {fname}")
            
        except Exception as e:
            error_msg = f"Error saving buffered data: {str(e)}"
            self.save_error_signal.emit(error_msg)
            logger.error(error_msg)
    
    def run(self):
        """Main thread loop - keeps thread alive for signal processing"""
        self._running = True
        logger.info("FileWorker thread started (signal-based mode)")
        
        # This thread now just stays alive to process signals
        # The actual work is done in on_new_data() slot
        self.exec_()  # Start Qt event loop for signal processing
        
        logger.info("FileWorker thread stopped")
    
    def stop(self):
        """Stop the thread gracefully"""
        logger.info("Stopping FileWorker thread...")
        
        # Save any remaining buffered data before stopping
        if not self.image_buffer.empty():
            logger.info(f"Saving remaining {self.image_buffer.qsize()} shots before stopping")
            self._save_buffered_data()
        
        self._running = False
        self.quit()  # Stop Qt event loop
        self.wait()  # Wait for thread to finish
    
    def set_shots_per_parameter(self, shots_per_parameter):
        """Update the number of shots to buffer before saving"""
        self.shots_per_parameter = shots_per_parameter
        logger.info(f"Shots per parameter updated to: {shots_per_parameter}")
    
    def set_auto_mode(self, auto_mode):
        """Enable or disable auto mode"""
        self.auto_shots_per_parameter = auto_mode
        logger.info(f"Auto shots per parameter mode: {auto_mode}")
    
    def set_save_format(self, file_extension):
        """Change the save format
        
        Args:
            file_extension: New file format (.hdf5, .npz, .mat)
        """
        valid_formats = ['.hdf5', '.npz', '.mat']
        if file_extension not in valid_formats:
            raise ValueError(f"Invalid format: {file_extension}. Valid formats: {valid_formats}")
        
        self.save_format = file_extension
        logger.info(f"Save format changed to: {file_extension}")
    

    def _save_hdf5(self, images, params, timestamp):
        """Save images and params to HDF5 file"""
        fname = os.path.join(self.file_path, f'{timestamp}.h5')
        
        try:
            with h5py.File(fname, "w") as f:
                # Save images dataset with compression
                f.create_dataset("images", data=images, compression="gzip")

                # Create params group
                params_group = f.create_group("params")

                # Save params as attributes
                for key, value in params.items():
                    params_group.attrs[key] = value
            
            logger.info(f"Successfully saved HDF5 file: {fname}")
            return fname
        except Exception as e:
            logger.error(f"Failed to save HDF5 file {fname}: {e}")
            raise
    
    def _save_npz(self, images, params, timestamp):
        """Save images and params to NumPy .npz file"""
        fname = os.path.join(self.file_path, f'{timestamp}.npz')
        
        try:
            # Combine images and params into one dictionary
            save_dict = {'images': images}
            save_dict.update(params)
            
            # Save compressed
            np.savez_compressed(fname, **save_dict)
            
            logger.info(f"Successfully saved NPZ file: {fname}")
            return fname
        except Exception as e:
            logger.error(f"Failed to save NPZ file {fname}: {e}")
            raise
    
    def _save_mat(self, images, params, timestamp):
        """Save images and params to MATLAB .mat file"""
        
        fname = os.path.join(self.file_path, f'{timestamp}.mat')
        
        try:
            # Combine images and params into one dictionary
            save_dict = {'images': images}
            save_dict.update(params)
            
            # Save to .mat file
            savemat(fname, save_dict, do_compression=True)
            
            logger.info(f"Successfully saved MAT file: {fname}")
            return fname
        except Exception as e:
            logger.error(f"Failed to save MAT file {fname}: {e}")
            raise
