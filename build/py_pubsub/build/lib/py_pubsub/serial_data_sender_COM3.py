# sender.py
import serial
import time

ser = serial.Serial('COM3', 9600)
while True:
    ser.write(b'3.56\n')
    print("Sent: 3.56")
    time.sleep(1)