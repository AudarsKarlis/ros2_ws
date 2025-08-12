import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
import numpy as np
import threading
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore
from pyqtgraph import ErrorBarItem
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
        self.error_bars = []        # Error bars for CI

        self.colors = ['r', 'g', 'b', 'c', 'm', 'y']
        self.plots = []
        self.curves = []

        # Arrange 2 rows × 3 columns
        for i in range(self.num_cells):
            if i > 0 and i % 3 == 0:
                self.win.nextRow()
            plot = self.win.addPlot(title=f"Cell {i+1} Resistance [Ohm]")
            plot.setLabel('left', 'Resistance', units='Ohm')
            plot.setLabel('bottom', 'Time', units='s')
            plot.showGrid(x=True, y=True)
            plot.enableAutoRange(x=True, y=True)

            # Resistance points
            curve = plot.plot(
                pen=None,
                symbol='o',
                symbolSize=8,
                symbolBrush=self.colors[i],
                symbolPen='k',
                name=f"Cell {i+1}"
            )

            # Moving average marker
            avg_marker = plot.plot(
                pen=None,
                symbol='s',  # square marker
                symbolSize=12,
                symbolBrush='w',
                symbolPen=pg.mkPen('k', width=2),
                name=f"Avg {i+1}"
            )

            # Error bars (confidence intervals)
            err = ErrorBarItem(
                x=np.array([], dtype=float),
                y=np.array([], dtype=float),
                top=np.array([], dtype=float),
                bottom=np.array([], dtype=float),
                beam=0.05
            )
            plot.addItem(err)

            self.plots.append(plot)
            self.curves.append(curve)
            self.avg_markers.append(avg_marker)
            self.error_bars.append(err)

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

            if abs(delta_i) >= 0.1:  # ΔI ≥ 100 mA
                for i in range(self.num_cells):
                    if self.last_cell_voltages[i] is not None:
                        delta_v = cell_voltages[i] - self.last_cell_voltages[i]
                        if abs(delta_v) >= 0.005:  # ΔV ≥ 5 mV
                            resistance = abs(delta_v / delta_i)
                            self.resistance_values[i].append(resistance)
                            resistances[i] = resistance
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

        # Save data to CSV
        row = [rel_time, current] + cell_voltages + resistances + moving_averages
        self.csv_writer.writerow(row)

        # Update memory
        self.last_cell_voltages = list(cell_voltages)
        self.last_current = current

    def update_plot(self):
        if len(self.resistance_times) == 0:
            return

        # Constants for uncertainty (from datasheet later)
        u_U = 0.004   # 4 mV
        u_I = 0.05    # 50 mA
        MIN_CURRENT = 0.1

        for i in range(self.num_cells):
            if len(self.resistance_values[i]) > 0:
                times = np.array(self.resistance_times[i], dtype=float)
                values = np.array(self.resistance_values[i], dtype=float)

                if len(times) == 0 or len(values) == 0:
                    continue

                # Plot resistance points
                self.curves[i].setData(
                    times,
                    values,
                    symbol='o',
                    symbolSize=8,
                    symbolBrush=self.colors[i],
                    pen=None
                )

                # Moving average marker
                recent_values = values[-self.moving_avg_window:]
                if len(recent_values) > 0 and not np.all(np.isnan(recent_values)):
                    avg_resistance = np.nanmean(recent_values)
                    avg_time = times[-1]
                    self.avg_markers[i].setData([avg_time], [avg_resistance])

                # Error bar calculation
                yerr = []
                for j, R in enumerate(values):
                    if np.isnan(R):
                        yerr.append(np.nan)
                        continue
                    U = self.last_cell_voltages[i]
                    I = self.last_current
                    if I is None or U is None or abs(I) < MIN_CURRENT:
                        yerr.append(np.nan)
                        continue
                    u_R = np.sqrt(((1.0 / I) * u_U) ** 2 + ((-U / (I ** 2)) * u_I) ** 2)
                    yerr.append(u_R)

                yerr_np = np.array(yerr, dtype=float)

                # Update error bars
                self.error_bars[i].setData(
                    x=times,
                    y=values,
                    top=yerr_np,
                    bottom=yerr_np
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