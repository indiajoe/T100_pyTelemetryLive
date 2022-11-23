#!/usr/bin/env python
""" This script is to plot captured telemetry from the file 
Usage: Plot_Captured_Telemetry_live.py [RecorderdTelemetryFile.pkl:StartTime:EndTime]
If no RecorderdTelemetryFile.pkl is prvided, it will plot /mnt/tmp_fast/T100_data_queue_dict.pkl

Start and End times are in the unit of day of the year. They are optional.

Last updated: JPN 20221123
"""
import pickle
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import style
import numpy as np
import sys

REFRESH_RATE = 1000  # Refresh rate of plot in milliseconds

# If user provided a custom file, use that, otherwise use the default live telemetry pkl file
try:
    TELEMETRY_INPUT_FILE = sys.argv[1]
except IndexError:
    TELEMETRY_INPUT_FILE = '/mnt/tmp_fast/T100_data_queue_dict.pkl'

def load_pickle_data_dict_file(raw_data_dict_file):
    """ Loads pickled dictionary file inside the optional time interval defined by :Start:End suffix"""
    try:
        start_time = float(raw_data_dict_file.split(':')[1])
    except (IndexError, ValueError):
        start_time = ''
    try:
        end_time = float(raw_data_dict_file.split(':')[2])
    except (IndexError, ValueError):
        end_time = ''
    data_dict_file = raw_data_dict_file.split(':')[0]

    # Read the pickled file first and ask pickle to deserialise to python dictionay object
    read_data = open(data_dict_file,'rb').read()
    full_data_dict = pickle.loads(read_data)

    # Strip out any data which is outside the optional Start and End time.
    data_dict = strip_data_outside_timestamp(full_data_dict,start_t=start_time,end_t=end_time)

    return data_dict

def strip_data_outside_timestamp(data_dict,start_t='',end_t=''):
    """ Strips out the data before start_1 and after end_t """
    time_axis = np.array(data_dict['DAY'])+np.array(data_dict['HH'])/24.+\
                np.array(data_dict['MM'])/(24*60.)+np.array(data_dict['SEC'])/(24*60*60.)+\
                np.array(data_dict['MSEC'])/(24*60*60*10000.)
    mask = time_axis > 0 # Initialise mask for all positive time data
    if start_t is not '':
        mask[time_axis<start_t] = False
    if end_t is not '':
        mask[time_axis>end_t] = False
    new_dict = {}
    for w_name in data_dict:
        new_dict[w_name] = np.array(data_dict[w_name])[mask]
    return new_dict


def process_raw_data_dict(data_queue_dict,MaxDiff=None,maxtp=None,mintp=None):
    """ This function does all the processing of the raw data dict frames for display"""
    # Combine the H and L Time counter in telmetry to a new keyword Time HL
    data_queue_dict['Time HL'] = np.array(data_queue_dict['Time H'])*4096 + np.array(data_queue_dict['Time L'])
    # Calculate 16bit FPS values by combining the H and L words after shifting to right by 4 bits (divide by 16)
    for i in range(4):
        data_queue_dict['FPS {0} HL'.format(i+1)] = np.array(data_queue_dict['FPS {0} H'.format(i+1)])*256//16 + np.array(data_queue_dict['FPS {0} L'.format(i+1)])//16 

    # Extract the Up/DOWN scan bit from the FPS SCAN STATUS word and save it to 'FPC Up/Down'
    data_queue_dict['FPC Up/Down'] = np.array([int(format(sbit,'b')[-3]) if (len(format(sbit,'b')) > 3) else 0 for sbit in data_queue_dict['FPS SCAN STATUS']])

    # Calculate FPC values for the 4 FPS values inside each frame
    data_queue_dict = interpolate_FPC_values(data_queue_dict,
                                             MaxDiff=MaxDiff,maxtp=maxtp,mintp=mintp)

    return data_queue_dict

def interpolate_FPC_values(data_queue_dict,MaxDiff=None,maxtp=None,mintp=None):
    """
    Returns the Data dict after interpolating the 4 FPC values in each frame (FPC1,FPC2,FPC3,FPC4), 
    based on the measured 'FPC COUNTER', which corresponds to FPS3 readout.
    Assumption is that, the FPC is sampled from a neat triangular waveform.
    If turning points (maxtp and mintp) are not inputed. It will try to estimate the turning points.
    But, this needs atleast two points of the measured FPC to be on same ramp of triangle.
    """

    FPC3_array = np.array(data_queue_dict['FPC COUNTER'])

    # If turning points maxtp and mintp are not provided, we shall estimate them from data.
    if MaxDiff is None: # This is almost always 520 in fast scan
        # We take the most frequent difference between the point sas the actuall difference between rows
        MaxDiff = np.argmax(np.bincount(np.abs(np.diff(FPC3_array))))
        #----
        # The command below is slower, but will work for non-integer FPC values also. If ever needed!!
        # from scipy.stats import mode  # Add this in begining of code.
        # MaxDiff = mode(np.abs(DataT['rawTele_FPC'][1:]-DataT['rawTele_FPC'][:-1]))[0][0]
        #----
    if (maxtp is None) or (mintp is None):
        # The max turning point can be calculated as (sum of the top most points + Distance between them )/ 2
        maxtp = np.max((FPC3_array[1:]+FPC3_array[:-1] +MaxDiff)/2)
        # Similarly, min is the (sum of the bottom most points - Distance between them )/ 2
        mintp = np.min((FPC3_array[1:]+FPC3_array[:-1] -MaxDiff)/2)

        print('Estimated FPC Triangle Waveform.')
        print('SampleGap= {0}, MaxTurningPoint= {1}, MinTurningPoint= {2}'.format(MaxDiff,maxtp,mintp))


    down_mask = data_queue_dict['FPC Up/Down'] == 0

    # Initialise the new FPC arrays
    FPC1_array = np.zeros(len(data_queue_dict))
    FPC2_array = np.zeros(len(data_queue_dict))
    FPC4_array = np.zeros(len(data_queue_dict))

    # First calculate for up scan # will result in garbage values in down scan
    FPC1_array = FPC3_array - MaxDiff*2/4.
    FPC1_array[FPC1_array < mintp] = 2*mintp - FPC1_array[FPC1_array < mintp]
    FPC2_array = FPC3_array - MaxDiff/4.
    FPC2_array[FPC2_array < mintp] = 2*mintp - FPC2_array[FPC2_array < mintp]
    FPC4_array = FPC3_array + MaxDiff/4.
    FPC4_array[FPC4_array > maxtp] = 2*maxtp - FPC4_array[FPC4_array > maxtp]
    # Now calculate for the down scan and update the down scan values
    FPC1_array[down_mask] = FPC3_array[down_mask] + MaxDiff*2/4.
    FPC1_array[down_mask & (FPC1_array > maxtp)] = 2*maxtp - FPC1_array[down_mask & (FPC1_array > maxtp)]
    FPC2_array[down_mask] = FPC3_array[down_mask] + MaxDiff/4.
    FPC2_array[down_mask & (FPC2_array > maxtp)] = 2*maxtp - FPC2_array[down_mask & (FPC2_array > maxtp)]
    FPC4_array[down_mask] = FPC3_array[down_mask] - MaxDiff/4.
    FPC4_array[down_mask & (FPC4_array < mintp)] = 2*mintp - FPC4_array[down_mask & (FPC4_array < mintp)]


    #######################################
    #Same as above,but slow. Kept here since this is more easier to understand the logic of the above steps.
    #######################################
    # for i,row in enumerate(DataT):
    #     fpc3 = row['FPC COUNTER']

    #     if int(row['FPC Up/Down']) == 1:  # Scan waveform is going UP
    #         # Now we should fold the values into the triangular wave if they overshoot turning points
    #         fpc1 = fpc3 - MaxDiff*2/4. if (fpc3 - MaxDiff*2/4.) > mintp else 2*mintp - (fpc3 - MaxDiff*2/4.)
    #         fpc2 = fpc3 - MaxDiff/4. if (fpc3 - MaxDiff/4.) > mintp else 2*mintp - (fpc3 - MaxDiff/4.)
    #         fpc4 = fpc3 + MaxDiff/4. if (fpc3 + MaxDiff/4.) < maxtp else 2*maxtp - (fpc3 + MaxDiff/4.)
            
    #     else: # Scan waveform is going DOWN
    #         fpc1 = fpc3 + MaxDiff*2/4. if (fpc3 + MaxDiff*2/4.) < maxtp else 2*maxtp - (fpc3 + MaxDiff*2/4.)
    #         fpc2 = fpc3 + MaxDiff/4. if (fpc3 + MaxDiff/4.) < maxtp else 2*maxtp - (fpc3 + MaxDiff/4.)
    #         fpc4 = fpc3 - MaxDiff/4. if (fpc3 - MaxDiff/4.) > mintp else 2*mintp - (fpc3 - MaxDiff/4.)

    #     # Update the table
    #     DataT['FPC1'][i] = fpc1
    #     DataT['FPC2'][i] = fpc2
    #     DataT['FPC3'][i] = fpc3
    #     DataT['FPC4'][i] = fpc4
    #######################################

    data_queue_dict['FPC 1'] = FPC1_array
    data_queue_dict['FPC 2'] = FPC2_array
    data_queue_dict['FPC 3'] = FPC3_array
    data_queue_dict['FPC 4'] = FPC4_array

    # Also add UPSCAN X arrays to identify up and down scans
    all_FPC_combined = np.dstack([FPC1_array,FPC2_array,FPC3_array,FPC4_array]).flatten()
    all_FPC_combined_upmask = np.gradient(all_FPC_combined) > 0
    all_FPC_combined_upmask_reshaped = all_FPC_combined_upmask.reshape(len(FPC1_array),4)

    # 1 is UP and 0 is DOWN as usuall
    data_queue_dict['UPSCAN 1'] = all_FPC_combined_upmask_reshaped[:,0].astype(int)
    data_queue_dict['UPSCAN 2'] = all_FPC_combined_upmask_reshaped[:,1].astype(int)
    data_queue_dict['UPSCAN 3'] = all_FPC_combined_upmask_reshaped[:,2].astype(int)
    data_queue_dict['UPSCAN 4'] = all_FPC_combined_upmask_reshaped[:,3].astype(int)

    return data_queue_dict


def animate(i):
    try:
        data_queue_dict = load_pickle_data_dict_file(TELEMETRY_INPUT_FILE)
    except EOFError:
        return  # Will update the plot in next refresh.
    # Do data processing
    data_queue_dict = process_raw_data_dict(data_queue_dict)

    time_axis = np.array(data_queue_dict['DAY'])+np.array(data_queue_dict['HH'])/24.+\
                np.array(data_queue_dict['MM'])/(24*60.)+np.array(data_queue_dict['SEC'])/(24*60*60.)+\
                np.array(data_queue_dict['MSEC'])/(24*60*60*10000.)
    ylim = ax1.get_ylim() # Get the previous y axis limits before clearing
    ax1.clear()
    m = time_axis > 0 # remove data with zero timestamp from plots
    for w_name in words_to_extract:
        ax1.plot(time_axis[m],np.array(data_queue_dict[w_name])[m],marker='.',label=w_name,alpha=.4)
    ax1.set_ylim(ylim)
    ax1.legend()
    ax1.set_title('FPS STATUS:{0} | Command :{1} {2}'.format(format(data_queue_dict['FPS SCAN STATUS'][-1],'b')[-4:],
                                                             oct(data_queue_dict['Command Address'][-1]),
                                                             oct(data_queue_dict['Command Data'][-1])))

if __name__ == '__main__':
    # Start plotting
    fig = plt.figure()
    ax1 = fig.add_subplot(1,1,1)
    ax1.set_ylim((0,4096))
    # Words to plot
    words_to_extract = ['SYNC 0','SYNC 1','SYNC 2']+\
                       ['S.T. Elev. Error','S.T. Xelev. Error']+\
                       ['Fine Elev. S. E.','Fine Xelev. S. E.']+\
                       ['Frame Number']+\
                       ['FPC COUNTER','DET SIGNAL','FPS SCAN STATUS']+\
                       ['MAG - I','MAG - II','Coarse Elev. S. E.']+\
                       ['Time H','Time L']#+\
                       # ['PDA No. {0}'.format(i+1) for i in range(8)]+\
                       #                   ['FPS {0} L'.format(i+1) for i in range(4)]+\ 
    #                   ['FPS {0} H'.format(i+1) for i in range(4)]
    animate(0) # Plot once before startig the animation
    ani = animation.FuncAnimation(fig, animate, interval=REFRESH_RATE)
    plt.show()
