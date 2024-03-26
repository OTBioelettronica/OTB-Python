import socket
import struct
import numpy as np
import matplotlib.pyplot as plt


# Function to calculate CRC8
def CRC8(Vector, Len):
    crc = 0
    j = 0

    while Len > 0:
        Extract = Vector[j]
        for i in range(8, 0, -1):
            Sum = crc % 2 ^ Extract % 2
            crc //= 2

            if Sum > 0:
                str_crc = []
                a = format(crc, '08b')
                b = format(140, '08b')
                for k in range(8):
                    str_crc.append(int(a[k] != b[k]))

                crc = int(''.join(map(str, str_crc)), 2)

            Extract //= 2

        Len -= 1
        j += 1

    return crc


# Configuration parameters
TCPPort = 54320
NumCycles = 20
OffsetEMG = 1000
PlotTime = 1

# ---------- muovi 1 ------------------------------------------------------
# Set to 1 the device you want to connect to the SyncStation considering this order:
# Device from 1 to 4: MUOVI
# Device 5 and 6: Sessantaquattro/Sessantaquattro+/MUOVI+
# Device from 7 to 14: DUE+
# Device 15 and 16: Quattro+
DeviceEN = [0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

EMG = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
Mode = [0, 0, 3, 3, 0, 0, 3, 0, 3, 3, 3, 3, 3, 3, 3, 3]
NumChan = [38, 38, 38, 38, 70, 70, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8]

Error = any(DeviceEN[i] > 1 for i in range(16))
if Error:
    print("Error, set DeviceEN values equal to 0 or 1")
    exit()

Error = any(EMG[i] > 1 for i in range(16))
if Error:
    print("Error, set EMG values equal to 0 or 1")
    exit()

Error = any(Mode[i] > 3 for i in range(16))
if Error:
    print("Error, set Mode values between to 0 and 3")
    exit()

SizeComm = sum(DeviceEN)

NumEMGChanMuovi = 0
NumAUXChanMuovi = 0
NumEMGChanSessn = 0  # also used for Muovi+ because they share the same position in the Syncstation (LED 5 and 6)
NumAUXChanSessn = 0  # also used for Muovi+ because they share the same position in the Syncstation (LED 5 and 6)
NumEMGChanDuePl = 0
NumAUXChanDuePl = 0
muoviEMGChan = []
muoviAUXChan = []
sessnEMGChan = []
sessnAUXChan = []
duePlEMGChan = []
duePlAUXChan = []

sampFreq = 2000
TotNumChan = 0
TotNumByte = 0
ConfStrLen = 1
ConfString = [0] * 18

ConfString[0] = SizeComm * 2 + 1

for i in range(16):
    if DeviceEN[i] == 1:
        ConfString[ConfStrLen] = (i * 16) + EMG[i] * 8 + Mode[i] * 2 + 1

        if i < 4:
            muoviEMGChan.extend(list(range(TotNumChan + 1, TotNumChan + 33)))
            muoviAUXChan.extend(list(range(TotNumChan + 33, TotNumChan + 39)))
            NumEMGChanMuovi += 32
            NumAUXChanMuovi += 4 + 2  # Quaternions + aux
        elif i > 5:
            duePlEMGChan.extend(list(range(TotNumChan + 1, TotNumChan + 3)))
            duePlAUXChan.extend(list(range(TotNumChan + 3, TotNumChan + 9)))
            NumEMGChanDuePl += 2
            NumAUXChanDuePl += 4 + 2  # Quaternions + aux
        else:
            sessnEMGChan.extend(list(range(TotNumChan + 1, TotNumChan + 65)))
            sessnAUXChan.extend(list(range(TotNumChan + 65, TotNumChan + 71)))
            NumEMGChanSessn += 64
            NumAUXChanSessn += 4 + 2  # Quaternions + aux

        TotNumChan += NumChan[i]

        if EMG[i] == 1:
            TotNumByte += NumChan[i] * 2
        else:
            TotNumByte += NumChan[i] * 3

        if EMG[i] == 1:
            sampFreq = 2000

        ConfStrLen += 1

SyncStatChan = list(range(TotNumChan, TotNumChan + 7))
TotNumChan += 6
TotNumByte += 12

ConfString[ConfStrLen] = 0  # Placeholder for CRC8 calculation

# INITIALIZE PLOT
# Estimate how many plots have to be generated
NumHorplot = 3

NoMuoviConnected = 0
if NumEMGChanMuovi == 0:
    NumHorplot -= 1
    NoMuoviConnected = 1

NoSessanConnected = 0
if NumEMGChanSessn == 0:
    NumHorplot -= 1
    NoSessanConnected = 1

NoDuePlusConnected = 0
if NumEMGChanDuePl == 0:
    NumHorplot -= 1
    NoDuePlusConnected = 1

# Calculate CRC8 and update ConfString
ConfString[ConfStrLen] = CRC8(ConfString, ConfStrLen)
ConfStrLen += 1

# Open the TCP socket
tcpSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcpSocket.connect(('192.168.76.1', TCPPort))
print("Connected to Socket!")
# Send the configuration to syncstation
StartCommand = ConfString[0:ConfStrLen]
packed_data = struct.pack('B' * ConfStrLen, *StartCommand)

tcpSocket.sendall(packed_data)
print("Start Command sent")
print(StartCommand)

data = np.zeros((TotNumChan + 1, sampFreq * PlotTime))
blockData = TotNumByte * sampFreq * PlotTime
# Set a timeout of 10 seconds for the socket
tcpSocket.settimeout(10)

# PLOT
fig = plt.figure()
plt.xlim([0, sampFreq * PlotTime])

for i in range(NumCycles):
    plt.cla()
    print(i)

    ChanReady = 1
    ReceivedData = 0
    data_buffer = b""  # Buffer to store received data

    while len(data_buffer) < blockData:
        data_temp = tcpSocket.recv(blockData - len(data_buffer))
        if not data_temp:
            # socket closed from remote side
            break
        data_buffer += data_temp

    print("Data packet pronto: " + str(len(data_buffer)))
    TempArray = np.frombuffer(data_buffer, dtype=np.uint8)
    Temp = np.reshape(TempArray, (sampFreq * PlotTime, TotNumByte)).T

    for DevId in range(16):
        if DeviceEN[DevId] == 1:
            if EMG[DevId] == 1:
                ChInd = np.arange(0, NumChan[DevId] * 2, 2)
                DataSubMatrix = Temp[ChInd] * 256 + Temp[ChInd + 1]

                # Search for the negative values and make the two's complement
                ind = np.where(DataSubMatrix >= 32768)
                DataSubMatrix[ind] = DataSubMatrix[ind] - 65536

                # convert to mV
                DataSubMatrix[ind] = np.array(DataSubMatrix[ind]) * 0.000286

                data[ChanReady:ChanReady + NumChan[DevId], :] = DataSubMatrix
                #Remove data read
                Ch2Delete = np.arange(0, NumChan[DevId]*2, 1)
                Temp = np.delete(Temp, Ch2Delete, 0)
            else:
                ChInd = np.arange(0, NumChan[DevId] * 3, 3)
                DataSubMatrix = Temp[ChInd] * 65536 + Temp[ChInd + 1] * 256 + Temp[ChInd + 2]

                # Search for the negative values and make the two's complement
                ind = np.where(DataSubMatrix >= 8388608)
                DataSubMatrix[ind] = DataSubMatrix[ind] - 16777216

                data[ChanReady:ChanReady + NumChan[DevId], :] = DataSubMatrix
                Ch2Delete = np.arange(0, NumChan[DevId] * 3, 1)
                Temp = np.delete(Temp, Ch2Delete, 0)

            del ChInd
            del ind
            del DataSubMatrix
            ChanReady += NumChan[DevId]

    # take last remaining samples related to Syncstation 3 AUX + 1 LOAD CELL + 1 BUFFER + 1 RAMP
    ChInd = np.arange(0, 12, 2)
    DataSubMatrix = Temp[ChInd] * 256 + Temp[ChInd + 1]

    # Search for the negative values and make the two's complement
    ind = np.where(DataSubMatrix >= 32768)
    DataSubMatrix[ind] = DataSubMatrix[ind] - 65536

    data[ChanReady:ChanReady + 6, :] = DataSubMatrix
    del ind
    del DataSubMatrix

    k = 0

    if NoMuoviConnected == 0:
        k = 0
        for j in muoviEMGChan:
            plt.plot(data[j, :] + OffsetEMG * k)
            k += 1
        for j in muoviAUXChan:
            plt.plot(data[j, :])

    if NoSessanConnected == 0:
        k = 0
        for j in sessnEMGChan:
            plt.plot(data[j, :] + OffsetEMG * k)
            k += 1
        for j in sessnAUXChan:
            plt.plot(data[j, :])

    if NoDuePlusConnected == 0:
        k = 0
        for j in duePlEMGChan:
            plt.plot(data[j, :] + OffsetEMG * k)
            k += 1
        for j in duePlAUXChan:
            plt.plot(data[j, :])

    for j in SyncStatChan:
        plt.plot(data[j, :])

    plt.pause(0.01)  # Pausa to enable rendering
    plt.draw()

print("Cycle ended")
# Send the stop command to syncstation
ConfString[0] = 0
ConfString[1] = CRC8(ConfString, 1)
StopCommand = ConfString[0:2]
packed_data = struct.pack('B' * 2, *StopCommand)

print("Stop Command sent")
tcpSocket.send(packed_data)

# Close the TCP socket
tcpSocket.shutdown(2)
tcpSocket.close()
print("Socket closed")

plt.show()
