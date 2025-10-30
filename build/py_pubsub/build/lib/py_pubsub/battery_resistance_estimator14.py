import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import BatteryState
import numpy as np
import threading
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore
from pyqtgraph import ErrorBarItem
import csv
import os
import time
import queue

class BatteryLoggerFirst6(Node):
    def __init__(self):
        super().__init__('battery_logger_first6')

        # Subscribe to battery state
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
        self.rint_err_top = [[] for _ in range(self.num_cells)]
        self.rint_err_bottom = [[] for _ in range(self.num_cells)]
        self.rint_queue = queue.Queue()  # Thread-safe queue

        # CSV Logging Setup
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        self.csv_filename = f"battery_logger_first6_{timestamp_str}.csv"
        self.csv_file = open(self.csv_filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # CSV Header as requested (with ErrorBar columns)
        header = ['Time (s)', 'Current (A)', 'abs(delta_I)']
        header += [f'Voltage_Cell{i+1} (V)' for i in range(self.num_cells)]
        header += [f'abs(delta_U_Cell{i+1})' for i in range(self.num_cells)]
        header += [f'R_int_Cell{i+1}' for i in range(self.num_cells)]
        header += [f'ErrorBar_Top_Cell{i+1}' for i in range(self.num_cells)]
        header += [f'ErrorBar_Bottom_Cell{i+1}' for i in range(self.num_cells)]
        self.csv_writer.writerow(header)

        # Setup live plot: 2 rows x 3 columns of subplots
        self.app = pg.mkQApp("R_int Live Plot")
        self.win = pg.GraphicsLayoutWidget(show=True, title="Internal Resistance Live Plots")
        self.plots = []
        self.curves = []
        self.err_items = []
        plot_titles = [f"R_int_Cell{i+1}" for i in range(self.num_cells)]

        # distinct colors for markers (6 colors)
        colors = ['#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4', '#46f0f0']

        for i in range(2):  # 2 rows
            for j in range(3):  # 3 columns
                idx = i*3 + j
                p = self.win.addPlot(row=i, col=j, title=plot_titles[idx])
                p.setLabel('left', 'R_int', units='Ohm')
                p.setLabel('bottom', 'Time', units='s')
                p.showGrid(x=True, y=True, alpha=0.5)  # Enable grid for easier reading
                # marker-only plot: pen=None disables connecting line
                brush = pg.mkBrush(colors[idx])
                pen = pg.mkPen(colors[idx])
                curve = p.plot(pen=None, symbol='o', symbolBrush=brush, symbolPen=pen)
                # add an ErrorBarItem for this subplot
                err = ErrorBarItem(x=np.array([], dtype=float),
                                   y=np.array([], dtype=float),
                                   top=np.array([], dtype=float),
                                   bottom=np.array([], dtype=float),
                                   beam=0.05)
                p.addItem(err)

                self.plots.append(p)
                self.curves.append(curve)
                self.err_items.append(err)

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

        # uncertainties (tune as needed)
        u_U = 0.004   # 4 mV
        u_I = 0.05    # 50 mA

        abs_delta_I = float('nan')
        delta_I = float('nan')
        abs_delta_U_cells = [float('nan')] * self.num_cells
        delta_U_cells = [float('nan')] * self.num_cells
        R_int_cells = [float('nan')] * self.num_cells
        err_tops = [float('nan')] * self.num_cells
        err_bottoms = [float('nan')] * self.num_cells

        if self.last_current is not None and self.last_cell_voltages is not None:
            delta_I = current - self.last_current
            abs_delta_I = abs(delta_I)
            delta_U_cells = [cell_voltages[i] - self.last_cell_voltages[i] for i in range(self.num_cells)]
            abs_delta_U_cells = [abs(du) for du in delta_U_cells]

            if abs_delta_I >= 10:
                for i in range(self.num_cells):
                    # R_int using absolute deltas
                    if abs_delta_I != 0:
                        R_int_cells[i] = abs_delta_U_cells[i] / abs_delta_I
                        # improved confidence interval using abs(delta_i) and abs(delta_v)
                        try:
                            # match requested formula:
                            # ci_val = np.sqrt(((1.0 / abs(delta_i)) * u_U) ** 2 + ((-abs(delta_v) / (abs(delta_i) ** 2)) * u_I) ** 2)
                            ai = abs_delta_I
                            av = abs_delta_U_cells[i]
                            ci = np.sqrt(((1.0 / ai) * u_U) ** 2 + (((-av) / (ai ** 2)) * u_I) ** 2)
                        except Exception:
                            ci = float('nan')
                        err_tops[i] = ci
                        err_bottoms[i] = ci
                        # push for plotting: include error values
                        self.rint_queue.put((i, rel_time, R_int_cells[i], err_tops[i], err_bottoms[i]))
                    else:
                        R_int_cells[i] = float('nan')
                        err_tops[i] = float('nan')
                        err_bottoms[i] = float('nan')
            else:
                # If delta_I is not large enough, keep all as nan
                abs_delta_I = float('nan')
                abs_delta_U_cells = [float('nan')] * self.num_cells
                R_int_cells = [float('nan')] * self.num_cells
                err_tops = [float('nan')] * self.num_cells
                err_bottoms = [float('nan')] * self.num_cells

        # write CSV row: include error bar top and bottom per cell
        row = [rel_time, current, abs_delta_I] + cell_voltages + abs_delta_U_cells + R_int_cells + err_tops + err_bottoms
        self.csv_writer.writerow(row)

        self.last_current = current
        self.last_cell_voltages = cell_voltages

    def update_plot(self):
        """Run in Qt thread → safely read from queue and update plot"""
        while not self.rint_queue.empty():
            cell_idx, t, rint, etop, ebot = self.rint_queue.get()
            self.rint_times[cell_idx].append(t)
            self.rint_values[cell_idx].append(rint)
            self.rint_err_top[cell_idx].append(etop)
            self.rint_err_bottom[cell_idx].append(ebot)

        for i in range(self.num_cells):
            if self.rint_times[i] and self.rint_values[i]:
                # update marker-only data
                self.curves[i].setData(self.rint_times[i], self.rint_values[i], pen=None, symbol='o')
                # update corresponding error bar item (expects top/bottom as distances)
                x = np.array(self.rint_times[i], dtype=float)
                y = np.array(self.rint_values[i], dtype=float)
                top = np.array(self.rint_err_top[i], dtype=float)
                bottom = np.array(self.rint_err_bottom[i], dtype=float)
                self.err_items[i].setData(x=x, y=y, top=top, bottom=bottom)

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