import os
import h5py
import time
import logging
import numpy as np
from queue import Queue
from scipy.io import savemat
from PyQt5.QtCore import QObject, pyqtSignal


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

# TODO: If the year month day directories don't exist create them.

class FileWorker(QObject):
    """Worker object for saving image data to files"""
    
    # Signals
    save_complete_signal = pyqtSignal(str)  # Emits filename when save completes

    def __init__(self, data_path, file_format, shots_per_parameter=1, auto_shots_per_parameter=False, use_socket_data_path=False, **kwargs):
        """
        Initialize FileWorker
        
        Args:
            data_path: Directory path where files will be saved
            file_format: File format extension (.hdf5, .npz, .mat)
            shots_per_parameter: Number of shots to buffer before saving
            auto_shots_per_parameter: If True, auto-detect when to save based on parameter changes
            use_socket_data_path: If True, use filename from socket parameters instead of timestamp
            **kwargs: Additional acquisition config parameters (e.g., frames_per_shot, max_shots)
        """
        super().__init__()
        # Public attributes
        self.file_path = data_path
        self.file_extension = file_format
        self.shots_per_parameter = shots_per_parameter
        self.auto_shots_per_parameter = auto_shots_per_parameter
        self.use_socket_data_path = use_socket_data_path
        
        # Internal buffers using Queue (thread-safe)
        self.image_buffer = Queue()
        self.parameter_buffer = Queue() 
        self.last_parameter_value = None
        
        # Shot counter
        self._shot_count = 0


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
        # Determine filename
        if self.use_socket_data_path and 'filename' in params:
            # Use filename from socket parameters
            filename = params.pop('filename')
        else:
            # Create timestamp for filename
            t = time.localtime()
            date_dir = time.strftime("%Y\\%m\\%d\\", t)
            timestamp = time.strftime("%H%M_%S", t)
            filename = timestamp
            date_dir_full_path = os.path.join(self.file_path, date_dir)
            os.makedirs(date_dir_full_path, exist_ok=True)   
        
        # Route to appropriate save method based on format
        if self.file_extension == '.hdf5' or self.file_extension == '.h5':
            return self._save_hdf5(images, params, filename)
        elif self.file_extension == '.npz':
            return self._save_npz(images, params, filename)
        elif self.file_extension == '.mat':
            return self._save_mat(images, params, filename)
        else:
            raise ValueError(f"Unsupported file format: {self.file_extension}")

    
    def on_new_data(self, images, parameters):
        """
        Slot to receive new data from Controller's new_data_signal.
        Simply buffers the data - Controller will signal when to save.
        
        Args:
            images: numpy array of image data
            parameters: dict of parameters
        """
        # Just buffer the data
        self.image_buffer.put(images)
        self.parameter_buffer.put(parameters)
        logger.debug(f"Buffered data. Current buffer size: {self.image_buffer.qsize()}")
    
    def save_buffered_data(self, n_shots):
        """
        Slot to trigger saving of buffered data.
        Called when Controller emits save_trigger_signal with number of shots to save.
        
        Args:
            n_shots: Number of shots to pull from buffer and save
        """
        if self.image_buffer.empty():
            logger.warning("No data in buffer to save")
            return
        
        try:
            # Pull n_shots items from the buffers
            images_list = []
            params_list = []
            
            # Determine how many items to actually pull
            available_shots = self.image_buffer.qsize()
            shots_to_save = min(n_shots, available_shots)
            
            if shots_to_save == 0:
                logger.warning("No images to save")
                return
            
            logger.info(f"Saving {shots_to_save} shots from buffer (requested: {n_shots}, available: {available_shots})")
            
            # Pull the specified number of shots
            for _ in range(shots_to_save):
                images_list.append(self.image_buffer.get())
                params_list.append(self.parameter_buffer.get())
            
            # Use the last parameter set (most recent)
            params = params_list[-1] if params_list else {}
            params['array_axes'] = ('shots_per_parameter', 'frames_per_shot', 'y_pixels', 'x_pixels')
            params['num_shots'] = len(images_list)
            
            # Stack all images into single array
            stacked_images = np.stack(images_list, axis=0)
            
            # Save to file
            fname = self._save(stacked_images, params)
            self.save_complete_signal.emit(fname)
            logger.info(f"Saved {len(images_list)} shots to {fname}")
            
        except Exception as e:
            error_msg = f"Error saving buffered data: {str(e)}"
            logger.error(error_msg)
    
    def stop(self):
        """Stop the FileWorker gracefully"""
        logger.info("Stopping FileWorker...")
        
        # Save any remaining buffered data before stopping
        buffer_size = self.image_buffer.qsize()
        if buffer_size > 0:
            logger.info(f"Saving remaining {buffer_size} shots before stopping")
            self.save_buffered_data(buffer_size)
        
        logger.info("FileWorker stopped")
    
    def set_shots_per_parameter(self, shots_per_parameter):
        """Update the number of shots to buffer before saving"""
        self.shots_per_parameter = shots_per_parameter
        logger.info(f"Shots per parameter updated to: {shots_per_parameter}")
    
    def set_auto_mode(self, auto_mode):
        """Enable or disable auto mode"""
        self.auto_shots_per_parameter = auto_mode
        logger.info(f"Auto shots per parameter mode: {auto_mode}")
    
    def set_file_extension(self, file_extension):
        """Change the save format
        
        Args:
            file_extension: New file format (.hdf5, .npz, .mat)
        """
        valid_formats = ['.hdf5', '.npz', '.mat']
        if file_extension not in valid_formats:
            raise ValueError(f"Invalid format: {file_extension}. Valid formats: {valid_formats}")
        
        self.file_extension = file_extension
        logger.info(f"Save format changed to: {file_extension}")
    

    def _save_hdf5(self, images, params, filename):
        """Save images and params to HDF5 file"""
        fname = os.path.join(self.file_path, f'{filename}.h5')
        
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
    
    def _save_npz(self, images, params, filename):
        """Save images and params to NumPy .npz file"""
        fname = os.path.join(self.file_path, f'{filename}.npz')
        
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
    
    def _save_mat(self, images, params, filename):
        """Save images and params to MATLAB .mat file"""
        
        fname = os.path.join(self.file_path, f'{filename}.mat')
        
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
