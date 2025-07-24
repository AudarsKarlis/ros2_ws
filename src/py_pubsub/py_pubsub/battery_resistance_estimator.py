#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from collections import deque
import numpy as np

# Optional: for live plotting
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui


class BatteryResistanceEstimator(Node):
    def __init__(self):
        super().__init__('battery_resistance_estimator')

        # Subscribes to the topic
        self.subscription = self.create_subscription(
            BatteryState,
            '/bat_state',
            self.listener_callback,
            10)

        self.voltage_history = deque(maxlen=100)  # store recent data
        self.current_history = deque(maxlen=100)
        self.time_history = deque(maxlen=100)

        self.start_time = None

        # Setup live plot
        self.app = pg.mkQApp("Real-time Battery Resistance")
        self.win = pg.GraphicsLayoutWidget(show=True, title="Battery Internal Resistance Estimation")
        self.plot = self.win.addPlot(title="Internal Resistance [Ohm]")
        self.plot.showGrid(x=True, y=True)
        self.curve = self.plot.plot(pen='y')
        self.resistance_values = []
        self.resistance_times = []

        # Timer for PyQtGraph updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(200)  # update every 200 ms

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

        # Compute resistance only if we have at least 2 samples
        if len(self.voltage_history) >= 2:
            dv = self.voltage_history[-1] - self.voltage_history[-2]
            di = self.current_history[-1] - self.current_history[-2]

            if abs(di) > 1e-3:  # prevent divide by zero
                r_internal = abs(dv / di)
                self.get_logger().info(f'Real-time Resistance: {r_internal:.4f} Ohm')
                self.resistance_values.append(r_internal)
                self.resistance_times.append(rel_time)

    def update_plot(self):
        if len(self.resistance_values) > 0:
            self.curve.setData(self.resistance_times, self.resistance_values)

    def spin(self):
        timer = QtCore.QTimer()
        timer.timeout.connect(lambda: None)
        timer.start(100)
        rclpy.spin(self)
        self.app.exec_()


def main(args=None):
    rclpy.init(args=args)
    node = BatteryResistanceEstimator()
    node.spin()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()