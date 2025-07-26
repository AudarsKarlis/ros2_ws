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

        # Data buffers
        self.voltage_history = deque(maxlen=100)
        self.current_history = deque(maxlen=100)
        self.time_history = deque(maxlen=100)

        self.start_time = None
        self.resistance_values = []
        self.resistance_times = []

        # Setup PyQtGraph window
        self.app = pg.mkQApp("Real-time Battery Resistance")
        self.win = pg.GraphicsLayoutWidget(show=True, title="Battery Internal Resistance Estimation")
        self.plot = self.win.addPlot(title="Internal Resistance [Ohm]")
        self.plot.setLabel('left', 'Resistance', units='Ohm')
        self.plot.setLabel('bottom', 'Time', units='s')
        self.plot.showGrid(x=True, y=True)
        self.curve = self.plot.plot(pen=pg.mkPen(color='y', width=2))
        self.plot.enableAutoRange(x=True, y=True)

        # Timer for plot updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(200)  # 200 ms

    def listener_callback(self, msg):
        voltage = msg.voltage
        current = msg.current
        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

        if self.start_time is None:
            self.start_time = timestamp

        rel_time = timestamp - self.start_time

        self.voltage_history.append(voltage)
        self.current_history.append(current)
        self.time_history.append(rel_time)

        if len(self.voltage_history) >= 2:
            dv = self.voltage_history[-1] - self.voltage_history[-2]
            di = self.current_history[-1] - self.current_history[-2]

            if abs(di) > 1e-3:
                r_internal = abs(dv / di)
                self.get_logger().info(f'Resistance: {r_internal:.4f} Ohm at t={rel_time:.2f}s')
                self.resistance_times.append(rel_time)
                self.resistance_values.append(r_internal)

    def update_plot(self):
        if len(self.resistance_values) > 0:
            self.curve.setData(self.resistance_times, self.resistance_values)

    def start_ros_spin(self):
        """Start rclpy spin in a separate thread."""
        spin_thread = threading.Thread(target=rclpy.spin, args=(self,), daemon=True)
        spin_thread.start()


def main(args=None):
    rclpy.init(args=args)
    node = BatteryResistanceEstimator()
    node.start_ros_spin()       # spin ROS in background
    node.app.exec_()            # run Qt event loop
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()