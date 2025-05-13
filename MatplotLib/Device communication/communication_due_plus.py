#!python3
# -------------------------------------------------------
# Module to connect to Due+ signal data logger
#
import datetime
import multiprocessing
import socket  # We will need this for establishing the communication with Due+
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation

CONVERSION_FACTOR = 0.000249  # Conversion factor needed to get values in mV


# Convert integer to bytes
def integer_to_bytes(command):
    return int(command).to_bytes(1, byteorder="big")


# Convert byte-array value to an integer value and apply two's complement
def convert_bytes_to_int(bytes_value, bytes_in_sample):
    value = None
    if bytes_in_sample == 2:
        # Combine 2 bytes to a 16 bit integer value
        value = \
            bytes_value[0] * 256 + \
            bytes_value[1]
        # See if the value is negative and make the two's complement
        if value >= 32768:
            value -= 65536
    elif bytes_in_sample == 3:
        # Combine 3 bytes to a 24 bit integer value
        value = \
            bytes_value[0] * 65536 + \
            bytes_value[1] * 256 + \
            bytes_value[2]
        # See if the value is negative and make the two's complement
        if value >= 8388608:
            value -= 16777216
    else:
        raise Exception(
            "Unknown bytes_in_sample value. Got: {}, "
            "but expecting 2 or 3".format(bytes_in_sample))
    return value


# Create the binary command which is sent to Due+
# to start or stop the communication with wanted data logging setup
def create_bin_command(start=1):
    
    # Refer to the communication protocol for details about these variables:
    ProbeEN = 1    # 1 = Probe enabled, 0 = Probe disabled
    EMG = 1        # 1 = EMG
    Mode = 0       # 0 = 2Ch Bipolar
    
    # Number of acquired channel
    NumChan = 8

    number_of_channels = None
    sample_frequency = None
    bytes_in_sample = None

    # Create the command to send to Due+
    command = 0
    if ProbeEN == 1:
        command = 0 + EMG * 8 + Mode * 2 + 1
        number_of_channels = NumChan
        sample_frequency = 2000; 
        bytes_in_sample = 2

    if (
            not number_of_channels or
            not sample_frequency or
            not bytes_in_sample):
        raise Exception(
            "Could not set number_of_channels "
            "and/or and/or bytes_in_sample")

    return (integer_to_bytes(command),
            number_of_channels,
            sample_frequency,
            bytes_in_sample)


# Convert channels from bytes to integers
def bytes_to_integers(
        sample_from_channels_as_bytes,
        number_of_channels,
        bytes_in_sample,
        output_milli_volts):
    channel_values = []
    # Separate channels from byte-string. One channel has
    # "bytes_in_sample" many bytes in it.
    for channel_index in range(number_of_channels):
        channel_start = channel_index * bytes_in_sample
        channel_end = (channel_index + 1) * bytes_in_sample 
        channel = sample_from_channels_as_bytes[channel_start:channel_end]

        # Convert channel's byte value to integer
        value = convert_bytes_to_int(channel, bytes_in_sample)

        # Convert bio measurement channels to milli volts if needed
        # The 4 last channels (Auxiliary and Accessory-channels)
        # are not to be converted to milli volts
        if output_milli_volts and channel_index < (number_of_channels - 6):
            value *= CONVERSION_FACTOR
        channel_values.append(value)
    return channel_values


#     Read raw byte stream from data logger. Read one sample from each
#     channel. Each channel has 'bytes_in_sample' many bytes in it.
def read_raw_bytes(connection, number_of_all_channels, bytes_in_sample):
    buffer_size = number_of_all_channels * bytes_in_sample
    new_bytes = connection.recv(buffer_size)
    return new_bytes


# Connect to Due+'s TCP socket and send start command
def connect_to_sq(
        sq_socket,
        ip_address,
        port,
        start_command):
    sq_socket.bind((ip_address, port))
    sq_socket.listen(1)
    print('Waiting for connection...')
    conn, addr = sq_socket.accept()
    print('Connection from address: {0}'.format((addr)))
    conn.send(start_command)
    return conn


# Disconnect from Due+ by sending a stop command
def disconnect_from_sq(conn):
    if conn is not None:
        (stop_command,
         _,
         __,
         ___) = create_bin_command(start=0)
        conn.send(stop_command)
        conn.shutdown(2)
        conn.close()
    else:
        raise Exception(
            "Can't disconnect because the"
            "connection is not established")