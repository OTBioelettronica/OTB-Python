import socket
import sys
import time
import signal
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg
import struct
import numpy as np


# Configuration class
class Config:
    DEFAULT_PLOT_TIME = 1      # seconds
    UPDATE_RATE = 16           # milliseconds (~60 FPS)
    PLOT_HEIGHT = 600          # pixels
    WINDOW_SIZE = (1200, 800)  # width, height


class Track:
    def __init__(self, title, frequency, num_channels, offset, conv_fact, plot_time=1):
        self.title = title
        self.frequency = frequency
        self.num_channels = num_channels
        self.offset = offset
        self.conv_fact = conv_fact
        self.plot_time = plot_time
        self.buffer = np.zeros((num_channels, int(plot_time * frequency)))
        self.buffer_index = 0
        self.time_array = np.linspace(0, self.plot_time, self.buffer.shape[1])

        # Create PlotWidget with enhanced interactive features
        self.plot_widget = pg.PlotWidget(title=self.title)
        self.plot_widget.setXRange(0, plot_time)  # Set initial x-axis range
        
        # Enable mouse interactions
        self.plot_widget.setMouseEnabled(x=True, y=True)  # Enable both x and y mouse interaction
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Add labels and units
        if 'Bipolar 4 channels' in title:
            self.plot_widget.setLabel('left', 'Amplitude', units='V')
        else:
            self.plot_widget.setLabel('left', 'Amplitude', units='A.U.')
        
        self.plot_widget.setLabel('bottom', 'Time', units='s')

        # Set background and enable antialiasing
        self.plot_widget.getViewBox().setBackgroundColor((30, 30, 30))
        self.plot_widget.setAntialiasing(True)
        
        # Enable auto range button
        self.plot_widget.enableAutoRange()
        
        # Get colors for this track type
        self.curves = []
        for i in range(num_channels):
            if title == 'Quaternions':
                # Use white for Quaternions
                pen = pg.mkPen(color=(255, 255, 255), width=1)
            elif title == 'Buffer':
                # Use white for Buffer
                pen = pg.mkPen(color=(255, 255, 255), width=1)
            elif title == 'Ramp':
                # Use white for Ramp
                pen = pg.mkPen(color=(255, 255, 255), width=1)
            else:
                # Use pyqtgraph's default color cycling for other tracks
                pen = pg.mkPen(color=i, width=1)

            curve_name = f"Ch {i+1}" if i < 8 or num_channels <= 8 else None
            curve = self.plot_widget.plot(pen=pen, name=curve_name)
            self.curves.append(curve)

    def feed(self, packet):
        packet_size = packet.shape[1]
        # Use buffer management
        if self.buffer_index + packet_size > self.buffer.shape[1]:
            # Calculate exactly how much data fits at the end
            end_space = self.buffer.shape[1] - self.buffer_index
            if end_space > 0:
                self.buffer[:, self.buffer_index:] = packet[:, :end_space]
            self.buffer[:, :packet_size-end_space] = packet[:, end_space:]
            self.buffer_index = packet_size - end_space
        else:
            self.buffer[:, self.buffer_index:self.buffer_index + packet_size] = packet
            self.buffer_index = (self.buffer_index + packet_size) % self.buffer.shape[1]

    def draw(self):
        for index, curve in enumerate(self.curves):
            curve.setData(self.time_array, self.buffer[index, :] * self.conv_fact + (self.offset * index))


class DataReceiverThread(QtCore.QThread):
    data_received = QtCore.pyqtSignal(np.ndarray)
    status_update = QtCore.pyqtSignal(str)

    def __init__(self, device, client_socket, tracks):
        super().__init__()
        self.device = device
        self.client_socket = client_socket
        self.tracks = tracks
        self.running = True
        self.packet_count = 0
        self.last_time = time.time()
        self.fps = 0

    def run(self):
        while self.running:
            try:
                data = self.client_socket.recv(self.device.nchannels * 2 * (self.device.frequency // 16))
                if not data:
                    print("No data received, connection may be closed")
                    break

                unpacked_data = struct.unpack(f'>{len(data) // 2}h', data)
                reshaped_data = np.array(unpacked_data).reshape((-1, self.device.nchannels)).T

                channel_index = 0
                for track in self.tracks:
                    track.feed(reshaped_data[channel_index:channel_index + track.num_channels, :])
                    channel_index += track.num_channels

                self.data_received.emit(reshaped_data)
                
                # Calculate FPS every 100 packets
                self.packet_count += 1
                if self.packet_count % 100 == 0:
                    current_time = time.time()
                    elapsed = current_time - self.last_time
                    self.fps = 100 / elapsed if elapsed > 0 else 0
                    self.last_time = current_time
                    self.status_update.emit(f"Data rate: {self.fps:.1f} packets/second")
                    
            except Exception as e:
                print(f"Error receiving data: {e}")
                break

    def stop(self):
        print("Stopping data receiver thread")
        self.running = False


class Soundtrack(QtWidgets.QWidget):
    def __init__(self, device, client_socket):
        super().__init__()
        self.device = device
        self.client_socket = client_socket
        self.tracks = []
        self.plot_time = Config.DEFAULT_PLOT_TIME
        self.is_paused = False

        self.setWindowTitle("Quattro+ Data Visualization")
        self.setGeometry(100, 100, *Config.WINDOW_SIZE)

        # Create main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)

        # Create menu bar widget
        self.menu_widget = QtWidgets.QWidget()
        self.menu_layout = QtWidgets.QHBoxLayout(self.menu_widget)
        
        # Create and setup the combo box for plot time
        self.time_selector = QtWidgets.QComboBox()
        self.time_selector.addItems(['100ms', '250ms', '500ms', '1s', '5s', '10s'])
        self.time_selector.setCurrentText(f"{Config.DEFAULT_PLOT_TIME}s")
        self.time_selector.currentTextChanged.connect(self.change_plot_time)
        
        # Add label and combo box to menu layout
        self.menu_layout.addWidget(QtWidgets.QLabel("Plot Time:"))
        self.menu_layout.addWidget(self.time_selector)
        
        # Add pause button
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.pause_button.setCheckable(True)
        self.pause_button.toggled.connect(self.toggle_pause)
        self.menu_layout.addWidget(self.pause_button)

        # Add status label
        self.status_label = QtWidgets.QLabel("Ready")
        self.menu_layout.addWidget(self.status_label)
        
        # Add stretch to push widgets to the left
        self.menu_layout.addStretch()  
        
        # Add menu widget to main layout
        self.main_layout.addWidget(self.menu_widget)
        
        # Create scroll area
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Create widget to hold plots
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        
        # Add scroll area to main layout
        self.main_layout.addWidget(self.scroll_area)
        self.scroll_area.setWidget(self.scroll_widget)
        
        self.init_tracks()

        # Timer for plot updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(Config.UPDATE_RATE)

        self.receiver_thread = DataReceiverThread(self.device, self.client_socket, self.tracks)
        self.receiver_thread.status_update.connect(self.update_status)
        self.receiver_thread.start()

    def init_tracks(self):
        track_info = [
            ('Bipolar 4 channels', 4, 0, 0.01, 0.000000249),
            ('Quaternions', 4, 5, 1, 1),
            ('Buffer', 1, 9, 1, 1),
            ('Ramp', 1, 10, 1, 1),
        ]

        for title, n_channels, acq_channel, offset, conv_fact in track_info:
            # Create container widget for each track
            track_container = QtWidgets.QWidget()
            track_layout = QtWidgets.QVBoxLayout(track_container)
            
            track = Track(title, self.device.frequency, n_channels, offset, conv_fact, self.plot_time)
            self.tracks.append(track)
            
            # Set minimum height for the plot widget
            track.plot_widget.setMinimumHeight(Config.PLOT_HEIGHT)
            
            # Add plot widget to track container
            track_layout.addWidget(track.plot_widget)
            
            # Add track container to scroll layout
            self.scroll_layout.addWidget(track_container)

        # Add stretch at the end to prevent unwanted spacing
        self.scroll_layout.addStretch()

    def change_plot_time(self, time_str):
        # Convert string time to seconds
        if time_str.endswith('ms'):
            new_time = float(time_str[:-2]) / 1000  # Convert milliseconds to seconds
        else:
            new_time = float(time_str[:-1])  # Remove 's' and convert to float
        
        print(f"Changing plot time to {new_time} seconds")
        
        # Update plot time for all tracks
        for track in self.tracks:
            # Create new buffer with new size
            new_buffer = np.zeros((track.num_channels, int(new_time * track.frequency)))
            
            # Copy existing data if possible
            if track.buffer_index > 0:
                # Calculate how much data to copy
                copy_size = min(new_buffer.shape[1], track.buffer.shape[1])
                new_buffer[:, -copy_size:] = track.buffer[:, -copy_size:]
            
            # Update track properties
            track.plot_time = new_time
            track.buffer = new_buffer
            track.buffer_index = min(track.buffer_index, new_buffer.shape[1])
            track.time_array = np.linspace(0, track.plot_time, track.buffer.shape[1])
            
            # Update plot x-axis range
            track.plot_widget.setXRange(0, new_time)

    def toggle_pause(self, checked):
        self.is_paused = checked
        self.pause_button.setText("Resume" if checked else "Pause")
        if checked:
            self.timer.stop()
            print("Visualization paused")
        else:
            self.timer.start(Config.UPDATE_RATE)
            print("Visualization resumed")

    def update_status(self, message):
        self.status_label.setText(message)

    def update_plot(self):
        if not self.is_paused:
            for track in self.tracks:
                track.draw()

    def closeEvent(self, event):
        print("Closing application")
        self.receiver_thread.stop()
        self.receiver_thread.wait()
        self.client_socket.close()
        event.accept()


class Muovi:
    def __init__(self, host="0.0.0.0", port=54321):
        self.host = host
        self.port = port
        self.nchannels = 10
        self.frequency = 2000
        self.server_socket = None
        self.client_socket = None

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_server()

    def start_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            print(f"Server listening on {self.host}:{self.port}")

            self.client_socket, addr = self.server_socket.accept()
            print(f"Connection accepted from {addr}")

            probe_en = 1
            emg = 1
            mode = 0
            command = 0 + (emg * 8) + (mode * 2) + probe_en
            self.client_socket.send(bytes([command]))

        except socket.error as e:
            print(f"Error creating server: {e}")
            sys.exit(1)

    def stop_server(self):
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()
        print("Server stopped")


def signal_handler(sig, frame):
    print("Interrupt received, shutting down...")
    if 'window' in globals():
        window.close()
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handler for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    app = QtWidgets.QApplication([])
    
    # Enable antialiasing for smoother plotting
    pg.setConfigOptions(antialias=True)
    
    # Start server and accept connection using context manager
    with Muovi() as device:
        device.start_server()

        # Create and show application window
        window = Soundtrack(device, device.client_socket)
        window.show()

        # Run PyQt application
        sys.exit(app.exec_())