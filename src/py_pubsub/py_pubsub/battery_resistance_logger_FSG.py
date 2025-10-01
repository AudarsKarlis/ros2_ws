import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
import csv
import os
import time

class BatteryLoggerSimple(Node):
    def __init__(self):
        super().__init__('battery_logger_simple')

        # Subscribe to battery state
        self.subscription = self.create_subscription(
            BatteryState,
            '/bat_state',
            self.listener_callback,
            10)

        self.start_time = None
        self.num_cells = 6

        # CSV Logging Setup
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        self.csv_filename = f"battery_logger_simple_{timestamp_str}.csv"
        self.csv_file = open(self.csv_filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # CSV Header
        header = ['Time (s)', 'Current (A)']
        header += [f'Voltage_Cell{i+1} (V)' for i in range(self.num_cells)]
        self.csv_writer.writerow(header)

    def listener_callback(self, msg):
        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if self.start_time is None:
            self.start_time = timestamp
        rel_time = timestamp - self.start_time

        cell_voltages = list(msg.cell_voltage)
        current = msg.current

        row = [rel_time, current] + cell_voltages
        self.csv_writer.writerow(row)

    def destroy_node(self):
        self.csv_file.close()
        self.get_logger().info(f"CSV log saved to {os.path.abspath(self.csv_filename)}")
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = BatteryLoggerSimple()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()