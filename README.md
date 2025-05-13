OT Bioelettronica Python Communication Scripts
This repository contains Python scripts developed for communicating with OT Bioelettronica devices. Two versions are provided, based on different graphical libraries: PyQt and Matplotlib.

Folder Structure
PyQt/
This folder contains communication scripts using the PyQt framework.
It provides a more optimized and responsive interface compared to the Matplotlib version, especially for real-time plotting and interaction. This version is recommended for practical use.

Matplotlib/
This folder contains an alternative implementation using Matplotlib.
Although the plotting performance is less efficient, this version is kept for completeness and educational purposes.

It includes the following subfolders:

device_communication/
Scripts for establishing and managing communication with OT Bioelettronica devices.

example/
Example scripts demonstrating how to send commands, receive data, and manage basic I/O operations.

Notes
The PyQt version is generally more suitable for real-time data acquisition.

The Matplotlib version may be useful for testing or environments where PyQt is not available.
