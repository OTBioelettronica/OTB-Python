import socket
import numpy as np
import time

import threading
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication
from pyqtgraph.Qt import QtCore

import math

def CRC8(Vector, Len):
    crc = 0
    j = 0

    while Len > 0:
        Extract = Vector[j]
        for i in range(8, 0, -1):
            Sum = crc % 2 ^ Extract % 2
            crc //= 2

            if Sum > 0:
                str_list = [0]* 8
                a = format(crc, '08b')
                b = format(140, '08b')
                
                for k in range(8):
                    str_list[k] = int(a[k] != b[k])

                crc = int(''.join(map(str, str_list)), 2)

            Extract //= 2

        Len -= 1
        j += 1

    return crc
	
# Configuration
PlotChan = list(range(0, 100))
PlotTime = 10
Update_time = 63
Decim = 64

offset = 2
Fsamp = [0, 8, 16, 24]

# Sampling frequency values
FsampVal = [512, 2048, 5120, 10240]
FSsel = 3
NumChan = [0, 2, 4, 6]  # Codes to set the number of channels
# Channels numbers
NumChanVal = [120, 216, 312, 408]
NCHsel = 3
AnOutSource = 9  # Source input for analog output
AnOutChan = 0    # Channel for analog output
AnOutGain = int('00000000', 2)

# Number of TCP socket port
TCPPort = 23456

GainFactor = 5 / 2**16 / 150 * 1000  # Provide amplitude in mV
AuxGainFactor = 5 / 2**16 / 0.5      # Gain factor to convert Aux Channels in V

# Create the command to send to Quattrocento
ConfString = [0] * 40
ConfString[0] = int('10000000', 2) + Decim + Fsamp[FSsel] + NumChan[NCHsel] + 1
ConfString[1] = AnOutGain + AnOutSource
ConfString[2] = AnOutChan
# -------- IN 1 --------
ConfString[3] = 0
ConfString[4] = 0
ConfString[5] = int('00010100', 2)
# -------- IN 2 --------
ConfString[6] = 0
ConfString[7] = 0
ConfString[8] = int('00010100', 2)
# -------- IN 3 --------
ConfString[9] = 0
ConfString[10] = 0
ConfString[11] = int('00010100', 2)
# -------- IN 4 --------
ConfString[12] = 0
ConfString[13] = 0
ConfString[14] = int('00010100', 2)
# -------- IN 5 --------
ConfString[15] = 0
ConfString[16] = 0
ConfString[17] = int('00010100', 2)
# -------- IN 6 --------
ConfString[18] = 0
ConfString[19] = 0
ConfString[20] = int('00010100', 2)
# -------- IN 7 --------
ConfString[21] = 0
ConfString[22] = 0
ConfString[23] = int('00010100', 2)
# -------- IN 8 --------
ConfString[24] = 0
ConfString[25] = 0
ConfString[26] = int('00010100', 2)
# -------- MULTIPLE IN 1 --------
ConfString[27] = 0
ConfString[28] = 0
ConfString[29] = int('00010100', 2)
# -------- MULTIPLE IN 2 --------
ConfString[30] = 0
ConfString[31] = 0
ConfString[32] = int('00010100', 2)
# -------- MULTIPLE IN 3 --------
ConfString[33] = 0
ConfString[34] = 0
ConfString[35] = int('00010100', 2)
# -------- MULTIPLE IN 4 --------
ConfString[36] = 0
ConfString[37] = 0
ConfString[38] = int('00010100', 2)
# ---------- CRC8 ----------
ConfString[39] = CRC8(ConfString, 39)

# Control channels
RampChan = NumChanVal[NCHsel] - 7
BuffChan = NumChanVal[NCHsel] - 4
TotSamp = 0

# Open the TCP socket
tcpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcpSocket.connect(('169.254.1.10', TCPPort))

# Send the configuration to Quattrocento
tcpSocket.sendall(bytearray(ConfString))

ConfString[0] = ConfString[0] + int('00100000', 2)  # Force the trigger to go high (bit 5)
ConfString[39] = CRC8(ConfString, 39)  # Estimates the new CRC
time.sleep(1)
tcpSocket.sendall(bytearray(ConfString))

communication = True

# Define a buffer to store 1 second of data
buffer_length = int(FsampVal[FSsel] * PlotTime)
data_buffer = np.zeros((buffer_length, NumChanVal[NCHsel]), dtype=np.int16)
buffer_index = 0

def receive_data():
    global buffer_index
    buffer = b''
    expected_bytes = 2 * int((NumChanVal[NCHsel] * FsampVal[FSsel]) / 16)

    while communication:
        try:
            while len(buffer) < expected_bytes:
                buffer += tcpSocket.recv(expected_bytes - len(buffer))

            data = buffer[:expected_bytes]
            buffer = buffer[expected_bytes:]

            new_data = np.frombuffer(data, dtype=np.int16).reshape(int(FsampVal[FSsel] / 16), NumChanVal[NCHsel])
            data_length = new_data.shape[0]

            if buffer_index + data_length > buffer_length:
                end_index = buffer_length - buffer_index
                data_buffer[buffer_index:] = new_data[:end_index]
                data_buffer[:data_length - end_index] = new_data[end_index:]
                buffer_index = data_length - end_index
            else:
                data_buffer[buffer_index:buffer_index + data_length] = new_data
                buffer_index += data_length

        except Exception as e:
            print(f"An error occurred: {e}")
            break

# Thread to receive data
data_receiver_thread = threading.Thread(target=receive_data)
data_receiver_thread.start()

# Plotting Widget
pw = pg.plot(title="Real-time Plot")
pw.showGrid(x=True, y=True)

# Create only the curves for the defined channels in PlotChan
curves = [pw.plot(pen=pg.intColor(i, len(PlotChan))) for i in PlotChan]

def update_plot():
    latest_data = np.roll(data_buffer, -buffer_index, axis=0)
    for plot_index, channel_index in enumerate(PlotChan):
        curves[plot_index].setData((latest_data[:, channel_index]) * GainFactor + offset * plot_index)

# Start application
timer = QtCore.QTimer()
timer.timeout.connect(update_plot)
timer.start(Update_time)  # Update every x milliseconds
app = QApplication.instance() if QApplication.instance() else QApplication([])
app.exec_()

# Stop data transfer
communication = False

# Stop data transfer command
ConfString[0] = int('10000000', 2)          # First byte that stops the data transfer
ConfString[39] = CRC8(ConfString, 39)  # Estimates the new CRC
tcpSocket.sendall(bytearray(ConfString))

# Close the communication
tcpSocket.close()
