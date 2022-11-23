#!/usr/bin/env python
""" This script is to record the captured telmetry for a longer duration before it gets erased from the temperory FIFO file. Useful for extended duration observation anlaysis.

Usage: Record_Captured_Telemetry.py RecordTelmetryFile.pkl [StartTime]

StartTime is in the unit of day of the year. It is optional

Last updated: JPN 20221123

"""
import sys
import pickle
import time
import numpy as np
import signal

# First argument if the output filename
output_filename = sys.argv[1]

# Second argument is the optional star time.
if sys.argv[2:]:
    start_time = float(sys.argv[2])
else:
    start_time = 0


print('Recording from {0} into {1}'.format(start_time,output_filename))

#################### Function to cleanup and exit in the event of Cntrl+C interupt.
def handler(signum, frame):
    """ Gets called when an interrupt signal is received """
    print('Cntrl +C Recived. Saving file and stoping at time {0}.'.format(last_timestamp))
    with open(output_filename,'wb') as odatafile:
        pickle.dump(recorded_data_dict,odatafile)
    sys.exit(0)

signal.signal(signal.SIGINT, handler)
####################

recorded_data_dict = None

while True:
    read_data = open('/mnt/tmp_fast/T100_data_queue_dict.pkl','rb').read()
    try:
        data_queue_dict = pickle.loads(read_data)
    except EOFError:
        continue
    if recorded_data_dict is None:
        recorded_data_dict = {w_name:[] for w_name in data_queue_dict}
        last_timestamp = start_time

    # Look for new entries in the dictionary since last recording
    new_mask = (np.array(data_queue_dict['DAY'])+np.array(data_queue_dict['HH'])/24.+np.array(data_queue_dict['MM'])/(24*60.)+np.array(data_queue_dict['SEC'])/(24*60*60.)+np.array(data_queue_dict['MSEC'])/(24*60*60*10000.)) > last_timestamp
    if np.sum(new_mask) > 0: # If new data exists
        for w_name in recorded_data_dict:
            recorded_data_dict[w_name].extend(np.array(data_queue_dict[w_name])[new_mask])
        with open(output_filename,'wb') as odatafile:
            pickle.dump(recorded_data_dict,odatafile)
        print('.',end ='',flush=True)
        # Update last entry timestamp in the recorded data
        last_timestamp = recorded_data_dict['DAY'][-1]+ recorded_data_dict['HH'][-1]/24.+ recorded_data_dict['MM'][-1]/(24*60.)+ recorded_data_dict['SEC'][-1]/(24*60*60.)+ recorded_data_dict['MSEC'][-1]/(24*60*60*10000.)

    time.sleep(2) # Sleep for 2 seconds
