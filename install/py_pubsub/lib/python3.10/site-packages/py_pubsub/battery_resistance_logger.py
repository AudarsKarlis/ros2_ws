import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
import csv
import os
import time

class BatteryResistanceLogger(Node):
    def __init__(self):
        super().__init__('battery_resistance_logger')

        # Prepare file
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        self.csv_filename = f"battery_cell_log_{timestamp_str}.csv"
        self.csv_file = open(self.csv_filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # CSV Header
        header = ['Time (s)', 'Current (A)']
        header += [f'Voltage_Cell{i+1} (V)' for i in range(6)]
        header += [f'Resistance_Cell{i+1} (Ohm)' for i in range(6)]
        self.csv_writer.writerow(header)

        self.subscription = self.create_subscription(
            BatteryState,
            '/bat_state',
            self.listener_callback,
            10
        )
        self.subscription  # prevent unused variable warning

        self.last_cell_voltages = None
        self.last_time = None

    def listener_callback(self, msg):
        current = msg.current
        cell_voltages = list(msg.cell_voltage)
        now = self.get_clock().now().nanoseconds * 1e-9  # seconds

        if len(cell_voltages) < 6:
            self.get_logger().warn("Less than 6 cell voltages received!")
            return

        # First callback: just store voltages
        if self.last_cell_voltages is None:
            self.last_cell_voltages = cell_voltages
            self.last_time = now
            return

        # Compute delta V for each cell
        delta_vs = [self.last_cell_voltages[i] - cell_voltages[i] for i in range(6)]

        # Avoid zero or near-zero current to prevent divide-by-zero
        if abs(current) > 0.01:
            resistances = [dv / current for dv in delta_vs]
        else:
            resistances = [float('nan')] * 6

        # Write row to CSV
        row = [now, current] + cell_voltages + resistances
        self.csv_writer.writerow(row)

        # Update memory
        self.last_cell_voltages = cell_voltages
        self.last_time = now

    def destroy_node(self):
        self.csv_file.close()
        self.get_logger().info(f"CSV log saved to {os.path.abspath(self.csv_filename)}")
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = BatteryResistanceLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()