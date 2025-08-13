import rclpy #For making ROS2 environment
from rclpy.node import Node #Import Node for implementing ROS2 nodes in Python
from sensor_msgs.msg import BatteryState #Imports ROS message for battery state info
import numpy as np #NumPy - fundamental package for array and numeric operations
import threading #For working with threading. In this script 'deamon' thread is spinning
import pyqtgraph as pg #Plotting library
from pyqtgraph.Qt import QtCore #For updating graph periodically
from pyqtgraph import ErrorBarItem #For plotting vertical error bars
import csv #Module for reading/writing csv file
import os #For building/checking paths
import time #Used for timestamps


class BatteryResistanceEstimator(Node): #New class 'BatteryResistanceEstimator' with features from 'Node' is defined
    def __init__(self): #Defines constructor method of object
        super().__init__('battery_resistance_estimator') #Constructs node called 'battery_resistance_estimator'

        # Subscribe to battery state
        self.subscription = self.create_subscription( #Calls node method to subscribe to a topic
            BatteryState, #Message type expected from topic
            '/bat_state', #Topic name to listen to
            self.listener_callback, #Function in class that runs every time new message arrives
            10) #Up to 10 messages can be stored if callback can not keep up

        self.start_time = None #Sets initial start time
        self.num_cells = 6 #Stores number of cells
        self.last_cell_voltages = [None] * self.num_cells #Stores previous voltage reading (no data yet)
        self.last_current = None #Stores previous current reading (starts with 'no data yet')

        # Resistance plotting data
        self.resistance_times = [[] for _ in range(self.num_cells)] #Creates list of empty lists for each cell, Stores time
        self.resistance_values = [[] for _ in range(self.num_cells)] #Stores resistance values

        # Store last computed CI values for each cell
        self.last_ci_top = [float('nan')] * self.num_cells #'Not value yet' is stored as CI upper value
        self.last_ci_bottom = [float('nan')] * self.num_cells #'Not value yet' is stored as CI lower value

        # === CSV Logging Setup ===
        timestamp_str = time.strftime("%Y%m%d_%H%M%S") #YYYYMMDD_HHMMSS format is used for naming csv file
        self.csv_filename = f"battery_estimator_log_{timestamp_str}.csv" #File name for csv file is defined
        self.csv_file = open(self.csv_filename, mode='w', newline='') #Opens file in writing mode
        self.csv_writer = csv.writer(self.csv_file) #Object for writing rows is tied up to csv file

        # CSV Header
        header = ['Time (s)', 'Current (A)'] #Starts building list with first two column names
        header += [f'Voltage_Cell{i+1} (V)' for i in range(self.num_cells)] #Adds one header for cell voltage
        header += [f'Resistance_Cell{i+1} (Ohm)' for i in range(self.num_cells)] #Adds one header per cell resistance
        header += [f'MovingAvg_Cell{i+1} (Ohm)' for i in range(self.num_cells)] #Adds one header per cell moving average
        header += [f'CI_Top_Cell{i+1} (Ohm)' for i in range(self.num_cells)] #... upper CI bound
        header += [f'CI_Bottom_Cell{i+1} (Ohm)' for i in range(self.num_cells)] #... lower CI bound
        self.csv_writer.writerow(header) #Writes entire header as first row of csv file

        # === Plotting Setup ===
        self.app = pg.mkQApp("Real-time Battery Resistance") #Displays window with name in brackets
        self.win = pg.GraphicsLayoutWidget(show=True, title="Battery Internal Resistance Estimation") #Creates main
        #plotting window, amkes it visible imediately, 'title' is displayed in window's title bar
        self.moving_avg_window = 3  #Use last 3 resistance values
        self.avg_markers = []       #One marker per cell
        self.error_bars = []        #Objects for error bars for CI are created

        self.colors = ['r', 'g', 'b', 'c', 'm', 'y'] #Colour for each cell's plot line
        self.plots = [] #Store plot objects
        self.curves = [] #Store data curve objects

        # Arrange 2 rows × 3 columns
        for i in range(self.num_cells): #Loops over each cell (for creating subplot)
            if i > 0 and i % 3 == 0: #After 3 subplots
                self.win.nextRow() #move to next row
            plot = self.win.addPlot(title=f"Cell {i+1} Resistance [Ohm]") #Creates new subplot
            plot.setLabel('left', 'Resistance', units='Ohm') #Y-axis labeled as 'Resistance'
            plot.setLabel('bottom', 'Time', units='s') #X-axis labeled as 'Time'
            plot.showGrid(x=True, y=True) #Turns on grid line for X and Y
            plot.enableAutoRange(x=True, y=True) #Enables auto-rescaling

            # Resistance points
            curve = plot.plot( #Creates scatter-plot curve
                pen=None, #No connecting lines between points
                symbol='o', #Symbol for circle
                symbolSize=8, #Size for circle
                symbolBrush=self.colors[i], #Fills circle with colour assigned to that cell
                symbolPen='k', #Draws black outline around each circle
                name=f"Cell {i+1}" #Gives name
            )

            # Moving average marker
            avg_marker = plot.plot( #Creates scatter-point
                pen=None,
                symbol='s',
                symbolSize=12,
                symbolBrush='w',
                symbolPen=pg.mkPen('k', width=2),
                name=f"Avg {i+1}"
            )

            # Error bars
            err = ErrorBarItem( #Creates error bar plot object
                x=np.array([], dtype=float), #Empty list for X value of error bar's center
                y=np.array([], dtype=float), #Empty list for Y value of error bar's center
                top=np.array([], dtype=float), #Empty list of top offset counted from Y value
                bottom=np.array([], dtype=float), #Empty list of bottom offset counted from Y value
                beam=0.05 #For little horizontal lines at the ends of vertical line
            )
            plot.addItem(err) #Call for error bars so they are added (displayed) in plot canvas

            self.plots.append(plot)
            self.curves.append(curve)
            self.avg_markers.append(avg_marker)
            self.error_bars.append(err) #For updating error bar with new data

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

        # Constants for uncertainty
        u_U = 0.004   # 4 mV
        u_I = 0.05    # 50 mA
        MIN_CURRENT = 0.1

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

        moving_averages = []
        for i in range(self.num_cells):
            recent = self.resistance_values[i][-self.moving_avg_window:]
            if recent and not all(np.isnan(recent)):
                avg = np.nanmean(recent)
            else:
                avg = float('nan')
            moving_averages.append(avg)

        # === CI calculation for logging ===
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

                # Error bars (use last computed CI from callback)
                yerr = [self.last_ci_top[i]] * len(times_curve)
                self.error_bars[i].setData(
                    x=times_curve,
                    y=values_curve,
                    top=yerr,
                    bottom=yerr
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