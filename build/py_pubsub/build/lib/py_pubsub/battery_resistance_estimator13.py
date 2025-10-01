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

        # For live plotting: one list per cell
        self.rint_times = [[] for _ in range(self.num_cells)]
        self.rint_values = [[] for _ in range(self.num_cells)]
        self.rint_queue = queue.Queue()  # Thread-safe queue

        # CSV Logging Setup
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        self.csv_filename = f"battery_logger_first6_{timestamp_str}.csv"
        self.csv_file = open(self.csv_filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # CSV Header as requested
        header = ['Time (s)', 'Current (A)', 'abs(delta_I)']
        header += [f'Voltage_Cell{i+1} (V)' for i in range(self.num_cells)]
        header += [f'abs(delta_U_Cell{i+1})' for i in range(self.num_cells)]
        header += [f'R_int_Cell{i+1}' for i in range(self.num_cells)]
        self.csv_writer.writerow(header)

        # Setup live plot: 2 rows x 3 columns of subplots
        self.app = pg.mkQApp("R_int Live Plot")
        self.win = pg.GraphicsLayoutWidget(show=True, title="Internal Resistance Live Plots")
        self.plots = []
        self.curves = []
        plot_titles = [f"R_int_Cell{i+1}" for i in range(self.num_cells)]
        for i in range(2):  # 2 rows
            for j in range(3):  # 3 columns
                p = self.win.addPlot(row=i, col=j, title=plot_titles[i*3 + j])
                p.setLabel('left', 'R_int', units='Ohm')
                p.setLabel('bottom', 'Time', units='s')
                p.showGrid(x=True, y=True, alpha=0.5)  # Enable grid for easier reading
                curve = p.plot(pen='y', symbol='o', symbolBrush='y')
                self.plots.append(p)
                self.curves.append(curve)

        # Timer refresh for curves
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(200)

    def listener_callback(self, msg):
        """Called in ROS 2 thread → compute R_int and push to queue"""
        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if self.start_time is None:
            self.start_time = timestamp
        rel_time = timestamp - self.start_time

        cell_voltages = list(msg.cell_voltage)[:self.num_cells]
        current = msg.current

        abs_delta_I = float('nan')
        delta_I = float('nan')
        abs_delta_U_cells = [float('nan')] * self.num_cells
        delta_U_cells = [float('nan')] * self.num_cells
        R_int_cells = [float('nan')] * self.num_cells

        if self.last_current is not None and self.last_cell_voltages is not None:
            delta_I = current - self.last_current
            abs_delta_I = abs(delta_I)
            delta_U_cells = [cell_voltages[i] - self.last_cell_voltages[i] for i in range(self.num_cells)]
            abs_delta_U_cells = [abs(du) for du in delta_U_cells]

            if abs_delta_I >= 10:
                for i in range(self.num_cells):
                    # Use abs(delta_U) / abs(delta_I) for R_int as requested
                    if abs_delta_I != 0:
                        R_int_cells[i] = abs_delta_U_cells[i] / abs_delta_I
                        # Push data for this cell to queue for plotting
                        self.rint_queue.put((i, rel_time, R_int_cells[i]))
                    else:
                        R_int_cells[i] = float('nan')
            else:
                # If delta_I is not large enough, keep all as nan
                abs_delta_I = float('nan')
                abs_delta_U_cells = [float('nan')] * self.num_cells
                R_int_cells = [float('nan')] * self.num_cells

        row = [rel_time, current, abs_delta_I] + cell_voltages + abs_delta_U_cells + R_int_cells
        self.csv_writer.writerow(row)

        self.last_current = current
        self.last_cell_voltages = cell_voltages

    def update_plot(self):
        """Run in Qt thread → safely read from queue and update plot"""
        while not self.rint_queue.empty():
            cell_idx, t, rint = self.rint_queue.get()
            self.rint_times[cell_idx].append(t)
            self.rint_values[cell_idx].append(rint)

        for i in range(self.num_cells):
            if self.rint_times[i] and self.rint_values[i]:
                self.curves[i].setData(self.rint_times[i], self.rint_values[i])

    def destroy_node(self):
        self.csv_file.close()
        self.get_logger().info(f"CSV log saved to {os.path.abspath(self.csv_filename)}")
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = BatteryLoggerFirst6()

    # Run ROS 2 executor in a background thread
    executor = MultiThreadedExecutor()
    executor.add_node(node)
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