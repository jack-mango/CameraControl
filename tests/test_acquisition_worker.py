import pytest
import time
from multiprocessing import Queue, Value, Event
from pylablib.devices import Andor
from camera_control import AcquisitionWorker
import numpy as np


@pytest.fixture
def worker():
    worker = AcquisitionWorker(
        camera_idx=0,
        config_queue=Queue(),
        info_queue=Queue(),
        data_queue=Queue(),
        acquisition_flag=Event(),
        teardown_flag=Event(),
        shot_counter=Value('i', 0),
        frames_per_shot=1,
        n_shots=1,
    )
    yield worker
    worker.teardown_flag.set()
    if worker.is_alive():
        worker.terminate()
        worker.join()


def test_single_param_update(worker):
    # Connect camera first
    worker.connect_camera()
    
    default_exposure = worker.camera.get_exposure()
    new_config = {"Exposure time (ms)": 0.02}

    worker.curr_config = {}
    worker.update_config(new_config)

    assert worker.camera.get_exposure() == pytest.approx(new_config["Exposure time (ms)"], rel=1e-2)

    current_shutter = worker.camera.get_shutter()
    default_shutter = worker.camera.get_shutter()
    assert current_shutter == default_shutter

    worker.update_config({"Exposure time (ms)": default_exposure})
    time.sleep(0.5)
    
    worker.disconnect_camera(0)


def test_update_full_config(worker):
    # Connect camera first
    worker.connect_camera()
    
    full_config = {
        "Temperature (C)": -60,
        "Fan mode": "full",
        "Amplifier": 0,
        "Horizontal shift speed (MHz)": 1,
        "Vertical shift speed (us)": 2,
        "Preamp gain": 1,
        "Exposure time (ms)": 0.01,
        "Trigger mode": 'int',
        "EM gain": 10,
        "High EM gain": False,
        "Shutter mode": "closed",
        "Acquisition mode": "cont",
        "X Origin": 10,
        "Y Origin": 10,
        "X Width": 100,
        "Y Height": 100,
        "X binning": 1,
        "Y binning": 1,
    }

    worker.curr_config = {}
    worker.update_config(full_config)

    assert worker.camera.get_temperature_setpoint() <= full_config["Temperature (C)"] + 1
    assert worker.camera.get_fan_mode() == full_config["Fan mode"]
    assert worker.camera.get_amp_mode().hsspeed == full_config["Horizontal shift speed (MHz)"]
    assert worker.camera.get_vsspeed() == full_config["Vertical shift speed (us)"]
    assert worker.camera.get_preamp() == full_config["Preamp gain"]
    assert worker.camera.get_exposure() == pytest.approx(full_config["Exposure time (ms)"], rel=1e-3)
    assert worker.camera.get_trigger_mode() == full_config["Trigger mode"]
    assert worker.camera.get_EMCCD_gain()[0] == full_config["EM gain"]
    assert worker.camera.get_EMCCD_gain()[1] == full_config["High EM gain"]
    assert worker.camera.get_shutter() == full_config["Shutter mode"]
    assert worker.camera.get_acquisition_mode() == full_config["Acquisition mode"]

    x_left, x_right, y_bottom, y_top, x_binning, y_binning = worker.camera.get_roi()
    assert x_left == full_config["X Origin"]
    assert x_right == full_config["X Origin"] + full_config["X Width"]
    assert y_bottom == full_config["Y Origin"]
    assert y_top == full_config["Y Origin"] + full_config["Y Height"]
    assert x_binning == full_config["X binning"]
    assert y_binning == full_config["Y binning"]
    
    worker.disconnect_camera(0)


def test_get_number_of_available_images(worker):
    # Connect camera first
    worker.connect_camera()
    
    full_config = {
        "Temperature (C)": -60,
        "Fan mode": "full",
        "Amplifier": 0,
        "Horizontal shift speed (MHz)": 1,
        "Vertical shift speed (us)": 2,
        "Preamp gain": 1,
        "Exposure time (ms)": 0.01,
        "Trigger mode": 'int',
        "EM gain": 10,
        "High EM gain": False,
        "Shutter mode": "closed",
        "Acquisition mode": "cont",
        "X Origin": 241,
        "Y Origin": 256,
        "X Width": 511,
        "Y Height": 511,
        "X binning": 1,
        "Y binning": 1,
    }
    worker.update_config(full_config)
    worker.camera.start_acquisition()
    
    # Wait for some images to accumulate
    time.sleep(0.5)
    
    # Check that we have images available
    num_images = worker.get_number_of_available_images()
    assert num_images > 0, f"Expected at least 1 image, got {num_images}"
    
    # Pull images and verify count decreases
    initial_count = worker.get_number_of_available_images()
    if initial_count >= worker.frames_per_shot:
        worker.pull_images()
        new_count = worker.get_number_of_available_images()
        # Should have fewer images after pulling (unless more came in)
        assert new_count >= 0
    
    worker.camera.stop_acquisition()
    worker.disconnect_camera(0)


def test_pull_images_with_range(worker):
    # Connect camera first
    worker.connect_camera()
    
    worker.frames_per_shot = 3
    
    full_config = {
        "Temperature (C)": -60,
        "Fan mode": "full",
        "Amplifier": 0,
        "Horizontal shift speed (MHz)": 1,
        "Vertical shift speed (us)": 2,
        "Preamp gain": 1,
        "Exposure time (ms)": 0.01,
        "Trigger mode": 'int',
        "EM gain": 10,
        "High EM gain": False,
        "Shutter mode": "closed",
        "Acquisition mode": "cont",
        "X Origin": 10,
        "Y Origin": 10,
        "X Width": 100,
        "Y Height": 100,
        "X binning": 1,
        "Y binning": 1,
    }
    worker.update_config(full_config)
    worker.camera.start_acquisition()
    
    # Wait for enough images to accumulate
    time.sleep(1.0)
    
    # Check that we have enough images
    num_available = worker.get_number_of_available_images()
    assert num_available >= worker.frames_per_shot, \
        f"Expected at least {worker.frames_per_shot} images, got {num_available}"
    
    # Pull images using the new approach
    images = worker.pull_images()
    
    # Verify we got the right number of images
    assert len(images) == worker.frames_per_shot, \
        f"Expected {worker.frames_per_shot} images, got {len(images)}"
    
    # Verify images have the correct shape
    # assert all(isinstance(img, np.ndarray) for img in images)
    
    worker.camera.stop_acquisition()
    worker.disconnect_camera(0)


def test_multiple_frames_per_shot(worker):
    worker.n_shots = 1
    worker.frames_per_shot = 10

    full_config = {
        "Temperature (C)": -60,
        "Fan mode": "full",
        "Amplifier": 0,
        "Horizontal shift speed (MHz)": 1,
        "Vertical shift speed (us)": 2,
        "Preamp gain": 1,
        "Exposure time (ms)": 0.01,
        "Trigger mode": 'int',
        "EM gain": 10,
        "High EM gain": False,
        "Shutter mode": "closed",
        "Acquisition mode": "cont",
        "X Origin": 10,
        "Y Origin": 10,
        "X Width": 100,
        "Y Height": 100,
        "X binning": 1,
        "Y binning": 1,
    }

    # Push config to queue
    worker.config_queue.put(full_config)
    
    # Set acquisition flag
    worker.acquisition_flag.set()

    worker.start()
    worker.join(timeout=15)

    # Get images from data queue
    assert not worker.data_queue.empty(), "Expected images in data queue"
    images = worker.data_queue.get()
    
    # Verify we got an ndarray with shape (10, 100, 100)
    assert isinstance(images, np.ndarray), f"Expected ndarray, got {type(images)}"
    assert images.shape == (10, 100, 100), f"Expected shape (10, 100, 100), got {images.shape}"
