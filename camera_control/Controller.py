from .AcquisitionWorker import AcquisitionWorker
from .ConnectionWorker import ConnectionWorker
from .FileWorker import FileWorker
from .CameraError import CameraError
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import multiprocessing
from pylablib.devices.Andor import AndorSDK2
import logging
import numpy as np
import json


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# TODO: Add support for user defined config.

# TODO: Track rep_counter internally and emit a signal for rep_counter to signal the file should be saved.

class Controller(QThread):

    new_data_signal = pyqtSignal(np.ndarray, dict)
    shot_counter_signal = pyqtSignal(int)  # Signal to emit shot counter value
    rep_counter_signal = pyqtSignal(int)  # Signal to emit repetition counter value
    save_trigger_signal = pyqtSignal(int)  # Signal to trigger FileWorker to save buffered data
    temperature_signal = pyqtSignal(float, str)  # Signal to emit temperature value and status
    camera_connection_signal = pyqtSignal(bool)  # Signal to emit camera connection status
    socket_connection_signal = pyqtSignal(bool)  # Signal to emit socket connection status

    def __init__(self, config):
        super().__init__()

        self.config = config
        self.camera_status_queue = multiprocessing.Queue()
        self.config_queue = multiprocessing.Queue()
        self.acquisition_flag = multiprocessing.Event()
        self.acquisition_teardown_flag = multiprocessing.Event()
        self.frames_per_shot = multiprocessing.Value('i', config['acquisition_config'].get('frames_per_shot', 1))  # integer counter

        self.image_queue = multiprocessing.Queue()
        self.parameter_queue = multiprocessing.Queue()

        self.acquisition_worker = None
        self.file_worker = None
        self.connection_worker = None
        self.is_camera_connected = False
        self.is_socket_connected = False
        
        self._running = True  # Flag to control the run loop

        self.shot_counter = 0
        self.shot_number_in_rep = 0
        self.rep_counter = 0

        self._connected_camera_settings = {}
        self._found_cameras = []  # Store found cameras for persistence
        self._camera_idx = None  # Currently connected camera index
        self._all_camera_settings = {}  # Store settings for all found cameras {idx: settings_dict}

    def run(self):
        """Override QThread.run() - this executes in the background thread"""
        while self._running:
            self.msleep(100)  # sleep 100ms

            # Check camera status queue for temperature updates (non-blocking)
            if self.is_camera_connected:
                try:
                    status = self.camera_status_queue.get_nowait()
                    if status:
                        temperature = status['temperature']
                        temp_status = status['temperature_status']
                        self.temperature_signal.emit(temperature, temp_status)
                        logger.debug(f"Temperature: {temperature:.1f}°C ({temp_status})")
                except multiprocessing.queues.Empty:
                    pass  # No status available, continue
                except Exception as e:
                    logger.error(f"Error reading camera status: {e}")


            if self.acquisition_in_progress() and not self.image_queue.empty() and not self.parameter_queue.empty():
                try:
                    images = self.image_queue.get_nowait()
                    parameters = self.parameter_queue.get_nowait()

                    if self.config['acquisition_config']['auto_shots_per_parameter']:
                        self.shot_counter = parameters['AAAreps']
                    else:
                        self.shot_counter += 1
                    
                    logger.info(f"Shot count: {self.shot_counter}")

                    # Emit signal to FileWorker and GUI to buffer data
                    self.new_data_signal.emit(images, parameters)
                    
                    # Determine if we should trigger a save
                    auto_shots_per_parameter = self.config['acquisition_config']['auto_shots_per_parameter']
                    shots_per_parameter = self.config['acquisition_config']['shots_per_parameter']

                    auto_save = auto_shots_per_parameter and parameters['AAAreps'] == parameters['n_reps'] - 1
                    manual_save = self.shot_counter % shots_per_parameter == 0 and not auto_shots_per_parameter
                    
                    # Emit shot counter signal BEFORE resetting (so the final shot of each rep is counted)
                    self.shot_counter_signal.emit(self.shot_counter)
                    
                    if auto_save or manual_save:
                        self.save_trigger_signal.emit(self.shot_counter + 1)
                        self.shot_counter = 0
                        self.rep_counter += 1
                        self.rep_counter_signal.emit(self.rep_counter)
                        
                except multiprocessing.queues.Empty:
                    # Race condition: one queue became empty between check and get
                    logger.warning("Race condition: Queue became empty after check")
                except Exception as e:
                    logger.error(f"Error processing images: {e}")


    def stop(self):
        """Custom method for graceful shutdown"""
        logger.info("Stopping Controller...")
        self._running = False  # Stop the run loop
        self.acquisition_teardown_flag.set()

        # Stop FileWorker if running
        if self.file_worker:
            if self.file_worker.isRunning():
                logger.info("Stopping FileWorker")
                self.file_worker.stop()
                # Don't wait here - let parent thread handle waiting
        
        # Stop ConnectionWorker if running
        if self.connection_worker:
            if self.connection_worker.isRunning():
                logger.info("Stopping ConnectionWorker")
                self.connection_worker.quit()
                # Don't wait here - let parent thread handle waiting
        
        # Signal the Controller's event loop to exit
        # Note: quit() and wait() should be called from the parent thread (MainWindow.closeEvent)
        self.quit()
        logger.info("Controller stop initiated")

    def start_acquisition(self):
        """Start image acquisition"""
        logger.info("Starting acquisition...")
        self.clear_queues()
        
        if not self.is_camera_connected:
            raise CameraError("No camera connected!")
        
        # Check if auto shots per parameter is enabled without socket connection
        auto_shots_per_parameter = self.config.get('acquisition_config', {}).get('auto_shots_per_parameter', False)
        if auto_shots_per_parameter and not self.is_socket_connected:
            raise CameraError("Auto shots per parameter requires socket connection! Please connect socket or disable auto mode.")
        
        try:
            self.start_file_worker()
            self.connection_worker.start()
            
            self.acquisition_flag.set()
            self.shot_counter = 0
            self.rep_counter = 0
            logger.info("Acquisition started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start acquisition: {e}")
            raise

    def stop_acquisition(self):
        logger.info("Stopping acquisition...")
        self.acquisition_flag.clear()
        self.clear_queues()
        self.shot_counter = 0
        self.shot_number_in_rep = 0
        self.rep_counter = 0
        # Clear the acquisition
        self.stop_file_worker()
        return
    
    def clear_queues(self):
        """Clear image and parameter queues"""
        logger.info("Clearing image and parameter queues...")
        while not self.image_queue.empty():
            try:
                self.image_queue.get_nowait()
            except Exception:
                break
        while not self.parameter_queue.empty():
            try:
                self.parameter_queue.get_nowait()
            except Exception:
                break

    def acquisition_in_progress(self):
        return self.acquisition_flag.is_set()
    
    def get_camera_config(self):
        if self.is_camera_connected:
            return self.config['camera_config']['camera_specific_config']
        else:
            return {}

    def get_image_config(self):
        return self.config['image_config']
    
    def connect_camera(self, camera_info):
        """Connect to a specific camera"""
        idx = int(camera_info['idx'])
        logger.info(f"Connecting to camera at idx {idx}...")
        
        try:
            # Use cached settings if available, otherwise get them
            if idx in self._all_camera_settings:
                self._connected_camera_settings = self._all_camera_settings[idx]
                logger.debug(f"Using cached settings for camera at idx {idx}")
            else:
                logger.warning(f"No cached settings for camera at idx {idx}, fetching...")
                self._connected_camera_settings = self._get_available_settings(idx)
            
            intial_camera_config = self._camera_friendly_config(self.config['camera_config']['camera_specific_config'])
            intial_camera_config.update(self._camera_friendly_config(self.config['image_config']))       
            self.acquisition_worker = AcquisitionWorker(idx, 
                                                        self.config_queue,
                                                        self.camera_status_queue,
                                                        self.image_queue,
                                                        self.acquisition_flag,
                                                        self.acquisition_teardown_flag,
                                                        self.frames_per_shot,
                                                        intial_camera_config
                                                        )
            self.acquisition_worker.start()
            status = self.get_camera_status()
            
            if status and status['Error']:
                logger.error(f"Camera connection failed at idx {idx}: {status['Error']}")
                self.is_camera_connected = False
                self.camera_connection_signal.emit(False)
                return False
            
            # Connection successful
            logger.info(f"Successfully connected to camera at idx {idx}")
            self.is_camera_connected = True
            self.camera_connection_signal.emit(True)
            self._camera_idx = idx
            self._camera_info = camera_info
            
            # Update config if camera changed
            correct_config = (int(self.config['camera_config']['idx']) == self._camera_idx and 
                            self.config['camera_config']['serial_number'] == self._camera_info['serial_number']
                            and self.config['camera_config']['model'] == self._camera_info['model']
                            )

            if not correct_config:
                self.config['camera_config']['camera_specific_config'] = {}
                self.config['camera_config']['idx'] = self._camera_idx
                self.config['camera_config']['serial_number'] = self._camera_info['serial_number']
            
            return True
            
        except Exception as e:
            logger.error(f"Unexpected error connecting to camera at idx {idx}: {e}")
            self.is_camera_connected = False
            self.camera_connection_signal.emit(False)
            return False

    def disconnect_camera(self, idx):
        """Disconnect from current camera"""
        logger.info(f"Disconnecting camera at idx {idx}...")
        
        try:
            self.acquisition_teardown_flag.set()
            self.acquisition_worker.join(5)  # wait up to 5 seconds for graceful shutdown

            if self.acquisition_worker.is_alive():
                logger.warning("Acquisition worker did not shut down gracefully, terminating...")
                self.acquisition_worker.terminate()
                self.acquisition_worker.join()

            self.acquisition_worker = None
            self.is_camera_connected = False
            self.camera_connection_signal.emit(False)
            self._connected_camera_settings = {}
            self.acquisition_teardown_flag.clear()
            
            logger.info(f"Camera at idx {idx} disconnected")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting camera: {e}")
            return False
    
    def get_camera_status(self, timeout=10):
        """Get camera status from the status queue
    
        Args:
            timeout (float): Maximum time to wait for status in seconds
            
        Returns:
            dict or None: Camera status information if available, None if timeout
        """
        try:
            status = self.camera_status_queue.get(timeout=timeout)
            return status
        except multiprocessing.queues.Empty:
            logger.warning(f"Camera status timeout after {timeout}s")
            return None
        except Exception as e:
            logger.error(f"Error reading camera status: {e}")
            return None
    
    def get_socket_config(self):
        return self.config['socket_config']
    
    def set_socket_config(self, new_config):
        if self.acquisition_in_progress():
            raise RuntimeError("Cannot change socket config while acquisition is running")
        else:
            self.config['socket_config'] = new_config
        return True
    
    def connect_socket(self):
        """Connect to socket for parameter communication"""
        try:
            self.connection_worker = ConnectionWorker(
                self.config['socket_config']['ip_address'],
                self.config['socket_config']['port'],
                self.parameter_queue
            )
            success = self.connection_worker.start_connection()
            self.is_socket_connected = success  # Update the attribute
            self.socket_connection_signal.emit(success)
            logger.info(f"Socket connected: {self.config['socket_config']['ip_address']}:{self.config['socket_config']['port']}")
            return success
        except KeyError as e:
            logger.error(f"Socket config missing required field: {e}")
            self.is_socket_connected = False
            self.socket_connection_signal.emit(False)
            return False
        except Exception as e:
            logger.error(f"Failed to connect socket: {e}")
            self.is_socket_connected = False
            self.socket_connection_signal.emit(False)
            return False
    
    def disconnect_socket(self):
        """Disconnect from socket"""
        self.is_socket_connected = False
        self.socket_connection_signal.emit(False)
        logger.info("Socket disconnected")
        return True

    def set_camera_config(self, new_config):
        """Update camera configuration settings"""
        if self.acquisition_in_progress():
            raise CameraError("Cannot change camera config while acquisition is running")
        
        old_config = self.get_camera_config()
        if old_config:
            changed_settings = {k: new_config[k] for k in new_config.keys() if new_config[k] != old_config[k]}
        else:
            changed_settings = new_config

        if changed_settings:
            try:
                self._update_camera_config(changed_settings)
                self.config['camera_config']['camera_specific_config'] = new_config
                logger.info(f"Camera config updated: {', '.join(changed_settings.keys())}")
            except CameraError as e:
                logger.error(f"Camera configuration error: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error updating camera config: {e}")
                raise
    
    def set_image_config(self, new_config):
        """Update image configuration settings"""
        if self.acquisition_in_progress():
            raise CameraError("Cannot change image config while acquisition is running")
        
        old_config = self.get_image_config()
        if old_config:
            changed_settings = {k: new_config[k] for k in new_config.keys() if new_config[k] != old_config[k]}
        else:
            changed_settings = new_config
        
        if changed_settings:
            try:
                self._update_camera_config(changed_settings)
                self.config['image_config'] = new_config
                logger.info(f"Image config updated: {', '.join(changed_settings.keys())}")
            except CameraError as e:
                logger.error(f"Image configuration error: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error updating image config: {e}")
                raise
    
    def get_is_camera_connected(self):
        return self.is_camera_connected
    
    def get_file_format(self):
        """Get the current file save format"""
        return self.config['acquisition_config'].get('file_format')
    
    def set_file_format(self, file_extension):
        """Set the file save format
        
        Args:
            file_extension: File format (.hdf5, .npz, .mat, .tiff)
        """
        valid_formats = ['.hdf5', '.npz', '.mat']
        if file_extension not in valid_formats:
            raise ValueError(f"Invalid format: {file_extension}. Valid formats: {valid_formats}")
        
        self.config['acquisition_config']['file_format'] = file_extension
        
        logger.info(f"File format set to: {file_extension}")
        return True
    
    def get_acquisition_config(self):
        return self.config['acquisition_config']
    
    def set_acquisition_config(self, new_config):
        """Update acquisition configuration settings"""
        if self.acquisition_in_progress():
            raise RuntimeError("Cannot change acquisition config while acquisition is running")
        else:
            self.config['acquisition_config'] = new_config
            # Update the frames_per_shot in acquisition_worker
            self.frames_per_shot.value = new_config['frames_per_shot']
            # Update the controllers max frames
            self.max_shots = new_config['max_shots']

    def save_config(self):
        """Save current configuration to config.json file"""
        try:
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info("Configuration saved to config.json")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def start_file_worker(self):
        """Start the FileWorker for saving images"""
        try:
            logger.info("Starting FileWorker")
            
            self.file_worker = FileWorker(**self.config['acquisition_config'])
            
            # Connect signals - FileWorker is now a QObject, not QThread
            self.new_data_signal.connect(self.file_worker.on_new_data)
            self.save_trigger_signal.connect(self.file_worker.save_buffered_data)
            
            # Optionally connect FileWorker's signals for monitoring
            self.file_worker.save_complete_signal.connect(self._on_file_saved)
            
            logger.info("FileWorker started")
            return True
        except Exception as e:
            logger.error(f"Failed to start FileWorker: {e}")
            return False
    
    def _on_file_saved(self, filename):
        """Handle file save completion"""
        logger.info(f"File saved successfully: {filename}")
    
    def stop_file_worker(self):
        """Stop the FileWorker"""
        if self.file_worker is not None:
            try:
                logger.info("Stopping FileWorker")
                self.file_worker.stop()
                self.file_worker = None
                return True
            except Exception as e:
                logger.error(f"Error stopping FileWorker: {e}")
                return False
        return True  # Already stopped
    
    def set_file_save_format(self, file_extension):
        """Change the save format of FileWorker
        
        Args:
            file_extension: File format (.hdf5, .npz, .mat)
        """
        if self.file_worker is not None:
            try:
                self.file_worker.set_save_format(file_extension)
                return True
            except Exception as e:
                logger.error(f"Failed to change FileWorker format: {e}")
                return False
        else:
            logger.warning("Cannot change format: FileWorker not running")
            return False
    
    def search_cameras(self):
        """
        Searches for available Andor cameras and retrieves their information.

        Returns:
            list[dict]: List of dictionaries containing camera information.
                Each dictionary has the following keys:
                - 'idx' (str): The index number of the camera
                - 'model' (str): The head model name of the camera
                - 'serial_number' (str): The serial number of the camera

        Example returned list:
            [
                {
                    'idx': '0',
                    'model': 'iXon Ultra 888',
                    'serial_number': '12345'
                },
                ...
            ]
        """

        n_cameras = AndorSDK2.get_cameras_number()
        logger.info(f"Found {n_cameras} cameras")
        available_cameras = []
        self._all_camera_settings = {}  # Reset settings cache
        
        for idx in range(n_cameras):
            try:
                camera = AndorSDK2.AndorSDK2Camera(idx)
                controller_mode, head_model, serial_number = camera.get_device_info()
                logger.info(f"Found {head_model} model Andor camera at idx {idx} with serial number {serial_number}")
                
                # Get and store settings for this camera
                settings = self._get_settings_from_camera(camera)
                self._all_camera_settings[idx] = settings
                
                camera.close()
                camera_info = {
                    'idx': idx,
                    'model': head_model,
                    'serial_number': str(serial_number)
                }
                available_cameras.append(camera_info)
            except Exception as e:
                logger.error(f"Error accessing camera at idx {idx}: {e}")
        # Persist found cameras in the controller's private store and return a copy
        try:
            self._found_cameras = list(available_cameras)
        except Exception:
            # In case something unexpected happens, still return the list
            pass

        return list(self._found_cameras)
    
    def get_connected_camera_settings_list(self):
        return self._connected_camera_settings

    def get_found_cameras(self):
        """Return a copy of the last-found cameras list kept privately on Main.

        Returns:
            list[dict]: shallow copy of the found cameras; empty list if none found.
        """
        return list(self._found_cameras)
    
    def _get_settings_from_camera(self, camera):
        """Extract available settings from an already-instantiated camera object.
        
        Args:
            camera: AndorSDK2Camera instance
            
        Returns:
            dict: Dictionary of available camera settings
        """
        all_oamp_modes = camera.get_all_amp_modes()
        oamp_kind = list(dict.fromkeys([mode[3] for mode in all_oamp_modes]))
        hss_mhz = list(dict.fromkeys([f"{int(mode[5])}" for mode in all_oamp_modes]))
        preamp_gain = list(dict.fromkeys([f"{mode[-1]:.1f}" for mode in all_oamp_modes]))

        settings = {
            # TODO: Add support back in for internal triggering; add "Internal" : "int" below and proceed with implementation.
            "Trigger mode": {"External": "ext", "External exposure": "ext_exp"},
            "Exposure time (ms)": 1.0,
            "EM gain": 1,
            "High EM gain": True,
            "Amplifier": oamp_kind,
            "Vertical shift speed (us)": [f'{vss:.2f}' for vss in camera.get_all_vsspeeds()],
            "Horizontal shift speed (MHz)": hss_mhz,
            "Preamp gain": preamp_gain,
            "Shutter mode": {"Auto": "auto", "Open": "open", "Closed": "closed"},
            "Temperature (C)": 1.0
        }
        return settings
    
    def _get_available_settings(self, idx):
        """Get available settings by instantiating a camera.
        
        This method is kept as a fallback for when cached settings are not available.
        
        Args:
            idx: Camera index
            
        Returns:
            dict: Dictionary of available camera settings
        """
        camera = AndorSDK2.AndorSDK2Camera(idx)
        settings = self._get_settings_from_camera(camera)
        camera.close()
        return settings

    def _update_camera_config(self, changed_settings):
        changed_settings = self._camera_friendly_config(changed_settings)
        self.config_queue.put(changed_settings)
        status = self.get_camera_status(timeout=5)
        if status['Error']:
            raise CameraError(f"Error updating camera settings: {status['Error']}")
        
    def _camera_friendly_config(self, config):
        """ Camera settings are stored internally in a user friendly format. This method converts them to the format required by the camera API.
        """
        friendly_config = {}
        camera_friendly_map = self._connected_camera_settings
        if 'Trigger mode' in config:
            friendly_config['Trigger mode'] = camera_friendly_map['Trigger mode'][config['Trigger mode']]
        if 'Shutter mode' in config:
            friendly_config['Shutter mode'] = camera_friendly_map['Shutter mode'][config['Shutter mode']]
        if 'Amplifier' in config:
            friendly_config['Amplifier'] = camera_friendly_map['Amplifier'].index(config['Amplifier'])
        if 'Vertical shift speed (us)' in config:
            friendly_config['Vertical shift speed (us)'] = camera_friendly_map['Vertical shift speed (us)'].index(config['Vertical shift speed (us)'])
        if 'Horizontal shift speed (MHz)' in config:
            friendly_config['Horizontal shift speed (MHz)'] = camera_friendly_map['Horizontal shift speed (MHz)'].index(config['Horizontal shift speed (MHz)'])
        if 'Preamp gain' in config:
            friendly_config['Preamp gain'] = camera_friendly_map['Preamp gain'].index(config['Preamp gain'])
        if 'Temperature (C)' in config:
            friendly_config['Temperature (C)'] = float(config['Temperature (C)'])
        if 'Exposure time (ms)' in config:
            friendly_config['Exposure time (ms)'] = float(config['Exposure time (ms)'])
        if 'EM gain' in config:
            friendly_config['EM gain'] = int(config['EM gain'])
        if 'X binning' in config:
            friendly_config['X binning'] = int(config['X binning'])
        if 'Y binning' in config:
            friendly_config['Y binning'] = int(config['Y binning'])
        if 'X Origin' in config:
            friendly_config['X Origin'] = int(config['X Origin'])
        if 'Y Origin' in config:
            friendly_config['Y Origin'] = int(config['Y Origin'])
        if 'X Width' in config:
            friendly_config['X Width'] = int(config['X Width'])
        if 'Y Height' in config:
            friendly_config['Y Height'] = int(config['Y Height'])
        return friendly_config