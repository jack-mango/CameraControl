from multiprocessing import Process
import logging
from pylablib.devices.Andor import AndorSDK2
try:
    from .CameraError import CameraError
except ImportError:
    from CameraError import CameraError
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# TODO: add some way to detect if the process has lost connection to main and kill it if so

class AcquisitionWorker(Process):

    def __init__(self,
                camera_idx,
                config_queue,
                info_queue,
                data_queue,
                acquisition_flag,
                teardown_flag,
                frames_per_shot,
                curr_config,
                timeout=0.01):
    
        super().__init__()
        self.camera_idx = camera_idx
        self.config_queue = config_queue
        self.info_queue = info_queue
        self.data_queue = data_queue
        self.teardown_flag = teardown_flag
        self.acquisition_flag = acquisition_flag
        self.timeout = timeout
        self.frames_per_shot = frames_per_shot
        self.curr_config = curr_config
        self.error = ''
    
    def run(self):
        success = self.connect_camera()
        if not success:
            status = {
                'temperature': None,
                'shutter_mode': None,
                'Error': f"Unable to connect to camera at idx {self.camera_idx}"
            }
            self.info_queue.put(status)
            return
        while not self.teardown_flag.is_set() and self.get_is_camera_connected():
            # Put the current camera state onto the info queue
            self.info_queue.put(self.get_camera_state())
            # Check for and apply updates to config settings
            if not self.config_queue.empty():
                new_config = self.get_latest_config()
                self.update_config(new_config)
            # If acquisition flag is set (True), pull images and put them on the data queue
            if self.get_acquisition_flag() and not self.acquisition_in_progress():
                self.camera.start_acquisition()
            elif not self.get_acquisition_flag() and self.acquisition_in_progress():
                self.camera.stop_acquisition()
            # Only pull images if we have a full n_frames_per_shot taken from the camera.
            # Then put them onto the data_queue. This corresponds to only taking images after an
            # experimental shot has completed.
            elif self.get_acquisition_flag() and self.acquisition_in_progress() and self.get_number_of_available_images() >= self.frames_per_shot.value:
                images = self.pull_images()
                self.data_queue.put(images)
            else:
                time.sleep(0.1)
        return
    
    def connect_camera(self):
        """Connect to a specific camera"""
        logger.info(f"Attempting to connect to camera at idx {self.camera_idx}")
        try:
            self.camera = AndorSDK2.AndorSDK2Camera(self.camera_idx, fan_mode='full')
            self.camera.set_frame_format("array")
            logger.info(f"Sucessfully connected to camera at idx {self.camera_idx}!")
            self.is_camera_connected = True
            for key, value in self.curr_config.items():
                success = self.handle_config_update(key, value)
                if not success:
                    self.error = f"Failed to update camera setting: {key} to value: {value}"
                    return
            return True
        except Exception as e:
            logger.info(f"Unable to connect to camera at idx {self.camera_idx}! Error: {e}")
            return False
    
    def disconnect_camera(self, idx):
        """Disconnect from current camera"""
        logger.info(f"Disconnecting from camera at idx {idx}")
        self.camera.close()
        self.is_camera_connected = False
        return True
    
    def get_is_camera_connected(self):
        """Check if camera is currently connected"""
        return self.is_camera_connected
    
    def get_acquisition_flag(self):
        return self.acquisition_flag.is_set()
    
    def acquisition_in_progress(self):
        return self.camera.acquisition_in_progress()
    
    def set_acquisition_flag(self):
        self.acquisition_flag.set()
    
    def get_latest_config(self):
        latest = None
        while not self.config_queue.empty():
            latest = self.config_queue.get_nowait()
        return latest
    
    def update_config(self, new_config):
        force_update = not self.curr_config
        self.error = ''
        for key, value in new_config.items():
            # TODO: Fix this, i dont like the logic lol
            if not force_update:
                update = self.curr_config.get(key, None) != value
            else:
                update = force_update
            if update:
                success = self.handle_config_update(key, value)
                if not success:
                    self.error = f"Failed to update camera setting: {key} to value: {value}"
                    return

    def handle_config_update(self, key, value):
        try:
            if key == 'Temperature (C)':
                self.set_temperature(value)
                self.curr_config['Temperature (C)'] = value
            elif key == 'Amplifier':
                self.set_oamp(value)
                self.curr_config['Amplifier'] = value
            elif key == 'Horizontal shift speed (MHz)':
                self.set_hsspeed(value)
                self.curr_config['Horizontal shift speed (MHz)'] = value
            elif key == 'Vertical shift speed (us)':
                self.set_vsspeed(value)
                self.curr_config['Vertical shift speed (us)'] = value
            elif key == 'Preamp gain':
                self.set_preamp(value)
                self.curr_config['Preamp gain'] = value
            elif key == 'Exposure time (ms)':
                self.set_exposure(value)
                self.curr_config['Exposure time (ms)'] = value
            elif key == 'Trigger mode':
                self.set_trigger_mode(value)
                self.curr_config['Trigger mode'] = value
            elif key == 'EM gain':
                self.set_emccd_gain(value)
                self.curr_config['EM gain'] = value
            elif key == 'High EM gain':
                self.set_high_em_gain(value)
                self.curr_config['High EM gain'] = value
            elif key == 'Shutter mode':
                self.set_shutter_mode(value)
                self.curr_config['Shutter mode'] = value
            elif key == 'Fan mode':
                self.set_fan_mode(value)
                self.curr_config['Fan mode'] = value
            elif key == 'Acquisition mode':
                self.set_acquisition_mode(value)
                self.curr_config['Acquisition mode'] = value
            elif key == 'X Origin' or key == 'Y Origin' or key == 'X Width' or key == 'Y Height' or key == 'X binning' or key == 'Y binning':
                # ROI settings - need all values to set ROI
                # Store individual values but only update camera when we have complete ROI
                self.curr_config[key] = value
                if all(k in self.curr_config for k in ['X Origin', 'Y Origin', 'X Width', 'Y Height', 'X binning', 'Y binning']):
                    roi = {
                        'x_left': self.curr_config['X Origin'],
                        'x_right': self.curr_config['X Origin'] + self.curr_config['X Width'],
                        'y_bottom': self.curr_config['Y Origin'],
                        'y_top': self.curr_config['Y Origin'] + self.curr_config['Y Height'],
                        'x_binning': self.curr_config['X binning'],
                        'y_binning': self.curr_config['Y binning']
                    }
                    self.set_roi(roi)
            return True
        except Exception as e:
            return False
    
    def get_camera_state(self): 
        temperature = self.camera.get_temperature()
        temperature_status = self.camera.get_temperature_status()
        shutter_mode = self.camera.get_shutter()
        state = {
            'temperature': temperature,
            'temperature_status': temperature_status,
            'shutter_mode': shutter_mode,
            'Error': self.error
        }
        return state
    
    def get_number_of_available_images(self):
        """
        Get the number of unread images currently available in the camera buffer.
        Returns the count of available images, or 0 if none available.
        """
        rng = self.camera.get_new_images_range()
        if rng is None:
            return 0
        
        first, last = rng
        unread = last - first
        return unread
    
    def pull_images(self):
        """
        Read the frames_per_shot oldest unread images from the camera buffer.
        Uses get_new_images_range() to determine the range of unread images
        and reads from that range, similar to test.py approach.
        """
        rng = self.camera.get_new_images_range()
        if rng is None:
            logger.warning("No unread images available.")
            return []

        first, last = rng
        total_unread = last - first + 1
        
        # Read the oldest frames_per_shot images
        read_range = (first, first + self.frames_per_shot.value)    
        logger.debug(f"Reading frames {read_range[0]}–{read_range[1]} "
                    f"(out of available {total_unread}, indices {first}–{last})")

        images = self.camera.read_multiple_images(rng=read_range)
        return images
    
    def set_temperature(self, temp):
        self.camera.set_temperature(temp)
        return
    
    def set_oamp(self, oamp):
        self.camera.set_amp_mode(oamp=oamp)
        return
    
    def set_hsspeed(self, speed):
        self.camera.set_amp_mode(hsspeed=speed)
        return
    
    def set_vsspeed(self, speed):
        self.camera.set_vsspeed(speed)
        return
    
    def set_preamp(self, preamp):
        self.camera.set_amp_mode(preamp=preamp)
        return
    
    def set_exposure(self, exposure):
        self.camera.set_exposure(exposure)
        return
    
    def set_trigger_mode(self, mode):
        self.camera.set_trigger_mode(mode)
        return
    
    def set_emccd_gain(self, gain):
        self.camera.set_EMCCD_gain(gain)
        return
    
    def set_high_em_gain(self, high):
        self.camera.set_EMCCD_gain(self.curr_config['EM gain'], advanced=high)
        return
    
    def set_shutter_mode(self, mode):
        self.camera.setup_shutter(mode)
        return  
    
    def set_fan_mode(self, mode):
        self.camera.set_fan_mode(mode)
        return
    
    def set_acquisition_mode(self, mode):
        self.camera.set_acquisition_mode(mode)
    
    def set_roi(self, roi):
        self.camera.set_roi(roi['x_left'],
                            roi['x_right'],
                            roi['y_bottom'],
                            roi['y_top'],
                            hbin=roi['x_binning'],
                            vbin=roi['y_binning'])
        return