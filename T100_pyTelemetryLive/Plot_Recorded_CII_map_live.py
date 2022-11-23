#!/usr/bin/env python
""" This script is to plot live CII map from the recorded telemetry data 

Usage: Plot_Recorded_CII_map_live.py Recorded_TelmetryFile.pkl:BkgStartTime:BkgEndTime Recorded_TelmetryFile.pkl:StartTime:EndTime

Start and End times are in the unit of day of the year. They are optional.

If one wants the background to be estimated by median combing nearest data points, provide the keywords `NEAREST_BKG` as the first argument instead of the pkl file.
Last updated: JPN 20221123

"""
import pickle
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib
from matplotlib import style
import numpy as np
from Plot_Captured_Telemetry_live import process_raw_data_dict, load_pickle_data_dict_file
from collections import defaultdict, deque
import sys

# Set the FPC scan parameters to None to esimtate automatically from the data
MAXDIFF = None #520 # 
MAXTP = None #2580 # None #
MINTP = None #1020  # None #

down_scan_offset_fpc = 580 # Adjusted by eye looking at the atmospheric line spectrum offsets
REFRESH_RATE = 100000  #  Refresh rate of plot in milliseconds # Set this to slow rate if you want to interact with the plot
WINDOW_SMOOTH = 18

USE_NEAREST_BKG = True
BKG_BUFFER_SIZE = 10
LINE_FPC_W = (1750,2500) # Window inside to sum the flux for C II 158 icron line

def average_el_Xel_FPC_FPS(data_dict,window=WINDOW_SMOOTH):
    """ Generater which returns the average of FPS values in the `window` number of frames at el and Xel values for different FPC values.
    Up/DOWN seperation logic assumes FPC values are not same for UP and DOWN scans"""

    # ALERT: For unknow reason, testing on 2018 Oct W3 data shows, the Elevation is given by 'Fine Xelev. S. E.' and Xel by 'Fine Elev. S. E.'. Reason Unknown!!!!!!
    el_array = np.array(data_dict['Fine Xelev. S. E.']) + (np.array(data_dict['S.T. Elev. Error'])-2048)*-0.02188  # 0.022 is Approximate scaling value fom SKG's code # Ignoring corss talk
    xel_array = np.array(data_dict['Fine Elev. S. E.']) + (np.array(data_dict['S.T. Xelev. Error'])-2048)*-0.02217
    for i in range(0,len(data_dict['FPC 1']),window//3): #Sample only 3 ponts inside a window 
        FPC_dict_t = defaultdict(list) # Temperory storage for averaging
        FPC_dict_UDt = defaultdict(list) # UP/DOWN mask bit
        for j in range(window):
            if i+j < len(data_dict['FPC 1']):
                for f in range(1,5):
                    FPC_dict_t[data_dict['FPC {0}'.format(f)][i+j]].append(data_dict['FPS {0} HL'.format(f)][i+j])
                    FPC_dict_UDt[data_dict['FPC {0}'.format(f)][i+j]].append(data_dict['UPSCAN {0}'.format(f)][i+j])

        FPC_dict = {}
        FPC_dict_UD = {}
        for fpc in FPC_dict_t:
            FPC_dict[fpc] = np.median(FPC_dict_t[fpc])  # Median combine for robustness
            FPC_dict_UD[fpc] = np.median(FPC_dict_UDt[fpc])

        mean_el = np.median(el_array[i:i+window])
        mean_xel = np.median(xel_array[i:i+window]) 
        # This is a python generator, hence yield
        yield mean_el, mean_xel, FPC_dict, FPC_dict_UD
        

def animate(i):
    global avg_bkg_fpc_dict
    try:
        data_queue_dict = load_pickle_data_dict_file(recorded_input_file)
    except EOFError:
        return
    if USE_NEAREST_BKG:
        bkg_dict_buffer = deque(maxlen=BKG_BUFFER_SIZE)

    # # Do data processing
    data_queue_dict = process_raw_data_dict(data_queue_dict,MaxDiff=MAXDIFF,maxtp=MAXTP,mintp=MINTP)

    el_list = []
    xel_list = []
    flux_list = []
    up_spectrum_list = []
    down_spectrum_list = []
    good_signal_spectra_up = []
    good_signal_spectra_down = []
    for mean_el, mean_xel, FPC_dict, FPC_dict_UD in average_el_Xel_FPC_FPS(data_queue_dict,window=WINDOW_SMOOTH):
        if USE_NEAREST_BKG:
            bkg_dict_buffer.append(FPC_dict)
            avg_bkg_fpc_dict = {fpc:np.median([f_dict[fpc] for f_dict in bkg_dict_buffer if fpc in f_dict.keys()]) for fpc in FPC_dict}
        try:
            up_spectrum = np.array([FPC_dict[fpc]-avg_bkg_fpc_dict[fpc] for fpc in FPC_dict if FPC_dict_UD[fpc]==1])
            down_spectrum = np.array([FPC_dict[fpc]-avg_bkg_fpc_dict[fpc] for fpc in FPC_dict if FPC_dict_UD[fpc]==0])
        except KeyError:
            # Bad data in the stream which was not present in bkg. Ignore and continue
            continue
        else:
            goodmask_up = np.abs(up_spectrum) < 200 # remove deivations larger than 200 after bkg subtraction
            goodmask_down = np.abs(down_spectrum) < 200

            up_scan_fpc = np.array([fpc for fpc in FPC_dict if FPC_dict_UD[fpc]==1])
            down_scan_fpc = np.array([fpc for fpc in FPC_dict if FPC_dict_UD[fpc]==0])

            line_mask_up = (up_scan_fpc > LINE_FPC_W[0]) & (up_scan_fpc < LINE_FPC_W[1])
            line_mask_down = (down_scan_fpc+down_scan_offset_fpc > LINE_FPC_W[0]) & (down_scan_fpc+down_scan_offset_fpc < LINE_FPC_W[1])
            # Flux is defined as the max minus median
            flux_list.append(np.mean([np.sum(spectrum[mask])-np.median(spectrum)*np.sum(mask) for spectrum,mask in [(up_spectrum,goodmask_up&line_mask_up),(down_spectrum,goodmask_down&line_mask_down)] if len(spectrum[mask]) > 1])) 

            el_list.append(mean_el)
            xel_list.append(mean_xel)


            up_spectrum_list.append((up_scan_fpc,up_spectrum))
            down_spectrum_list.append((down_scan_fpc,down_spectrum))

            if flux_list[-1] > 40:
                good_signal_spectra_up.append(up_spectrum_list[-1])
                good_signal_spectra_down.append(down_spectrum_list[-1])
    
    # xlim = ax1.get_xlim()
    fig.clear()
    ax1 = fig.add_subplot(2,1,1)
    ax1.plot(el_list,xel_list,alpha=0.1,color='k')#,norm=True)
    sp = ax1.scatter(el_list,xel_list,c=flux_list)#,norm=matplotlib.colors.LogNorm())
    ax1.set_xlabel('Fine el SE + S.T. Elev Error *0.022')
    ax1.set_ylabel('Fine Xel SE + S.T. Xelev Error * 0.022')
    fig.colorbar(sp,ax=ax1)
    # print(FPC_dict.keys(),[FPC_dict[fpc]-avg_bkg_fpc_dict[fpc] for fpc in FPC_dict],[avg_bkg_fpc_dict[fpc] for fpc in FPC_dict],[FPC_dict[fpc] for fpc in FPC_dict])
    ax2 = fig.add_subplot(2,1,2)
    # First lot the best spectrum in the bkg for reference
    for fpc,spec in good_signal_spectra_up:
        ax2.plot(fpc,spec,'o',color='k')
    for fpc,spec in good_signal_spectra_down:
        ax2.plot(fpc+down_scan_offset_fpc,spec,'s',color='k')
    # Plot the latest few spectra
    for fpc,spec in up_spectrum_list[-20::2]:
        ax2.plot(fpc,spec,'v')
    for fpc,spec in down_spectrum_list[-20::2]:
        ax2.plot(fpc+down_scan_offset_fpc,spec,'^')


    ax2.set_xlabel('FPC')
    ax2.set_ylabel('Counts')
    # ax2.set_ylim((-50,100))#ax2_ylim)
    # ax1.set_ylim(ylim)
    


if __name__ == '__main__':
    # First argument is background and second is the live target.
    bkg_input_file = sys.argv[1]
    recorded_input_file = sys.argv[2]
    
    if bkg_input_file == 'NEAREST_BKG':
        USE_NEAREST_BKG = True
    else:
        USE_NEAREST_BKG = False

    if not USE_NEAREST_BKG:
        print('Load bkg file and creating a bkg template')
        bkg_data_dict = load_pickle_data_dict_file(bkg_input_file)
        bkg_data_dict = process_raw_data_dict(bkg_data_dict,MaxDiff=MAXDIFF,maxtp=MAXTP,mintp=MINTP)
        bkg_el, bkg_xel, avg_bkg_fpc_dict, fpc_updown = next(average_el_Xel_FPC_FPS(bkg_data_dict,window=len(bkg_data_dict['FPC 1'])))
        plt.figure()
        up_scan_fpc = [fpc for fpc in avg_bkg_fpc_dict if fpc_updown[fpc]==1]
        down_scan_fpc = [fpc for fpc in avg_bkg_fpc_dict if fpc_updown[fpc]==0]
        plt.plot(up_scan_fpc,[avg_bkg_fpc_dict[fpc] for fpc in avg_bkg_fpc_dict if fpc_updown[fpc]==1],'o',label='UP')
        plt.plot(np.array(down_scan_fpc)+down_scan_offset_fpc,[avg_bkg_fpc_dict[fpc] for fpc in avg_bkg_fpc_dict if fpc_updown[fpc]==0],'o',label='DOWN')
        plt.title('Avg Background')
        plt.xlabel('FPC')
        plt.ylabel('Bkg Counts')
        plt.legend()
        plt.show(block=False)
    else:
        avg_bkg_fpc_dict = {}


    print('Starting CII map generation..')
    fig, ax1 = plt.subplots()
    # fig = plt.figure()
    # ax1 = fig.add_subplot(1,1,1)
    animate(0)
    ani = animation.FuncAnimation(fig, animate, interval=REFRESH_RATE)
    plt.show()
