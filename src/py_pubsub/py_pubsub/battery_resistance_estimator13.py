import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import BatteryState
import numpy as np
import threading
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore
import csv
import os
import time
import queue


class BatteryLoggerFirst6(Node):
    def __init__(self):
        super().__init__('battery_logger_first6')

        self.subscription = self.create_subscription(
            BatteryState,
            '/bat_state',
            self.listener_callback,
            10)

        self.start_time = None
        self.num_cells = 6  # Only log first 6 cells
        self.last_current = None
        self.last_cell_voltages = None

        # For live plotting
        self.rint_times = []
        self.rint_values = []
        self.rint_queue = queue.Queue()  # Thread-safe queue

        # CSV Logging Setup
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        self.csv_filename = f"battery_logger_first6_{timestamp_str}.csv"
        self.csv_file = open(self.csv_filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # CSV Header
        header = ['Time (s)', 'Current (A)']
        header += [f'Voltage_Cell{i+1} (V)' for i in range(self.num_cells)]
        header += ['abs(delta_I)', 'abs(delta_U)', 'R_int']
        self.csv_writer.writerow(header)

        # Setup live plot
        self.app = pg.mkQApp("R_int Live Plot")
        self.win = pg.GraphicsLayoutWidget(show=True, title="Internal Resistance Live Plot")
        self.plot = self.win.addPlot(title="Internal Resistance vs Time")
        self.plot.setLabel('left', 'R_int', units='Ohm')
        self.plot.setLabel('bottom', 'Time', units='s')
        self.curve = self.plot.plot(pen='y', symbol='o', symbolBrush='y')

        # Timer refresh for curve
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(200)

    def listener_callback(self, msg):
        """Called in ROS 2 thread → compute R_int and push to queue"""
        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if self.start_time is None:
            self.start_time = timestamp
        rel_time = timestamp - self.start_time

        # Only log first 6 cell voltages
        cell_voltages = list(msg.cell_voltage)[:self.num_cells]
        current = msg.current

        abs_delta_I = float('nan')
        abs_delta_U = float('nan')
        R_int = float('nan')
        if self.last_current is not None and self.last_cell_voltages is not None:
            delta_I = current - self.last_current
            delta_U = np.mean([cell_voltages[i] - self.last_cell_voltages[i] for i in range(self.num_cells)])
            if abs(delta_I) >= 10:
                abs_delta_I = abs(delta_I)
                abs_delta_U = abs(delta_U)
                if abs_delta_I > 0:
                    R_int = abs_delta_U / abs_delta_I
                    # Push data to queue instead of touching GUI directly
                    self.rint_queue.put((rel_time, R_int))

        row = [rel_time, current] + cell_voltages + [abs_delta_I, abs_delta_U, R_int]
        self.csv_writer.writerow(row)

        self.last_current = current
        self.last_cell_voltages = cell_voltages

    def update_plot(self):
        """Run in Qt thread → safely read from queue and update plot"""
        while not self.rint_queue.empty():
            t, rint = self.rint_queue.get()
            self.rint_times.append(t)
            self.rint_values.append(rint)

        if self.rint_times and self.rint_values:
            self.curve.setData(self.rint_times, self.rint_values)

    def destroy_node(self):
        self.csv_file.close()
        self.get_logger().info(f"CSV log saved to {os.path.abspath(self.csv_filename)}")
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = BatteryLoggerFirst6()

    # Run ROS 2 executor in a background thread
    executor = MultiThreadedExecutor()
    executor.add_node(node)   # <-- important!
    ros_thread = threading.Thread(target=executor.spin)
    ros_thread.start()

    try:
        # Start Qt event loop in main thread
        pg.exec()
    finally:
        node.destroy_node()
        rclpy.shutdown()
        ros_thread.join()


if __name__ == '__main__':
    main()