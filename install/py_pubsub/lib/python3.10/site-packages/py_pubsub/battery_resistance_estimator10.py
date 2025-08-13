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

        # === ROS 2 Subscription ===
        self.subscription = self.create_subscription(
            BatteryState,
            '/bat_state',
            self.listener_callback,
            10
        )

        self.start_time = None
        self.num_cells = 6
        self.last_cell_voltages = [None] * self.num_cells
        self.last_current = None

        # Resistance plotting data
        self.resistance_times = [[] for _ in range(self.num_cells)]
        self.resistance_values = [[] for _ in range(self.num_cells)]

        # CI history (persistent)
        self.ci_top_values = [[] for _ in range(self.num_cells)]
        self.ci_bottom_values = [[] for _ in range(self.num_cells)]

        # === CSV Logging Setup ===
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        self.csv_filename = f"battery_estimator_log_{timestamp_str}.csv"
        self.csv_file = open(self.csv_filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

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
        self.moving_avg_window = 2
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
                symbol='s',
                symbolSize=12,
                symbolBrush='w',
                symbolPen=pg.mkPen('k', width=2),
                name=f"Avg {i+1}"
            )

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

    def listener_callback(self, msg):
        if self.start_time is None:
            self.start_time = time.time()
        elapsed = time.time() - self.start_time

        cell_voltages = list(msg.cell_voltage)[:self.num_cells]
        current = msg.current

        row_data = [elapsed, current] + cell_voltages

        uU = 0.004  # Voltage uncertainty (V)
        uI = 0.05   # Current uncertainty (A)

        resistances = []
        moving_averages = []
        ci_tops = []
        ci_bottoms = []

        for i in range(self.num_cells):
            R_val = float('nan')
            R_avg = float('nan')
            ci_top_val = float('nan')
            ci_bottom_val = float('nan')

            if self.last_cell_voltages[i] is not None and self.last_current is not None:
                dV = cell_voltages[i] - self.last_cell_voltages[i]
                dI = current - self.last_current

                if abs(dI) >= 0.1 and abs(dV) >= 0.005:
                    R_val = dV / dI
                    self.resistance_times[i].append(elapsed)
                    self.resistance_values[i].append(R_val)

                    # CI calculation
                    U = cell_voltages[i]
                    I = current
                    if I != 0:
                        uR = np.sqrt((1/I * uU)**2 + ((-U)/(I**2) * uI)**2)
                        ci_top_val = R_val + uR
                        ci_bottom_val = R_val - uR

                    # Append CI history
                    self.ci_top_values[i].append(ci_top_val)
                    self.ci_bottom_values[i].append(ci_bottom_val)

                    # Moving average
                    if len(self.resistance_values[i]) >= self.moving_avg_window:
                        R_avg = np.mean(self.resistance_values[i][-self.moving_avg_window:])

            resistances.append(R_val)
            moving_averages.append(R_avg)
            ci_tops.append(ci_top_val)
            ci_bottoms.append(ci_bottom_val)

        self.last_cell_voltages = cell_voltages
        self.last_current = current

        row_data += resistances + moving_averages + ci_tops + ci_bottoms
        self.csv_writer.writerow(row_data)
        self.csv_file.flush()

        # Update plots
        for i in range(self.num_cells):
            self.curves[i].setData(self.resistance_times[i], self.resistance_values[i])

            if len(self.resistance_values[i]) >= self.moving_avg_window:
                self.avg_markers[i].setData(
                    [self.resistance_times[i][-1]],
                    [np.mean(self.resistance_values[i][-self.moving_avg_window:])]
                )

            # Persistent error bars (full history)
            if len(self.resistance_values[i]) > 0:
                times = np.array(self.resistance_times[i], dtype=float)
                res_vals = np.array(self.resistance_values[i], dtype=float)
                top_offsets = np.array(self.ci_top_values[i], dtype=float) - res_vals
                bottom_offsets = res_vals - np.array(self.ci_bottom_values[i], dtype=float)

                self.error_bars[i].setData(
                    x=times,
                    y=res_vals,
                    top=top_offsets,
                    bottom=bottom_offsets
                )

    def run(self):
        timer = QtCore.QTimer()
        timer.timeout.connect(lambda: None)
        timer.start(100)
        rclpy.spin(self, executor=rclpy.executors.MultiThreadedExecutor())

def main(args=None):
    rclpy.init(args=args)
    estimator = BatteryResistanceEstimator()
    thread = threading.Thread(target=estimator.run, daemon=True)
    thread.start()
    pg.exec()

if __name__ == '__main__':
    main()