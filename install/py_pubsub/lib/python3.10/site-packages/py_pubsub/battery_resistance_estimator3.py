import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from collections import deque
import numpy as np
import threading
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui


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

        self.num_cells = 6  # number of battery cells (assumed fixed)
        self.last_cell_voltages = [None] * self.num_cells
        self.last_current = None

        # Store per-cell resistance data
        self.resistance_times = []
        self.resistance_values = [[] for _ in range(self.num_cells)]

        # Setup PyQtGraph window
        self.app = pg.mkQApp("Real-time Battery Resistance")
        self.win = pg.GraphicsLayoutWidget(show=True, title="Battery Internal Resistance Estimation")
        self.plot = self.win.addPlot(title="Internal Resistance per Cell [Ohm]")
        self.plot.setLabel('left', 'Resistance', units='Ohm')
        self.plot.setLabel('bottom', 'Time', units='s')
        self.plot.showGrid(x=True, y=True)
        self.plot.addLegend()
        self.plot.enableAutoRange(x=True, y=True)

        # Line colors for each cell
        self.colors = ['r', 'g', 'b', 'c', 'm', 'y']
        self.curves = []
        for i in range(self.num_cells):
            curve = self.plot.plot(pen=pg.mkPen(self.colors[i], width=2), name=f"Cell {i+1}")
            self.curves.append(curve)

        # Timer for plot updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(200)  # 200 ms

    def listener_callback(self, msg):
        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if self.start_time is None:
            self.start_time = timestamp
        rel_time = timestamp - self.start_time

        cell_voltages = msg.cell_voltage
        current = msg.current

        # Only compute if previous values exist and length matches
        if self.last_current is not None and len(cell_voltages) == self.num_cells:
            delta_i = current - self.last_current

            if abs(delta_i) > 1e-3:
                for i in range(self.num_cells):
                    if self.last_cell_voltages[i] is not None:
                        delta_v = cell_voltages[i] - self.last_cell_voltages[i]
                        resistance = abs(delta_v / delta_i)
                        self.resistance_values[i].append(resistance)
                self.resistance_times.append(rel_time)

                res_str = ", ".join([f"R{i+1}: {self.resistance_values[i][-1]:.4f} Ω" for i in range(self.num_cells)])
                self.get_logger().info(f"t={rel_time:.2f}s: {res_str}")

        # Update history
        self.last_cell_voltages = list(cell_voltages)
        self.last_current = current

    def update_plot(self):
        if len(self.resistance_times) == 0:
            return
        for i in range(self.num_cells):
            if len(self.resistance_values[i]) > 0:
                self.curves[i].setData(self.resistance_times, self.resistance_values[i])

    def start_ros_spin(self):
        spin_thread = threading.Thread(target=rclpy.spin, args=(self,), daemon=True)
        spin_thread.start()


def main(args=None):
    rclpy.init(args=args)
    node = BatteryResistanceEstimator()
    node.start_ros_spin()
    node.app.exec_()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()