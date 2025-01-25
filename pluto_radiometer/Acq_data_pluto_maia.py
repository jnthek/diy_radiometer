#!/usr/bin/env python3

import numpy as np
import h5py
import serial
from time import sleep
import sys
import argparse
import requests
from websockets.sync.client import connect
import time

def error_check(res):
    if res.status_code != 200:
        print(res.text)
        sys.exit(1)

parser = argparse.ArgumentParser(description='Acquire data from three state radiometer, with Pluto backend')
parser.add_argument('-f', metavar='freq_c', help='Centre frequency (Hz)', nargs='?', default=320e6, type=float)
parser.add_argument('-s', metavar='freq_s', help='Sampling frequency (Hz)', nargs='?', default=50e6, type=float)
parser.add_argument('-g', metavar='gain',  help='SDR gain (dB)', nargs='?', default=40, type=float)
parser.add_argument('-t', metavar='t_int', help='Integration time (s)', nargs='?', default=1, type=int)

args = parser.parse_args()

fc = int(args.f)
fs = int(args.s)
gain = int(args.g)
t_int = int(args.t)
spectrum_rate = 60 #Fixed
integrations = int(t_int * spectrum_rate)

print("Acq params")
print("fc="+str(fc/1e6)+" MHz")
print("fs="+str(fs/1e6)+" MHz")
print("Gain="+str(gain))
print("t_int="+str(t_int)+" s")

timestr = time.strftime("%Y%m%d-%H%M%S")
h5_file = str(timestr)+"_pluto_3state.h5"

ser = serial.Serial(port='/dev/ttyUSB0', baudrate=115200, timeout=.1)
maiasdr_url = "http://192.168.2.5:8000"

response = requests.patch(maiasdr_url + '/api/ad9361', json={
        'sampling_frequency': fs,
        'rx_rf_bandwidth': fs,
        'rx_lo_frequency': fc,
        'rx_gain': gain,
        'rx_gain_mode': 'Manual',})
error_check(response)

response = requests.patch(maiasdr_url + '/api/spectrometer',json={'output_sampling_frequency': spectrum_rate,})
error_check(response)

ws_url = 'ws:' + ':'.join(maiasdr_url.split(':')[1:]) + '/waterfall'

print ("Writing to",h5_file)
hf = h5py.File(h5_file, 'w')

timestamp = time.time()
dummy_data = np.zeros(4096, dtype=np.float32)

data_group = hf.create_group('data')
data_group.attrs["fc"] = fc
data_group.attrs["fs"] = fs
data_group.attrs["NFFT"] = 4096
data_group.attrs["gain"] = gain
data_group.attrs["t_int"] = t_int

data_group.create_dataset('timestamps', data=np.array([timestamp]), maxshape=(None,))
data_group.create_dataset('temperature', data=np.array([0.0]), maxshape=(None,))
data_group.create_dataset('obssource', data=np.array([-1]), maxshape=(None,))
data_group.create_dataset('radio', data=np.array([dummy_data]), maxshape=(None,None))

source_index = 0

freq = np.linspace((fc-fs/2), fc+(fs/2), 4096)

for dv in range(10):
    ser.write(bytes("A", 'ascii'))
    sleep(1)
    temperature = ser.readline().decode('ascii').strip()
    print (temperature)

while True:
    try:
        if source_index == 0:
            ser.write(bytes("A", 'ascii'))
            print ("Antenna")
        elif source_index == 1:
            ser.write(bytes("C", 'ascii'))
            print ("Cold")
        elif source_index == 2:
            ser.write(bytes("H", 'ascii'))
            print ("Hot")
        else:
            print ("Wrong count ?")

        sleep(1)

        len_old_data = data_group['timestamps'].shape[0]

        hf['data/obssource'].resize((len_old_data + 1), axis=0)
        hf['data/obssource'][-1] = source_index

        hf['data/timestamps'].resize((len_old_data + 1), axis=0)
        hf['data/timestamps'][-1] = time.time()

        with connect(ws_url) as ws:
            specs = np.zeros([integrations, 4096])
            for i in range(integrations):
                specs[i, :] = np.frombuffer(ws.recv(), 'float32')
            auto11 = np.average(specs, axis=0)

        try:
            temperature = float(ser.readline().decode('ascii').strip())
            print (temperature)
        except:
            print("An exception occurred, setting temperature to a large number") 
            temperature = 1e9

        hf['data/temperature'].resize((len_old_data + 1), axis=0)
        hf['data/temperature'][-1] = float(temperature)

        hf['data/radio'].resize((len_old_data + 1), axis=0)
        hf['data/radio'][-1:] = np.array(auto11)

        source_index = int((source_index+1)%3)
        del (auto11)

    except KeyboardInterrupt:
        print ("Exiting gracefully !")
        ser.write(bytes("A", 'ascii'))
        hf.close()
        ser.close() 
        sys.exit()






