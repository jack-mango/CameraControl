import pytest
import time
from multiprocessing import Queue, Value, Event
import threading
from pylablib.devices import Andor
from camera_control import AcquisitionWorker
import numpy as np


@pytest.fixture(scope="module")
def real_camera():
    cam = Andor.AndorSDK2.AndorSDK2Camera()
    yield cam
    cam.close()


@pytest.fixture
def worker(real_camera):
    worker = AcquisitionWorker(
        camera_instance=real_camera,
        config_queue=Queue(),
        info_queue=Queue(),
        data_queue=Queue(),
        teardown_flag=Event(),
        acquisition_flag=Value('b', False),
        shot_counter=Value('i', 0),    
        n_states=1,
        n_shots=1,
    )
    yield worker
    worker.teardown_flag.set()


def test_single_param_update(worker, real_camera):
    # Save default exposure
    default_exposure = real_camera.get_exposure()

    # Only update exposure
    new_config = {"exposure": 20e-6}

    worker.curr_config = {}
    worker.update_config(new_config)

    # Assert only exposure was updated
    assert real_camera.get_exposure() == pytest.approx(new_config["exposure"], rel=1e-2)

    # Make sure a different parameter (e.g., shutter) wasn’t changed
    current_shutter = real_camera.get_shutter()
    default_shutter = real_camera.get_shutter()
    assert current_shutter == default_shutter

    # Restore original exposure
    worker.update_config({"exposure": default_exposure})
    time.sleep(0.5)

def test_update_full_config(worker, real_camera):
    full_config = {
        "temperature": -60,
        "fan_mode": "full",
        "oamp": 0,
        "hsspeed": 1,
        "vsspeed": 2,
        "preamp": 1,
        "exposure": 0.001,
        "trigger_mode": "ext",
        "EMCCD_gain": 10,
        "high_em_gain": 1,
        "shutter_mode": "closed",
        "acquisition_mode": "single",
        "roi": {
            "x_left": 241,
            "y_bottom": 256,
            "x_right": 752,
            "y_top": 767,
            "x_binning": 1,
            "y_binning": 1,
        },
    }

    worker.curr_config = {}
    worker.update_config(full_config)

    # Assertions for each parameter
    assert real_camera.get_temperature_setpoint() <= full_config["temperature"] + 1  # tolerance
    assert real_camera.get_fan_mode() == full_config["fan_mode"]
    assert real_camera.get_amp_mode().hsspeed == full_config["hsspeed"]
    assert real_camera.get_vsspeed() == full_config["vsspeed"]
    assert real_camera.get_preamp() == full_config["preamp"]
    assert real_camera.get_exposure() == pytest.approx(full_config["exposure"], rel=1e-3)
    assert real_camera.get_trigger_mode() == full_config["trigger_mode"]
    assert real_camera.get_EMCCD_gain()[0] == full_config["EMCCD_gain"]
    assert real_camera.get_EMCCD_gain()[1] == full_config["high_em_gain"]
    assert real_camera.get_shutter() == full_config["shutter_mode"]
    assert real_camera.get_acquisition_mode() == full_config["acquisition_mode"]

    x_left, x_right, y_bottom, y_top, x_binning, y_binning = real_camera.get_roi()
    assert x_left == full_config["roi"]["x_left"] 
    assert x_right == full_config["roi"]["x_right"]
    assert y_bottom == full_config["roi"]["y_bottom"]
    assert y_top == full_config["roi"]["y_top"]
    assert x_binning == full_config["roi"]["x_binning"]
    assert y_binning == full_config["roi"]["y_binning"]


def test_images_available_true(worker):
    # Set config with external trigger
    full_config = {
        "temperature": -60,
        "fan_mode": "full",
        "oamp": 0,
        "hsspeed": 1,
        "vsspeed": 2,
        "preamp": 1, 
        "exposure": 0.01,
        "trigger_mode": 'ext',
        "EMCCD_gain": 10,
        "high_em_gain": 1,
        "shutter_mode": "auto",
        "acquisition_mode": "cont",
        "roi": {
            "x_left": 241,
            "y_bottom": 256,
            "x_right": 752,
            "y_top": 767,
            "x_binning": 1,
            "y_binning": 1,
        },
    }
    worker.update_config(full_config)
    worker.camera_instance.start_acquisition()
    time.sleep(2)
    assert worker.images_available() == True
    worker.camera_instance.stop_acquisition()


def test_run_multiple_shots_single_state(worker):
    worker.n_shots = 10

    full_config = {
        "temperature": -60,
        "fan_mode": "full",
        "oamp": 0,
        "hsspeed": 1,
        "vsspeed": 2,
        "preamp": 1,
        "exposure": 0.01,
        "trigger_mode": 'ext',
        "EMCCD_gain": 10,
        "high_em_gain": 1,
        "shutter_mode": "auto",
        "acquisition_mode": "cont",
        "roi": {
            "x_left": 241,
            "y_bottom": 256,
            "x_right": 752,
            "y_top": 767,
            "x_binning": 1,
            "y_binning": 1,
        },
    }

    # Update config with full settings including ext trigger
    worker.update_config(full_config)

    worker.set_acquisition_flag(True)

    # Start the acquisition worker thread
    worker_thread = threading.Thread(target=worker.run, daemon=True)
    worker_thread.start()

    time.sleep(15)

    worker_thread.join(timeout=1)

    # Count images in data queue
    images_received = 0
    while not worker.data_queue.empty():
        _ = worker.data_queue.get()
        images_received += 1    

    assert images_received == 10, f"Expected 10 images, got {images_received}"
    assert worker.get_shot_counter() == 10

#TODO: Further tests to write
# Multiple states multiple shots

# Single state multiple shots with a config update received during acquisition
# Single state multiple shots that ends before getting all shots
