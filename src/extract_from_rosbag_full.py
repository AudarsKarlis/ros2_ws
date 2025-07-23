import sqlite3
import rclpy
from sensor_msgs.msg import BatteryState
import pandas as pd
import matplotlib.pyplot as plt

# Initialize ROS (needed for message conversions)
rclpy.init()

# --------------------
# DATABASE EXTRACTION
# --------------------

# Path to .db3 file (replace with your absolute path)
db3_path = '/home/vboxuser/ros2_ws/src/rosbag2_2025_07_21-14_34_13/rosbag2_2025_07_21-14_34_13_0.db3'

# Connect to sqlite3 database
conn = sqlite3.connect(db3_path)
cursor = conn.cursor()

# Query messages from /bat_state topic
query = """
SELECT timestamp, data
FROM messages
JOIN topics ON messages.topic_id = topics.id
WHERE topics.name = '/bat_state';
"""
cursor.execute(query)
results = cursor.fetchall()

# Close database
conn.close()

# ----------------------------
# PARSING MESSAGES INTO LISTS
# ----------------------------

timestamps = []
voltages = []
currents = []
resistances = []

for row in results:
    timestamp, data = row
    msg = BatteryState()
    msg.deserialize(data)

    voltage = msg.voltage
    current = msg.current

    # Calculate resistance; avoid division by zero
    resistance = voltage / current if current != 0 else None

    timestamps.append(timestamp)
    voltages.append(voltage)
    currents.append(current)
    resistances.append(resistance)

# ----------------------------
# CREATING PANDAS DATAFRAME
# ----------------------------

df = pd.DataFrame({
    'timestamp': timestamps,
    'voltage': voltages,
    'current': currents,
    'resistance': resistances
})

# Convert timestamp from nanoseconds to seconds if needed
df['timestamp'] = df['timestamp'] * 1e-9

# ----------------------------
# PRINT SAMPLE DATA
# ----------------------------
print(df.head())

# ----------------------------
# PLOTTING USING MATPLOTLIB
# ----------------------------

plt.figure(figsize=(12, 8))

# Voltage plot
plt.subplot(3, 1, 1)
plt.plot(df['timestamp'], df['voltage'], label='Voltage (V)', color='blue')
plt.ylabel('Voltage (V)')
plt.legend()
plt.grid(True)

# Current plot
plt.subplot(3, 1, 2)
plt.plot(df['timestamp'], df['current'], label='Current (A)', color='green')
plt.ylabel('Current (A)')
plt.legend()
plt.grid(True)

# Resistance plot
plt.subplot(3, 1, 3)
plt.plot(df['timestamp'], df['resistance'], label='Internal Resistance (Ohm)', color='red')
plt.xlabel('Time (s)')
plt.ylabel('Resistance (Ohm)')
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.show()

# ----------------------------
# OPTIONAL: SAVE TO CSV
# ----------------------------

# df.to_csv('bms_extracted_data.csv', index=False)
# print("Data saved to bms_extracted_data.csv")

# Shutdown ROS
rclpy.shutdown()