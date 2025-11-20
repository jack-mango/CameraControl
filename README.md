# CameraControl - Andor Camera Acquisition System

A Python-based application for controlling Andor SDK2 cameras with multi-threaded image acquisition, real-time parameter monitoring, and flexible data storage options.

## Features

- **Multi-Camera Support**: Search, connect, and control multiple Andor cameras
- **Real-Time Acquisition**: Multi-process architecture for continuous image capture without blocking
- **Flexible Data Storage**: Save acquired images in multiple formats (HDF5, NPZ, MAT)
- **Network Integration**: Socket-based parameter communication for synchronized experimental control
- **Live Monitoring**: Real-time temperature monitoring and camera status updates
- **Configurable Settings**: Comprehensive control over camera parameters including:
  - Trigger modes (External, External Exposure)
  - EM gain and amplifier settings
  - Exposure time and ROI configuration
  - Shutter control
  - Temperature management

## Architecture

- **Controller**: Main orchestration thread managing camera operations and data flow
- **AcquisitionWorker**: Separate process for camera communication and image capture
- **FileWorker**: Background thread for buffered data storage
- **ConnectionWorker**: Socket interface for external parameter synchronization

## Requirements

- Python 3.x
- PyQt5
- pylablib
- Andor SDK2
- NumPy

## Use Case

Designed for experimental physics applications requiring synchronized camera acquisition with external control systems, particularly for time-resolved imaging experiments.
