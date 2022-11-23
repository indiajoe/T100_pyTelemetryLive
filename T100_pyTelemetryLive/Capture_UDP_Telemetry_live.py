#!/usr/bin/env python
""" This script is to capture the telemetry live broadcasted via UDP in the control room 

Last updated: JPN 20221123
"""
#########################################################
# First create a fast RAM file for storing the Telmetry stream fast
# sudo mkdir /mnt/tmp_fast
# sudo mount -t tmpfs tmpfs /mnt/tmp_fast
# If firewall is loking UPD allow or disable
# sudo systemctl stop firewalld
# sudo systemctl status firewalld
#########################################################
import socket
import binascii
from collections import deque
import pickle
import sys
import signal

# Fast tmpfs file to chache FIFO data stram
data_output_filename = '/mnt/tmp_fast/T100_data_queue_dict.pkl'

def load_telemetry_word_file():
    """ Returns a dictionary of the words and the position number in a frame from the Telemetry definition file TelemetryFrameWords.txt"""
    word_dict = {}
    with open('TelemetryFrameWords.txt','r') as framewordfile:
        for line in framewordfile:
            line = line.rstrip()
            if len(line.split()) > 1:
                word_dict[' '.join(line.split()[1:])] = int(line.split()[0])
    return word_dict

# Load the word number dictionary to interpret frame data
word_dict = load_telemetry_word_file()

# Only the following selected words are extracted from the frame and saved into the FIFO file
words_to_extract = ['SYNC 0','SYNC 1','SYNC 2']+\
                   ['MAG - I','MAG - II','Coarse Elev. S. E.']+\
                   ['PDA No. {0}'.format(i+1) for i in range(8)]+\
                   ['DC PDA {0}'.format(i+1) for i in range(8)]+\
                   ['S.T. Elev. Error','S.T. Xelev. Error']+\
                   ['Fine Elev. S. E.','Fine Xelev. S. E.']+\
                   ['Time H','Time L','Command Address','Command Data','Frame Number']+\
                   ['FPC COUNTER','DET SIGNAL','FPS SCAN STATUS']+\
                   ['FPS {0} L'.format(i+1) for i in range(4)]+\
                   ['FPS {0} H'.format(i+1) for i in range(4)]


extra_frameprefix_keywords = ['DAY','HH','MM','SEC','MSEC']
#FIFO queue to stor the last N frame points
buffer_size = 1000  # Size of the FIFO queue
file_write_count = 11 # Write the FIFO file out after receiving these many number of frames

# Initialise the FIFO dictionary for all the words with 0
data_queue_dict = {}
for w in words_to_extract + extra_frameprefix_keywords:
    data_queue_dict[w] = deque(maxlen=buffer_size)


###############################  Setup socket object to capture UDP packets
UDP_IP = "0.0.0.0"
UDP_PORT = 5000

s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)  # UDP
s.bind((UDP_IP,UDP_PORT))
###############################

# Function to cleanup and exit if Cntrl+C is pressed.
data_stream_started = False
def handler(signum, frame):
    """ Gets called when an interrupt signal is received """
    print('Cntrl +C Received. Stopping.')
    if data_stream_started:
        print('Saving file and stoping at time {0}.'.format(last_time_stamp))
        with open(data_output_filename,'wb') as datafile:
            pickle.dump(data_queue_dict,datafile)
    sys.exit(0)

signal.signal(signal.SIGINT, handler)

############################################################################
print('Starting Telemetry Capture to {0}'.format(data_output_filename))
f_c = 0
while True:
    message, addr = s.recvfrom(4096)
    data_stream_started = True
    # print("Raw msg : ",message,addr)
    # print(len(message[11:]))
    for w_name in words_to_extract:
        i = word_dict[w_name] + 5  # Add 5 since the Telemetry words start there
        word = message[i*2+1+1:i*2+2+1]+message[i*2+1:i*2+1+1] # Swap the bytes to make LSM into MSB
        value = int(word.hex(),16)//2  # Shift one parity byte out by diving by 2 in decimal
        # print(w_name,value)
        data_queue_dict[w_name].append(value)
    # also save the time stamp prefix in hex format sent along with the UDP packet
    data_queue_dict['DAY'].append(int(message[4:6].hex()))
    data_queue_dict['HH'].append(int(message[6:7].hex()))
    data_queue_dict['MM'].append(int(message[7:8].hex()))
    data_queue_dict['SEC'].append(int(message[8:9].hex()))
    data_queue_dict['MSEC'].append(int(message[9:11].hex()))
    # Print if the latest command reported in telemetry changes form the one before
    if (data_queue_dict['Command Address'][-1],data_queue_dict['Command Data'][-1]) != (data_queue_dict['Command Address'][-2],data_queue_dict['Command Data'][-2]):
        print(oct(data_queue_dict['Command Address'][-1]),oct(data_queue_dict['Command Data'][-1]))
    if f_c > file_write_count: # Overwrite the FIFO file on the disk if we reached the count
        last_time_stamp = data_queue_dict['DAY'][-1] + data_queue_dict['HH'][-1]/24. +\
                          data_queue_dict['MM'][-1]/(24*60.) + data_queue_dict['SEC'][-1]/(24*60*60.) +\
                          data_queue_dict['MSEC'][-1]/(24*60*60*10000.)
        print('Time:{0} | {1}T{2}:{3}:{4}:{5} | TCounter {6} H {7} L'.format(last_time_stamp,data_queue_dict['DAY'][-1],
                                                                             data_queue_dict['HH'][-1],data_queue_dict['MM'][-1],
                                                                             data_queue_dict['SEC'][-1],data_queue_dict['MSEC'][-1],
                                                                             data_queue_dict['Time H'][-1],data_queue_dict['Time L'][-1]))
        # print('T Counter {0} ; Frame Number {1}'.format(data_queue_dict['Time H'][-1]*4096 + data_queue_dict['Time L'][-1] , data_queue_dict['Frame Number'][-1]))
        with open(data_output_filename,'wb') as datafile:
            pickle.dump(data_queue_dict,datafile)
        f_c = 0
    else:
        f_c += 1
print('End')
############################################################################
