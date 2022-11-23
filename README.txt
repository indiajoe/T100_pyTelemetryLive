T100_pyTelemetryLive
====================

How to run them at the control room during the flight
-----------------------------------------------------

Setup/Installation
------------------
Download the latest version of scripts from this repository.

Create a RAM disk partition for fast I/O to a file.
On GNU/Linux machines you can do that by the following command

```
$ sudo mkdir /mnt/tmp_fast
$ sudo mount -t tmpfs tmpfs /mnt/tmp_fast
```

Note: Either disable the firewall or enable receiving of UDP packets at 5000


Install numpy and matplotlib in your python 3 environment.

Note: Execute all the remaining commands from the folder these scripts are extracted into.

Starting the UDP Telemetry capture
-----------------------------------

First start the telemetry capture into a FIFO buffer.
```
$ python Capture_UDP_Telemetry_live.py
```
You will start seeing time stamps and commands getting printed on screen. It shows, the UDP capture is working. 

Starting the live Word Telemetry plot
-------------------------------------
To see the live plot of some selected words in the telemetry, execute the command below

```
$ python Plot_Captured_Telemetry_live.py [/mnt/tmp_fast/Recorded_OBJECTname_data.pkl:StartTime:EndTime]
```

The second argument is optional, and can be used if you want to inspect a different recorded telemetry file. By default, while executed without any arguments, it will plot the live telemetry from the FIFO buffer file.
Start and End times are in the unit of day of the year, as printed by the first Capture_UDP_Telemetry_live.py script. They are optional.

Starting the Recording of Telemetry
-----------------------------------
The previous telemetry capture script is only writing files to a fixed size FIFO buffer file. For a more detailed analysis of a target observations, we can record the telemetry.

```
$ python Record_Captured_Telemetry.py /mnt/tmp_fast/Recorded_OBJECTname_data.pkl [StartTime]
```
StartTime is in the unit of day of the year. It is optional


Plotting the live spectrum map
------------------------------
We shall use the telemetry file into which any particular source is being observed to generate the map.

```
$ python Plot_Recorded_CII_map_live.py /mnt/tmp_fast/Recorded_OBJECTname_data.pkl[:BkgStartTime:BkgEndTime] /mnt/tmp_fast/Recorded_OBJECTname_data.pkl[:StartTime:EndTime]
```
Start and End times are in the unit of day of the year. They are optional.

The first argument is to provide the time window during which the FPS values are median combined to produce the sky background spectrum.

The second argument is the file which will be used to make live plots of the C II map.

If one wants the background to be estimated by median combing nearest data points, provide the keywords `NEAREST_BKG` as the first argument instead of the pkl file.



