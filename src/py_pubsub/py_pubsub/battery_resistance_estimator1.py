import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

class BatteryResistanceEstimator(Node):
    def __init__(self):
        super().__init__('battery_resistance_estimator1')
        self.subscription = self.create_subscription(
            BatteryState,
            '/bat_state',
            self.listener_callback,
            10)
        
        # Lists to store time and resistance
        self.times = []
        self.resistances = []
        self.start_time = None
        self.last_voltage = None
        self.last_current = None

        # Setup matplotlib figure and axis
        self.fig, self.ax = plt.subplots()
        self.line, = self.ax.plot([], [], 'r-')
        self.ax.set_xlabel('Time [s]')
        self.ax.set_ylabel('Internal Resistance [Ohm]')
        self.ax.set_title('Real-time Internal Resistance Estimation')
        self.ax.grid()

        # Animation
        self.ani = animation.FuncAnimation(
            self.fig, self.update_plot, interval=1000, blit=True)

        # Timer to keep GUI alive
        self.create_timer(0.1, self.dummy_timer_callback)

    def listener_callback(self, msg):
        voltage = msg.voltage
        current = msg.current
        time_sec = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

        if self.start_time is None:
            self.start_time = time_sec

        rel_time = time_sec - self.start_time

        # Calculate resistance if last values exist
        if self.last_voltage is not None and self.last_current is not None:
            delta_v = voltage - self.last_voltage
            delta_i = current - self.last_current

            if delta_i != 0:
                resistance = abs(delta_v / delta_i)
                self.get_logger().info(f'Resistance: {resistance:.4f} Ohm at t={rel_time:.2f}s')

                self.times.append(rel_time)
                self.resistances.append(resistance)

        self.last_voltage = voltage
        self.last_current = current

    def update_plot(self, frame):
        if len(self.times) > 0:
            self.line.set_data(self.times, self.resistances)
            self.ax.relim()
            self.ax.autoscale_view()
        return self.line,

    def dummy_timer_callback(self):
        # Dummy timer to keep ROS spinning and GUI responsive
        pass

def main(args=None):
    rclpy.init(args=args)
    node = BatteryResistanceEstimator()

    try:
        plt.show()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()