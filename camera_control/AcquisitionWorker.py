class AcquisitionWorker:

    def __init__(self,
                camera_instance,
                config_queue,
                info_queue,
                data_queue,
                acquisition_flag,
                shot_counter,
                n_states,
                n_shots,
                update_interval=0.10):
        
        self.camera_instance = camera_instance
        self.config_queue = config_queue
        self.info_queue = info_queue
        self.data_queue = data_queue
        self.acquisition_flag = acquisition_flag
        self.shot_counter = shot_counter
        self.update_interval = update_interval
        self.n_states = n_states
        self.n_shots = n_shots
        self.curr_config = {}
    
    def run(self):
        while True:
            # Put the current camera state onto the info queue
            self.info_queue.put(self.get_camera_state())
            # Check for and apply updates to config settings
            if not self.config_queue.empty():
                new_config = self.get_latest_config()
                self.update_config(new_config)
            # If acquisition flag is set (True), pull images and put them on the data queue
            if self.get_acquisition_flag():
                images = self.pull_images()
                self.data_queue.put(images)
                self.increment_shot_counter()
                if self.get_shot_counter == self.n_shots:
                    self.set_acquisition_flag(False)
        return
    
    def increment_shot_counter(self):
        self.shot_counter.value += 1

    def get_shot_counter(self):
        return self.shot_counter.value
    
    def get_acquisition_flag(self):
        return self.acquisition_flag.value
    
    def set_acquisition_flag(self, flag):
        self.acquisition_flag.value = flag
    
    def get_latest_config(self):
        latest = None
        while not self.config_queue.empty():
            latest = self.config_queue.get_nowait()
        return latest
    
    def update_config(self, new_config):
        force_update = not self.curr_config
        for key, value in new_config.items():
            if not force_update:
                update = self.curr_config[key] != value
            else:
                update = force_update
            if update:
                self.handle_config_update(key, value)
        return
    
    def handle_config_update(self, key, value):
        if key == 'temperature':
            self.set_temperature(value)
            self.curr_config['temperature'] = value
        elif key == 'oamp':
            self.set_oamp(value)
            self.curr_config['oamp'] = value
        elif key == 'hsspeed':
            self.set_hsspeed(value)
            self.curr_config['hsspeed'] = value
        elif key == 'vsspeed':
            self.set_vsspeed(value)
            self.curr_config['vsspeed'] = value
        elif key == 'preamp':
            self.set_preamp(value)
            self.curr_config['preamp'] = value
        elif key == 'exposure':
            self.set_exposure(value)
            self.curr_config['exposure'] = value
        elif key == 'trigger_mode':
            self.set_trigger_mode(value)
            self.curr_config['trigger_mode'] = value
        elif key == 'EMCCD_gain':
            self.set_emccd_gain(value)
            self.curr_config['EMCCD_gain'] = value
        elif key == 'high_em_gain':
            self.set_high_em_gain(value)
            self.curr_config['high_em_gain'] = value
        elif key == 'shutter_mode':
            self.set_shutter_mode(value)
            self.curr_config['shutter_mode'] = value
        elif key == 'fan_mode':
            self.set_fan_mode(value)
            self.curr_config['fan_mode'] = value
        elif key == 'roi':
            self.set_roi(value)
            self.curr_config['roi'] = value
        else:
            raise ValueError(f"Unknown config setting: {key}")
        return
    
    def get_camera_state(self, full=False):
        temperature = self.camera_instance.get_temperature()
        shutter_mode = self.camera_instance.get_shutter()
        state = {
            'temperature': temperature,
            'shutter_mode': shutter_mode
        }
        return state
    
    def pull_images(self):
        self.camera_instance.wait_for_frame(nframe=self.n_states)
        images = self.camera_instance.read_multiple_images(rng=(0, self.n_states-1))
        return images
    
    def set_temperature(self, temp):
        self.camera_instance.set_temperature(temp)
        return
    
    def set_oamp(self, oamp):
        self.camera_instance.set_amp_mode(oamp=oamp)
        return
    
    def set_hsspeed(self, speed):
        self.camera_instance.set_amp_mode(hsspeed=speed)
        return
    
    def set_vsspeed(self, speed):
        self.camera_instance.set_vsspeed(speed)
        return
    
    def set_preamp(self, preamp):
        self.camera_instance.set_amp_mode(preamp=preamp)
        return
    
    def set_exposure(self, exposure):
        self.camera_instance.set_exposure(exposure)
        return
    
    def set_trigger_mode(self, mode):
        self.camera_instance.set_trigger_mode(mode)
        return
    
    def set_emccd_gain(self, gain):
        self.camera_instance.set_EMCCD_gain(gain)
        return
    
    def set_high_em_gain(self, high):
        self.camera_instance.set_EMCCD_gain(self.curr_config['EMCCD_gain'], advanced=high)
        return
    
    def set_shutter_mode(self, mode):
        self.camera_instance.setup_shutter(mode)
        return  
    
    def set_fan_mode(self, mode):
        self.camera_instance.set_fan_mode(mode)
        return
    
    def set_roi(self, roi):
        self.camera_instance.set_roi(roi['x_left'],
                                     roi['x_right'],
                                     roi['y_bottom'],
                                     roi['y_top'],
                                     roi['x_binning'],
                                     roi['y_binning'])
        return