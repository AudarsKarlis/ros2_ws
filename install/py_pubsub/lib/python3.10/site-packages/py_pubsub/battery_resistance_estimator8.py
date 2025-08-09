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
        header += [f'MovingAvg_Cell{i+1} (Ohm)' for i in range(self.num_cells)]
        self.csv_writer.writerow(header)

        # === Plotting Setup ===
        self.app = pg.mkQApp("Real-time Battery Resistance")
        self.win = pg.GraphicsLayoutWidget(show=True, title="Battery Internal Resistance Estimation")
        self.moving_avg_window = 2  # Use last 2 resistance values
        self.avg_markers = []       # One per cell

        self.colors = ['r', 'g', 'b', 'c', 'm', 'y']
        self.plots = []
        self.curves = []

        self.upper_curves = []
        self.lower_curves = []

        # Arrange 2 rows × 3 columns
        for i in range(self.num_cells):
            if i > 0 and i % 3 == 0:
                self.win.nextRow()
            plot = self.win.addPlot(title=f"Cell {i+1} Resistance [Ohm]")
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

            avg_marker = plot.plot(
                pen=None,
                symbol='s',  # square marker
                symbolSize=12,
                symbolBrush='w',
                symbolPen=pg.mkPen('k', width=2),
                name=f"Avg {i+1}"
            )

            # Create curves for confidence interval boundaries
            upper = plot.plot(pen=pg.mkPen(self.colors[i], style=QtCore.Qt.DashLine, width=1))
            lower = plot.plot(pen=pg.mkPen(self.colors[i], style=QtCore.Qt.DashLine, width=1))
            self.upper_curves.append(upper)
            self.lower_curves.append(lower)

            self.plots.append(plot)
            self.curves.append(curve)
            self.avg_markers.append(avg_marker)

        self.win.show()

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

            if abs(delta_i) >= 0.1: #Only consider if ΔA ≥ 100 mA
                resistance_added = False
                for i in range(self.num_cells):
                    if self.last_cell_voltages[i] is not None:
                        delta_v = cell_voltages[i] - self.last_cell_voltages[i]
                        if abs(delta_v) >= 0.005:  # Only consider if ΔV ≥ 5 mV
                            resistance = abs(delta_v / delta_i)
                            self.resistance_values[i].append(resistance)
                            resistances[i] = resistance
                            resistance_added = True
                for i in range(self.num_cells):
                    if not np.isnan(resistances[i]):
                        self.resistance_times[i].append(rel_time)

                res_str = ", ".join([f"R{i+1}: {resistances[i]:.4f} Ω" for i in range(self.num_cells)])
                self.get_logger().info(f"t={rel_time:.2f}s: {res_str}")

        moving_averages = []
        for i in range(self.num_cells):
            recent = self.resistance_values[i][-self.moving_avg_window:]
            if recent and not all(np.isnan(recent)):
                avg = np.nanmean(recent)
            else:
                avg = float('nan')
            moving_averages.append(avg)

        # Save data to CSV (including nan if resistance not computed)
        row = [rel_time, current] + cell_voltages + resistances + moving_averages
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
                
                if len(times) == 0 or len(values) == 0:
                    continue

                self.curves[i].setData(
                    times,
                    values,
                    symbol='o',
                    symbolSize=8,
                    symbolBrush=self.colors[i],
                    pen=None
                )

                # === Compute and plot moving average point ===
                recent_values = values[-self.moving_avg_window:]
                if len(recent_values) == 0 or np.all(np.isnan(recent_values)):
                    continue
                
                avg_resistance = np.nanmean(recent_values)
                avg_time = times[-1]  # Use latest time for marker position

                self.avg_markers[i].setData(
                    [avg_time],
                    [avg_resistance]
                )

                # === Confidence interval calculation ===
                delta_V = 0.004  # 4 mV uncertainty (recheck later again)
                delta_I = 0.05   # 50 mA uncertainty (recheck later again)

                upper = []
                lower = []
                for j, R in enumerate(values):
                    if j == 0:
                        upper.append(np.nan)
                        lower.append(np.nan)
                        continue
                    ΔV = self.last_cell_voltages[i] - self.last_cell_voltages[i-1] if i > 0 else delta_V
                    ΔI = self.last_current - self.last_current if self.last_current else delta_I
                    ΔI = ΔI if abs(ΔI) > 1e-3 else delta_I  # avoid div by 0
                    standard_deviation = abs(R) * np.sqrt((delta_V / ΔV)**2 + (delta_I / ΔI)**2)
                    upper.append(R + standard_deviation)
                    lower.append(R - standard_deviation)

                self.upper_curves[i].setData(times, upper)
                self.lower_curves[i].setData(times, lower)

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