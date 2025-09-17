# test_file_worker.py
import pytest
import tempfile
import os
import numpy as np
import queue
import threading
import h5py
import time
from unittest import mock

from camera_control import FileWorker


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def worker(tmp_dir):
    return FileWorker(
        file_path=tmp_dir,
        image_queue=queue.Queue(),
        parameter_queue=queue.Queue(),
    )


# -----------------------
# Tests
# -----------------------

def test_save_creates_file_with_timestamp(worker, tmp_dir):
    images = np.random.randint(0, 255, size=(2, 10, 10), dtype=np.uint8)
    params = {"voltage": 3.3}

    # Mock localtime to return a fixed time
    fixed_time = time.struct_time((2025, 1, 1, 9, 26, 31, 0, 0, -1))
    with mock.patch("time.localtime", return_value=fixed_time):
        worker.save(images, params)

    expected_name = "0926_31.h5"
    expected_path = os.path.join(tmp_dir, expected_name)

    assert os.path.exists(expected_path)

    with h5py.File(expected_path, "r") as f:
        assert "images" in f
        np.testing.assert_array_equal(f["images"][:], images)
        for k, v in params.items():
            assert f["params"].attrs[k] == v


def test_save_creates_pm_filename(worker, tmp_dir):
    images = np.zeros((1, 5, 5), dtype=np.uint8)
    params = {"laser": 1550.0}

    # Mock localtime to 4:07:06 PM
    fixed_time = time.struct_time((2025, 1, 1, 16, 7, 6, 0, 0, -1))
    with mock.patch("time.localtime", return_value=fixed_time):
        worker.save(images, params)

    expected_name = "1607_06.h5"
    expected_path = os.path.join(tmp_dir, expected_name)
    assert os.path.exists(expected_path)


def test_run_consumes_queues_and_saves(worker, tmp_dir):
    images = np.ones((2, 3, 3), dtype=np.uint8)
    params = {"shot": 7}

    worker.image_queue.put(images)
    worker.parameter_queue.put(params)

    fixed_time = time.struct_time((2025, 1, 1, 10, 0, 0, 0, 0, -1))
    with mock.patch("time.localtime", return_value=fixed_time):
        t = threading.Thread(target=worker.run, daemon=True)
        t.start()
        time.sleep(0.05)
        t.join(timeout=1)

    expected_name = "1000_00.h5"
    expected_path = os.path.join(tmp_dir, expected_name)
    assert os.path.exists(expected_path)

    with h5py.File(expected_path, "r") as f:
        assert np.array_equal(f["images"][:], images)
        assert f["params"].attrs["shot"] == 7

def test_run_only_images(worker, tmp_dir):
    # Put images only
    images = np.ones((2, 3, 3), dtype=np.uint8)
    worker.image_queue.put(images)

    # Mock time so if a file is saved, it would have a predictable name
    fixed_time = time.struct_time((2025, 1, 1, 11, 0, 0, 0, 0, -1))
    with mock.patch("time.localtime", return_value=fixed_time):
        # Run worker in background
        t = threading.Thread(target=worker.run, daemon=True)
        t.start()
        time.sleep(0.05)  # give the worker time to run
        t.join(timeout=1)

    # Ensure nothing was saved because no params were queued
    saved_files = os.listdir(tmp_dir)
    assert len(saved_files) == 0, f"Unexpected files saved: {saved_files}"



def test_run_only_params(worker, tmp_dir):
    # Put params only
    params = {"temperature": 77}
    worker.parameter_queue.put(params)

    # Mock time so any saved file would have a predictable name
    fixed_time = time.struct_time((2025, 1, 1, 12, 0, 0, 0, 0, -1))
    with mock.patch("time.localtime", return_value=fixed_time):
        # Run worker in background
        t = threading.Thread(target=worker.run, daemon=True)
        t.start()
        time.sleep(0.05)  # give the worker time to run
        t.join(timeout=1)

    # Ensure nothing was saved because no images were queued
    saved_files = os.listdir(tmp_dir)
    assert len(saved_files) == 0, f"Unexpected files saved: {saved_files}"


def test_run_mismatched_queue_lengths(worker, tmp_dir):
    img1 = np.ones((1, 2, 2), dtype=np.uint8)
    img2 = np.zeros((1, 2, 2), dtype=np.uint8)

    worker.image_queue.put(img1)
    worker.image_queue.put(img2)
    worker.parameter_queue.put({"step": 1})  # only one param

    fixed_time = time.struct_time((2025, 1, 1, 13, 0, 0, 0, 0, -1))
    with mock.patch("time.localtime", return_value=fixed_time):
        t = threading.Thread(target=worker.run, daemon=True)
        t.start()
        time.sleep(0.1)
        t.join(timeout=1)

    files = os.listdir(tmp_dir)
    assert len(files) == 1  # Only one pair matched

def test_run_images_and_params_arrive_at_different_times(worker, tmp_dir):
    img1 = np.ones((1, 4, 4), dtype=np.uint8)
    img2 = np.zeros((1, 4, 4), dtype=np.uint8)

    param1 = {"index": 1}
    param2 = {"index": 2}

    fixed_time1 = time.struct_time((2025, 1, 1, 14, 0, 0, 0, 0, -1))
    fixed_time2 = time.struct_time((2025, 1, 1, 14, 0, 1, 0, 0, -1))

    # Patch time.localtime in the FileWorker module so worker.run sees it
    with mock.patch("camera_control.FileWorker.time.localtime", side_effect=[fixed_time1, fixed_time2]):
        # Run worker in background
        t = threading.Thread(target=worker.run, daemon=True)
        t.start()

        # First put images only
        worker.image_queue.put(img1)
        worker.image_queue.put(img2)

        # Small delay before parameters arrive
        time.sleep(0.05)
        worker.parameter_queue.put(param1)

        time.sleep(0.05)
        worker.parameter_queue.put(param2)

        # Allow processing then stop
        time.sleep(0.1)
        worker.running = False
        t.join(timeout=1)

    # Both should have been saved once params arrived
    files = sorted(os.listdir(tmp_dir))
    assert len(files) == 2
    assert files[0] == "1400_00.h5"
    assert files[1] == "1400_01.h5"

    with h5py.File(os.path.join(tmp_dir, files[0]), "r") as f:
        np.testing.assert_array_equal(f["images"][:], img1)
        assert f["params"].attrs["index"] == 1

    with h5py.File(os.path.join(tmp_dir, files[1]), "r") as f:
        np.testing.assert_array_equal(f["images"][:], img2)
        assert f["params"].attrs["index"] == 2

