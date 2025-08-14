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

        # Confidence interval history for each cell
        self.ci_top_history = [[] for _ in range(self.num_cells)]
        self.ci_bottom_history = [[] for _ in range(self.num_cells)]

        # Store last computed CI values for each cell (still used for CSV/logging)
        self.last_ci_top = [float('nan')] * self.num_cells
        self.last_ci_bottom = [float('nan')] * self.num_cells

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
        header += [f'CI_Top_Cell{i+1} (Ohm)' for i in range(self.num_cells)]
        header += [f'CI_Bottom_Cell{i+1} (Ohm)' for i in range(self.num_cells)]
        self.csv_writer.writerow(header)

        # === Plotting Setup ===
        self.app = pg.mkQApp("Real-time Battery Resistance")
        self.win = pg.GraphicsLayoutWidget(show=True, title="Battery Internal Resistance Estimation")
        self.moving_avg_window = 3
        self.avg_markers = []
        self.error_bars = []

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
                symbol='s',
                symbolSize=12,
                symbolBrush='w',
                symbolPen=pg.mkPen('k', width=2),
                name=f"Avg {i+1}"
            )

            # Error bars
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
        self.timer.start(200)

    def listener_callback(self, msg):
        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if self.start_time is None:
            self.start_time = timestamp
        rel_time = timestamp - self.start_time

        cell_voltages = list(msg.cell_voltage)
        current = msg.current

        resistances = [float('nan')] * self.num_cells

        # Constants for uncertainty
        u_U = 0.004   # 4 mV
        u_I = 0.05    # 50 mA
        MIN_CURRENT = 0.1

        # Only compute if previous values exist
        if self.last_current is not None and len(cell_voltages) == self.num_cells:
            delta_i = current - self.last_current

            if abs(delta_i) >= 0.1:
                for i in range(self.num_cells):
                    if self.last_cell_voltages[i] is not None:
                        delta_v = cell_voltages[i] - self.last_cell_voltages[i]
                        if abs(delta_v) >= 0.005:
                            resistance = abs(delta_v / delta_i)
                            self.resistance_values[i].append(resistance)
                            resistances[i] = resistance
                            self.resistance_times[i].append(rel_time)

                            # Calculate CI for this resistance value
                            if np.isnan(resistance) or current is None or cell_voltages[i] is None or abs(current) < MIN_CURRENT:
                                ci_val = float('nan')
                            else:
                                ci_val = np.sqrt(((1.0 / current) * u_U) ** 2 + ((-cell_voltages[i] / (current ** 2)) * u_I) ** 2)
                            self.ci_top_history[i].append(ci_val)
                            self.ci_bottom_history[i].append(ci_val)

        moving_averages = []
        for i in range(self.num_cells):
            recent = self.resistance_values[i][-self.moving_avg_window:]
            if recent and not all(np.isnan(recent)):
                avg = np.nanmean(recent)
            else:
                avg = float('nan')
            moving_averages.append(avg)

        # === CI calculation for logging (for last value, for CSV) ===
        ci_top_list = []
        ci_bottom_list = []
        for i in range(self.num_cells):
            if np.isnan(resistances[i]) or current is None or cell_voltages[i] is None or abs(current) < MIN_CURRENT:
                ci_val = float('nan')
            else:
                ci_val = np.sqrt(((1.0 / current) * u_U) ** 2 + ((-cell_voltages[i] / (current ** 2)) * u_I) ** 2)
            ci_top_list.append(ci_val)
            ci_bottom_list.append(ci_val)
            self.last_ci_top[i] = ci_val
            self.last_ci_bottom[i] = ci_val

        # Save to CSV
        row = [rel_time, current] + cell_voltages + resistances + moving_averages + ci_top_list + ci_bottom_list
        self.csv_writer.writerow(row)

        # Update memory
        self.last_cell_voltages = list(cell_voltages)
        self.last_current = current

    def update_plot(self):
        for i in range(self.num_cells):
            if len(self.resistance_values[i]) > 0:
                times = np.array(self.resistance_times[i], dtype=float)
                values = np.array(self.resistance_values[i], dtype=float)

                if len(times) == 0 or len(values) == 0:
                    continue

                # Scatter points (filter NaNs)
                mask_curve = ~np.isnan(times) & ~np.isnan(values)
                times_curve = times[mask_curve]
                values_curve = values[mask_curve]
                self.curves[i].setData(
                    times_curve,
                    values_curve,
                    symbol='o',
                    symbolSize=8,
                    symbolBrush=self.colors[i],
                    pen=None
                )

                # Moving average marker
                if len(values_curve) > 0:
                    recent_values = values_curve[-self.moving_avg_window:]
                    avg_resistance = np.nanmean(recent_values)
                    avg_time = times_curve[-1]
                    self.avg_markers[i].setData([avg_time], [avg_resistance])

                # Error bars (use CI history)
                ci_top_arr = np.array(self.ci_top_history[i], dtype=float)
                ci_bottom_arr = np.array(self.ci_bottom_history[i], dtype=float)
                # Filter CI values to match valid resistance points
                ci_top_curve = ci_top_arr[mask_curve]
                ci_bottom_curve = ci_bottom_arr[mask_curve]
                self.error_bars[i].setData(
                    x=times_curve,
                    y=values_curve,
                    top=ci_top_curve,
                    bottom=ci_bottom_curve
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