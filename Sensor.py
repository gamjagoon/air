#!/usr/bin/python -u
# coding=utf-8
from __future__ import print_function
import serial, struct, sys, time , subprocess,json,socket, Adafruit_DHT 
DEBUG = 0
CMD_MODE = 2
CMD_QUERY_DATA = 4
CMD_DEVICE_ID = 5
CMD_SLEEP = 6
CMD_FIRMWARE = 7
CMD_WORKING_PERIOD = 8
MODE_ACTIVE = 0
MODE_QUERY = 1
PERIOD_CONTINUOUS = 0
DATAPATH = "/home/pi/IOT-Airsensor-server-web/LCD/tmp.txt"
ser = serial.Serial()
ser.port = "/dev/ttyUSB0"
ser.baudrate = 9600
sensor = Adafruit_DHT.DHT11
pin = 4

ser.open()
ser.flushInput()

byte, data = 0, ""

def dump(d, prefix=''):
    print(prefix + ' '.join(x.encode('hex') for x in d))

def construct_command(cmd, data=[]):
    assert len(data) <= 12
    data += [0,]*(12-len(data))
    checksum = (sum(data)+cmd-2)%256
    ret = "\xaa\xb4" + chr(cmd)
    ret += ''.join(chr(x) for x in data)
    ret += "\xff\xff" + chr(checksum) + "\xab"

    if DEBUG:
        dump(ret, '> ')
    return ret

def process_data(d):
    r = struct.unpack('<HHxxBB', d[2:])
    pm25 = r[0]/10.0
    pm10 = r[1]/10.0
    checksum = sum(ord(v) for v in d[2:8])%256
    return [pm25, pm10]

def process_version(d):
    r = struct.unpack('<BBBHBB', d[3:])
    checksum = sum(ord(v) for v in d[2:8])%256
    print("Y: {}, M: {}, D: {}, ID: {}, CRC={}".format(r[0], r[1], r[2], hex(r[3]), "OK" if (checksum==r[4] and r[5]==0xab) else "NOK"))

def read_response():
    byte = 0
    while byte != "\xaa":
        byte = ser.read(size=1)

    d = ser.read(size=9)

    if DEBUG:
        dump(d, '< ')
    return byte + d

def cmd_set_mode(mode=MODE_QUERY):
    ser.write(construct_command(CMD_MODE, [0x1, mode]))
    read_response()

def cmd_query_data():
    ser.write(construct_command(CMD_QUERY_DATA))
    d = read_response()
    values = []
    if d[1] == "\xc0":
        values = process_data(d)
    return values

def cmd_set_sleep(sleep):
    mode = 0 if sleep else 1
    ser.write(construct_command(CMD_SLEEP, [0x1, mode]))
    read_response()

def cmd_set_working_period(period):
    ser.write(construct_command(CMD_WORKING_PERIOD, [0x1, period]))
    read_response()

def cmd_firmware_ver():
    ser.write(construct_command(CMD_FIRMWARE))
    d = read_response()
    process_version(d)

def cmd_set_id(id):
    id_h = (id>>8) % 256
    id_l = id % 256
    ser.write(construct_command(CMD_DEVICE_ID, [0]*10+[id_l, id_h]))
    read_response()


def savedata(values,sumh,sumt):
    # pm10 pm25 hum tem time
    data = str(values[1])+" "+str(values[0])+" "+str(sumh)+" "+str(sumt)+" "+time.strftime("%Y.%m.%d %H:%M")
    F = open(DATAPATH, "w+")
    F.write(data)
    F.close()
    client_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    client_socket.connect(('algora.iptime.org',30122))
    client_socket.sendall(data.encode())
    resp = client_socket.recv(64)
    print(resp)
    client_socket.close()

if __name__ == "__main__":
    cmd_set_sleep(0)
    cmd_firmware_ver()
    cmd_set_working_period(PERIOD_CONTINUOUS)
    cmd_set_mode(MODE_QUERY);
    eval_values = [0,0];
    sumh ,sumt = 0.0,0.0
    while True:
        cmd_set_sleep(0)
        for t in range(15):
            values = cmd_query_data();
            eval_values[0] += values[0];
            eval_values[1] += values[1];
            h,t = Adafruit_DHT.read_retry(sensor, pin)
            sumh += h
            sumt += t
            if values is not None and len(values) == 2:
              time.sleep(2)
        eval_values = list(map(lambda x : round(x / 15,2) , eval_values))
        sumh = round(sumh/15,2)
        sumt = round(sumt/15,2)
        savedata(eval_values,sumh,sumt)
        cmd_set_sleep(1)
        time.sleep(30)
