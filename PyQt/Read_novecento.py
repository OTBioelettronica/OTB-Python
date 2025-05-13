import socket
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets
import math
import threading


def CRC8(Vector, Len):
    crc = 0
    j = 0

    while Len > 0:
        Extract = Vector[j]
        for i in range(8, 0, -1):
            Sum = crc % 2 ^ Extract % 2
            crc //= 2

            if Sum > 0:
                a = format(crc, '08b')
                b = format(140, '08b')
                str_list = [0] * 8

                for k in range(8):
                    str_list[k] = int(a[k] != b[k])

                crc = int(''.join(map(str, str_list)), 2)

            Extract //= 2

        Len -= 1
        j += 1

    return crc


# Configuration
PlotTime = 1
Update_time = 200
offset = 2

IN_Active = [0] * 10
Mode = [0] * 10
Gain = [0] * 10
HRES = [0] * 10
HPF = [0] * 10
Fsamp = [0] * 10
NumChan = [0] * 10
Ptr_IN = [0] * 11
Size_IN = [0] * 11

ChVsType = [0, 14, 22, 38, 46, 70, 102, 0, 0, 0, 0, 0, 0, 0, 0, 0]

# Set configuration for each input
IN_Active[0] = 1
Mode[0] = 0
Gain[0] = 0
HRES[0] = 0
HPF[0] = 1
Fsamp[0] = 1

IN_Active[1] = 1
Mode[1] = 0
Gain[1] = 0
HRES[1] = 0
HPF[1] = 1
Fsamp[1] = 1

IN_Active[2] = 1
Mode[2] = 0
Gain[2] = 0
HRES[2] = 0
HPF[2] = 1
Fsamp[2] = 1

IN_Active[3] = 0
Mode[3] = 0
Gain[3] = 0
HRES[3] = 0
HPF[3] = 1
Fsamp[3] = 1

IN_Active[4] = 0
Mode[4] = 0
Gain[4] = 0
HRES[4] = 0
HPF[4] = 1
Fsamp[4] = 1

IN_Active[5] = 0
Mode[5] = 0
Gain[5] = 0
HRES[5] = 0
HPF[5] = 1
Fsamp[5] = 1

IN_Active[6] = 0
Mode[6] = 0
Gain[6] = 0
HRES[6] = 0
HPF[6] = 1
Fsamp[6] = 1

IN_Active[7] = 0
Mode[7] = 0
Gain[7] = 0
HRES[7] = 0
HPF[7] = 1
Fsamp[7] = 1

IN_Active[8] = 0
Mode[8] = 0
Gain[8] = 0
HRES[8] = 0
HPF[8] = 1
Fsamp[8] = 0

IN_Active[9] = 0
Mode[9] = 0
Gain[9] = 0
HRES[9] = 0
HPF[9] = 1
Fsamp[9] = 0

AuxFsamp = [0, 16, 32, 48]  # Codes to set the sampling frequency for AUX Channels
FsampVal = [500, 2000, 4000, 8000]
SizeAux = [16, 64, 128, 256]
FSelAux = 0
AnOutINSource = 2
AnOutChan = 1
AnOutGain = int('00100000', 2)

TCPPort = 23456
GainFactor = 0.0002861
AuxGainFactor = 5 / 2 ** 16 / 0.5

ConfString = [0] * 15
ConfString[0] = int('10000000', 2) + AuxFsamp[FSelAux] + IN_Active[9] * 2 + IN_Active[8]
ConfString[1] = 0
for i in range(8):
    ConfString[1] += IN_Active[i] * (2 ** i)
ConfString[2] = AnOutGain + AnOutINSource
ConfString[3] = AnOutChan
for i in range(10):
    ConfString[4 + i] = Mode[i] * 64 + Gain[i] * 16 + HPF[i] * 8 + HRES[i] * 4 + Fsamp[i]
ConfString[14] = CRC8(ConfString, 14)

# Open the TCP socket
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_socket.connect(('169.254.1.10', TCPPort))
print('Connected to the Socket')

def send_request(command):
    cmd = [command, CRC8([command], 1)]
    tcp_socket.sendall(bytearray(cmd))
    response = tcp_socket.recv(20)
    return response

firmware_version = send_request(2)
print('Firmware Version:', firmware_version[1:])

battery_level = send_request(3)
print('Battery Level: {}%'.format(battery_level[1]))

settings = send_request(1)
if settings[19] == 0:
    print('Error None')
elif settings[19] == 255:
    print('Error CRC')
print('Probes configuration:', settings[1:11])

tcp_socket.sendall(bytearray(ConfString))

# Calculate the number of active channels
NumActInputs = 0
Ptr_IN[0] = 0
for i in range(10):
    NumChan[i] = ChVsType[settings[i + 1]]
    if NumChan[i] == 0:
        IN_Active[i] = 0
    if IN_Active[i] == 1:
        Size_IN[i] = (HRES[i] + 1) * FsampVal[Fsamp[i]] // 500 * NumChan[i]
        NumActInputs = NumActInputs + 1
    Ptr_IN[i + 1] = Ptr_IN[i] + Size_IN[i]

PacketSize1Block = Ptr_IN[10] + SizeAux[FSelAux] + 128
blockData = PacketSize1Block * 500 * PlotTime * 2

tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, blockData * 2)

# Initialize global Data variable
Data = None
Temp = None

# PyQt Application
app = QtWidgets.QApplication([])

# Create a main widget with a vertical layout
main_widget = QtWidgets.QWidget()
layout = QtWidgets.QVBoxLayout(main_widget)

# Create a scroll area to make the plots scrollable
scroll_area = QtWidgets.QScrollArea()
scroll_area.setWidgetResizable(True)

# Create a widget inside the scroll area
scroll_widget = QtWidgets.QWidget()
scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)

# Set the widget with the vertical layout as the main widget of the scroll area
scroll_area.setWidget(scroll_widget)

# Add the scroll area to the main layout
layout.addWidget(scroll_area)

# Increase the size of each plot by specifying the height
PLOT_HEIGHT = 400  # Height for each plot

plots = []
curves = []

# Plot IN Channels
for i in range(10):
    if IN_Active[i] == 1:
        plot_title = f"IN {i + 1} ({NumChan[i]} Chan)"
        plot = pg.PlotWidget(title=plot_title)
        plot.setFixedHeight(PLOT_HEIGHT)
        plot.showGrid(x=True, y=True)
        plots.append(plot)
        num_channels = NumChan[i]
        curves.append([plot.plot(pen=pg.intColor(j, num_channels)) for j in range(num_channels)])
        scroll_layout.addWidget(plot)

# Plot AUX Channels
plot_title = "AUX Channels"
aux_plot = pg.PlotWidget(title=plot_title)
aux_plot.setFixedHeight(PLOT_HEIGHT)
aux_plot.showGrid(x=True, y=True)
plots.append(aux_plot)
curves.append([aux_plot.plot(pen=pg.intColor(j, 16)) for j in range(16)])
scroll_layout.addWidget(aux_plot)

# Plot Accessory Channels
plot_title = "Accessory Channels"
accessory_plot = pg.PlotWidget(title=plot_title)
accessory_plot.setFixedHeight(PLOT_HEIGHT)
accessory_plot.showGrid(x=True, y=True)
plots.append(accessory_plot)
curves.append([accessory_plot.plot(pen=pg.intColor(j, 8)) for j in range(8)])
scroll_layout.addWidget(accessory_plot)

# Set the main widget to be the window and show it
main_widget.setWindowTitle('Real-time Plot')
main_widget.resize(800, 600)  # Initial size of the window
main_widget.show()

terminate_thread = threading.Event()

def receive_data():
    global Data, Temp
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, blockData * 2)
    buffer = b''
    while not terminate_thread.is_set():
        try:
            chunk = tcp_socket.recv(blockData)
            buffer += chunk
            while len(buffer) >= blockData:
                packet = buffer[:blockData]
                buffer = buffer[blockData:]
                Temp = np.frombuffer(packet, dtype='<i2')  # Little-endian
                if len(Temp) == PacketSize1Block * 500:
                    Data = Temp.reshape(PacketSize1Block, 500, order='F')
                else:
                    print(f"Unexpected packet size: {len(Temp)}")
        except (OSError, ValueError) as e:
            print(f"Error receiving data: {e}")
            break

def update_plot():
    global Data, Temp
    if Data is not None:
        current_plot = 0
        Sig_IN = [None] * 10
        for i in range(10):
            if IN_Active[i] == 1:
                Temp1 = Data[Ptr_IN[i]:Ptr_IN[i + 1], :].reshape(1, NumChan[i] * FsampVal[Fsamp[i]] * PlotTime, order='F')
                Sig_IN[i] = Temp1.reshape(NumChan[i], FsampVal[Fsamp[i]] * PlotTime, order='F').astype(np.int32)

                for ch in range(NumChan[i] - 6):
                    if ch < len(curves[current_plot]):
                        curves[current_plot][ch].setData(Sig_IN[i][ch, :] * GainFactor + offset * ch)
                current_plot += 1

        # AUX Channels
        if current_plot < len(plots):
            Temp = Data[Ptr_IN[10]:-128, :].reshape(1, 16 * FsampVal[FSelAux] * PlotTime, order='F')
            Sig_AUX = Temp.reshape(16, FsampVal[FSelAux] * PlotTime, order='F').astype(np.int32)

            for ch in range(16):
                if ch < len(curves[current_plot]):
                    curves[current_plot][ch].setData(Sig_AUX[ch, :] * AuxGainFactor + offset * (15 - ch))
            current_plot += 1

        # Accessory Channels
        if current_plot < len(plots):
            Temp = Data[-128:, :].reshape(1, 8 * 8000 * PlotTime, order='F').astype(np.int16)
            Temp1 = Temp.view(np.int32)
            Sig_Accessory = Temp1.reshape(4, 8000 * PlotTime, order='F')

            for ch in range(1):
                if ch < len(curves[current_plot]):
                    curves[current_plot][ch].setData(Sig_Accessory[ch, :])

# Thread to receive data
data_receiver_thread = threading.Thread(target=receive_data)
data_receiver_thread.start()

# Start update timer
timer = QtCore.QTimer()
timer.timeout.connect(update_plot)
timer.start(Update_time)

# Start application
if __name__ == '__main__':
    app.exec_()

# Stop data transfer
ConfString[0] = int('00000000', 2)
ConfString[14] = CRC8(ConfString, 14)
tcp_socket.sendall(bytearray(ConfString))

tcp_socket.close()
print('Socket closed')