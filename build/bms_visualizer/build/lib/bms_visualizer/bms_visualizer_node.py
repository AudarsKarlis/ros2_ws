import os
import time
import threading
from pyqtgraph.Qt import QtWidgets
# from PySide2 import QtWidgets
import rclpy
import rclpy.executors
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import BatteryState

from bms_visualizer.bms_window import BMSWindow

class BMSVisualizer(Node):
    def __init__(self, node_name="bms_visualizer_node", context = None, cli_args = None, namespace = None, use_global_arguments = True, enable_rosout = True, start_parameter_services = True, parameter_overrides = None, allow_undeclared_parameters = False, automatically_declare_parameters_from_overrides = False):
        super().__init__(node_name, context=context, cli_args=cli_args, namespace=namespace, use_global_arguments=use_global_arguments, enable_rosout=enable_rosout, start_parameter_services=start_parameter_services, parameter_overrides=parameter_overrides, allow_undeclared_parameters=allow_undeclared_parameters, automatically_declare_parameters_from_overrides=automatically_declare_parameters_from_overrides)

        self.declare_parameter("log_dir", "")
        self.log_dir = self.get_parameter("log_dir").get_parameter_value().string_value
        self.log_path = os.path.join(self.log_dir, time.strftime("%Y%m%d_%H%M%S_bms.csv", time.gmtime()))
        if self.log_dir != "":
            with open(self.log_path, "w") as fil:
                fil.write("t,vbat,ibat,v1,v2,v3,v4,v5,v6\n")
        self.window = BMSWindow()
        self._sub_float = self.create_subscription(BatteryState, "bms_state", self.update_volt, 10)


    def update_volt(self, msg: BatteryState):
        t = Time.from_msg(msg.header.stamp).nanoseconds*1e-9
        self.window.update("Battery Voltage", t, msg.voltage)
        self.window.update("Load Current", t, msg.current)
        for i, v in enumerate(msg.cell_voltage):
            self.window.update(f"Cell {i+1}", t, v)
            
        if self.log_dir != "":
            with open(self.log_path, "a") as fil:
                fil.write(f"{t},{msg.voltage},{msg.current}")
                for v in msg.cell_voltage:
                    fil.write(f",{v}")
                fil.write("\n")


def main(args=None):
    rclpy.init(args=args)
    app = QtWidgets.QApplication([])
    node = BMSVisualizer()
    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin)
    spin_thread.start()
    
    while True:
        try:
            app.processEvents()
        except KeyboardInterrupt:
            break
    rclpy.shutdown()


if __name__ == '__main__':
    main()
