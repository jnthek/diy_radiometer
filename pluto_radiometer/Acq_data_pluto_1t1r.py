#! /bin/python3

import numpy as np
import h5py
import time
import serial
from time import sleep
import sys
import argparse
import adi

parser = argparse.ArgumentParser(description='Acquire data from three state radiometer, with Pluto backend')
parser.add_argument('-f', metavar='freq_c', help='Centre frequency (Hz)', nargs='?', default=320e6, type=float)
parser.add_argument('-s', metavar='freq_s', help='Sampling frequency (Hz)', nargs='?', default=50e6, type=float)
parser.add_argument('-g', metavar='gain',  help='SDR gain (dB)', nargs='?', default=50, type=float)
parser.add_argument("-c",  nargs='?', type=int, help='Set chunk size of samples to be collected in each acq. If unspecified, set to 4194304')
parser.add_argument('-N', metavar='NFFT', help='NFFT', nargs='?', default=4096, type=int)

args = parser.parse_args()

if (args.c) is None:
    chunk_size = 4194304 #1048576
else:
    chunk_size = int(args.c)

fc = int(args.f)
fs = int(args.s)
NFFT = int(args.N) 
gain = int(args.g)

print("Acq params")
print("fc="+str(fc/1e6)+" MHz")
print("fs="+str(fs/1e6)+" MHz")
print("NFFT="+str(NFFT))
print("Gain="+str(gain))
print("chunk_size="+str(chunk_size)+" s")
timestr = time.strftime("%Y%m%d-%H%M%S")
h5_file = str(timestr)+"_pluto_3state.h5"

ser = serial.Serial(port='/dev/ttyUSB0', baudrate=115200, timeout=.1)
sdr = adi.ad9364("ip:192.168.2.5") #Note this change based on https://github.com/analogdevicesinc/pyadi-iio/issues/521

print ("Writing to",h5_file)
hf = h5py.File(h5_file, 'w')

timestamp = time.time()
dummy_data = np.zeros(NFFT, dtype=np.float32)

data_group = hf.create_group('data')
data_group.attrs["fc"] = fc
data_group.attrs["fs"] = fs
data_group.attrs["NFFT"] = NFFT
data_group.attrs["gain"] = gain
data_group.attrs["chunk_size"] = chunk_size

data_group.create_dataset('timestamps', data=np.array([timestamp]), maxshape=(None,))
data_group.create_dataset('temperature', data=np.array([0.0]), maxshape=(None,))
data_group.create_dataset('obssource', data=np.array([-1]), maxshape=(None,))
data_group.create_dataset('radio', data=np.array([dummy_data]), maxshape=(None,None))

source_index = 0

sdr.sample_rate = int(fs)
sdr.rx_rf_bandwidth = int(fs)
sdr.rx_lo = int(fc)
sdr.rx_buffer_size = int(chunk_size)
sdr.gain_control_mode_chan0 = "manual"
sdr.rx_hardwaregain_chan0 = int(gain)
samples = sdr.rx() # Dummy rx

freq = np.linspace((fc-fs/2), fc+(fs/2), NFFT)

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

        auto11 = np.zeros(NFFT, dtype=np.float32)
        a = np.array(sdr.rx())
        Nsamp = a.shape[0]
        for j in range(int(Nsamp/NFFT)):
            c1_fft = np.fft.fft(a[j*NFFT:(j+1)*NFFT])
            auto11 = auto11 + np.abs(c1_fft)**2
        Nnorm = int(Nsamp/NFFT)
        auto11 = np.fft.fftshift(auto11/Nnorm)

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






