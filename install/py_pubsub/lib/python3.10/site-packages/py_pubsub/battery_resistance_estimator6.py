import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from collections import deque
import numpy as np
import threading
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import csv
import os
import time


class BatteryResistanceEstimator(Node):
    def __init__(self):
        super().__init__('battery_resistance_estimator')

        # Subscribe to battery state
        self.subscription = self.create_subscription(
            BatteryState,
            '/bat_state',
            self.listener_callback,
            10)

        self.start_time = None
        self.num_cells = 6
        self.last_cell_voltages = [None] * self.num_cells
        self.last_current = None

        # Resistance plotting data
        self.resistance_times = [[] for _ in range(self.num_cells)]
        self.resistance_values = [[] for _ in range(self.num_cells)]

        # === CSV Logging Setup ===
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        self.csv_filename = f"battery_estimator_log_{timestamp_str}.csv"
        self.csv_file = open(self.csv_filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # CSV Header
        header = ['Time (s)', 'Current (A)']
        header += [f'Voltage_Cell{i+1} (V)' for i in range(self.num_cells)]
        header += [f'Resistance_Cell{i+1} (Ohm)' for i in range(self.num_cells)]
        self.csv_writer.writerow(header)

        # === Plotting Setup ===
        self.app = pg.mkQApp("Real-time Battery Resistance")

        self.colors = ['r', 'g', 'b', 'c', 'm', 'y']
        self.windows = []
        self.plots = []
        self.curves = []

        for i in range(self.num_cells):
            win = pg.GraphicsLayoutWidget(title=f"Cell {i+1} Resistance")
            plot = win.addPlot(title=f"Cell {i+1} Resistance [Ohm]")
            plot.setLabel('left', 'Resistance', units='Ohm')
            plot.setLabel('bottom', 'Time', units='s')
            plot.showGrid(x=True, y=True)
            plot.enableAutoRange(x=True, y=True)

            curve = plot.plot(
                pen=None,
                symbol='o',
                symbolSize=8,
                symbolBrush=self.colors[i],
                symbolPen='k',
                name=f"Cell {i+1}"
            )

            self.windows.append(win)
            self.plots.append(plot)
            self.curves.append(curve)
            win.show()  # Show the individual window

        # Timer for plot updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(200)  # ms

    def listener_callback(self, msg):
        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if self.start_time is None:
            self.start_time = timestamp
        rel_time = timestamp - self.start_time

        cell_voltages = list(msg.cell_voltage)
        current = msg.current

        resistances = [float('nan')] * self.num_cells

        # Only compute if previous values exist
        if self.last_current is not None and len(cell_voltages) == self.num_cells:
            delta_i = current - self.last_current

            if abs(delta_i) > 1e-3:
                resistance_added = False
                for i in range(self.num_cells):
                    if self.last_cell_voltages[i] is not None:
                        delta_v = cell_voltages[i] - self.last_cell_voltages[i]
                        if abs(delta_v) >= 0.004:  # Only consider if ΔV ≥ 4 mV
                            resistance = abs(delta_v / delta_i)
                            self.resistance_values[i].append(resistance)
                            resistances[i] = resistance
                            resistance_added = True
                for i in range(self.num_cells):
                    if not np.isnan(resistances[i]):
                        self.resistance_times[i].append(rel_time)

                res_str = ", ".join([f"R{i+1}: {resistances[i]:.4f} Ω" for i in range(self.num_cells)])
                self.get_logger().info(f"t={rel_time:.2f}s: {res_str}")

        # Save data to CSV (including nan if resistance not computed)
        row = [rel_time, current] + cell_voltages + resistances
        self.csv_writer.writerow(row)

        # Update memory
        self.last_cell_voltages = list(cell_voltages)
        self.last_current = current

    def update_plot(self):
        if len(self.resistance_times) == 0:
            return
        for i in range(self.num_cells):
            if len(self.resistance_values[i]) > 0:
                times = np.array(self.resistance_times[i])
                values = np.array(self.resistance_values[i])
                self.curves[i].setData(
                    times,
                    values,
                    symbol='o',
                    symbolSize=8,
                    symbolBrush=self.colors[i],
                    pen=None
                )

    def start_ros_spin(self):
        spin_thread = threading.Thread(target=rclpy.spin, args=(self,), daemon=True)
        spin_thread.start()

    def destroy_node(self):
        self.csv_file.close()
        self.get_logger().info(f"CSV log saved to {os.path.abspath(self.csv_filename)}")
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = BatteryResistanceEstimator()
    node.start_ros_spin()
    try:
        node.app.exec_()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()