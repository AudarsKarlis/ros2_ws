#!/usr/bin/env python3

import rclpy
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from sensor_msgs.msg import BatteryState
import rclpy.serialization
import pandas as pd
import matplotlib.pyplot as plt

# Initialize ROS2
rclpy.init()

# === CONFIGURATION ===
bag_path = '/home/vboxuser/ros2_ws/src/rosbag2_2025_07_21-14_34_13'

# Setup rosbag2 reader
storage_options = StorageOptions(uri=bag_path, storage_id='sqlite3')
converter_options = ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr')

reader = SequentialReader()
reader.open(storage_options, converter_options)

# Get topic types for deserialization
topic_types = reader.get_all_topics_and_types()
type_map = {t.name: t.type for t in topic_types}

# Prepare data storage
timestamps = []
voltages = []
currents = []
resistances = []

# === READ MESSAGES ===
while reader.has_next():
    (topic, data, t) = reader.read_next()

    if topic == '/bat_state':
        msg = rclpy.serialization.deserialize_message(data, BatteryState)
        
        voltage = msg.voltage
        current = msg.current

        if current != 0:
            resistance = voltage / current
        else:
            resistance = None

        # Append to lists
        timestamps.append(t * 1e-9)  # Convert from ns to s
        voltages.append(voltage)
        currents.append(current)
        resistances.append(resistance)

# === CREATE PANDAS DATAFRAME ===
df = pd.DataFrame({
    'time_s': timestamps,
    'voltage_V': voltages,
    'current_A': currents,
    'resistance_Ohm': resistances
})

# === Convert UNIX timestamps to relative time (t=0s at start) ===
time_zero = df['time_s'].iloc[0]
df['time_s'] = df['time_s'] - time_zero

# === SAVE TO CSV FOR FUTURE ANALYSIS ===
df.to_csv('battery_internal_resistance.csv', index=False)
print("✅ Data saved to 'battery_internal_resistance.csv'")

# === PLOT RESULTS ===
plt.figure(figsize=(12, 6))

plt.subplot(2,1,1)
plt.plot(df['time_s'].to_numpy(), df['voltage_V'].to_numpy(), label='Voltage [V]')
plt.plot(df['time_s'].to_numpy(), df['current_A'].to_numpy(), label='Current [A]')
plt.legend()
plt.title('Battery Voltage and Current vs Time')
plt.xlabel('Time [s]')
plt.ylabel('Value')

plt.subplot(2,1,2)
plt.plot(df['time_s'].to_numpy(), df['resistance_Ohm'].to_numpy(), label='Internal Resistance [Ohm]', color='orange')
plt.legend()
plt.xlabel('Time [s]')
plt.ylabel('Resistance [Ohm]')
plt.title('Estimated Internal Resistance vs Time')

plt.tight_layout()
plt.show()