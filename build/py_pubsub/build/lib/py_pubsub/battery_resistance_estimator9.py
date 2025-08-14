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
            #Stores all plot elements in list for easier updating later on
            self.plots.append(plot)
            self.curves.append(curve)
            self.avg_markers.append(avg_marker)
            self.error_bars.append(err) #For updating error bar with new data

        self.win.show() #Displays entire window after plots have been created

        # Timer for plot updates
        self.timer = QtCore.QTimer() #Makes QTimer object - like a stopwatch
        self.timer.timeout.connect(self.update_plot) #Every time timer 'ticks' the plot is updated
        self.timer.start(200)  #5 times per second (200ms) plot update is called

    def listener_callback(self, msg): #Callback function called by ROS2 whenever new /bat_state is received
        timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9 #ROS2 timestamps to relative time
        if self.start_time is None: #On first message self.start_time = timestamp
            self.start_time = timestamp
        rel_time = timestamp - self.start_time #Calculates time since last message, Used for plottin on X-axis

        cell_voltages = list(msg.cell_voltage) #Extracts cell voltages from message and saves as list
        current = msg.current #Extracts current from message

        resistances = [float('nan')] * self.num_cells #Creates list for resistance values, Initially with NaN

        # Constants for uncertainty
        u_U = 0.004   # 4 mV
        u_I = 0.05    # 50 mA
        MIN_CURRENT = 0.1 #Don't calculate resistance when current is near zero

        # Only compute if previous values exist
        if self.last_current is not None and len(cell_voltages) == self.num_cells: #Checks previous measurement
            #and number of cell voltages
            delta_i = current - self.last_current #Calculated delta_I from current and last timestamp

            if abs(delta_i) >= 0.1:  #Only proceed if ΔI ≥ 100 mA, Filters the noise
                for i in range(self.num_cells):
                    if self.last_cell_voltages[i] is not None: #If there is voltage previously
                        delta_v = cell_voltages[i] - self.last_cell_voltages[i] #Calculate delta_V
                        if abs(delta_v) >= 0.005:  #Only proceed if ΔV ≥ 5 mV
                            resistance = abs(delta_v / delta_i) #Calculate absolute value of resistance
                            self.resistance_values[i].append(resistance) #Add resistance value to history list
                            resistances[i] = resistance #Store resistance for respective timestep
                for i in range(self.num_cells): #If resistance was calculated, store corresponding timestamp
                    if not np.isnan(resistances[i]):
                        self.resistance_times[i].append(rel_time)

        moving_averages = [] #Creates list for moving averages and calculates value for it
        for i in range(self.num_cells):
            recent = self.resistance_values[i][-self.moving_avg_window:]
            if recent and not all(np.isnan(recent)):
                avg = np.nanmean(recent)
            else:
                avg = float('nan')
            moving_averages.append(avg)

        # === CI calculation for logging ===
        ci_top_list = [] #Creates list for upper bounds
        ci_bottom_list = [] #Creates list for lower bounds
        for i in range(self.num_cells):
            if np.isnan(resistances[i]) or current is None or cell_voltages[i] is None or abs(current) < MIN_CURRENT:
                ci_val = float('nan') #Don't calculate (put NaN) if resistance, current, voltage is NaN or ...
            else: #In any other case calculate ci_val
                ci_val = np.sqrt(((1.0 / current) * u_U) ** 2 + ((-cell_voltages[i] / (current ** 2)) * u_I) ** 2)
            ci_top_list.append(ci_val) #Add ci_val to upper bounds list
            ci_bottom_list.append(ci_val) #Add ci_val to lower bounds list
            self.last_ci_top[i] = ci_val #Stores last calculated upper CI to draw error bar
            self.last_ci_bottom[i] = ci_val #Stored last calculated lower CI to draw error bar

        # Save to CSV
        row = [rel_time, current] + cell_voltages + resistances + moving_averages + ci_top_list + ci_bottom_list
        self.csv_writer.writerow(row) #Writes row to csv file

        # Update memory
        self.last_cell_voltages = list(cell_voltages) #Saves voltage value for use in next message
        self.last_current = current #Saves current value for use in next message

    def update_plot(self): #Defines update plot method
        for i in range(self.num_cells): #Loops through each battery cell
            if len(self.resistance_values[i]) > 0: #Checks if there already are resistance value for this cell
                times = np.array(self.resistance_times[i], dtype=float) #Converts time list to NumPy array
                values = np.array(self.resistance_values[i], dtype=float) #Converts resistance list to NumPy array

                if len(times) == 0 or len(values) == 0: #Safety check if empty lists don't exist
                    continue

                # Scatter points (filter NaNs)
                mask_curve = ~np.isnan(times) & ~np.isnan(values) #Ensures that time and values are 'not NaN'
                times_curve = times[mask_curve] #times curve contains only valid points to plot
                values_curve = values[mask_curve] #values curve contains only valid points to plot
                self.curves[i].setData( #Updates scatter plot for cell
                    times_curve,
                    values_curve,
                    symbol='o',
                    symbolSize=8,
                    symbolBrush=self.colors[i],
                    pen=None #No connecting line between points
                )

                # Moving average marker
                if len(values_curve) > 0: #Checks if there is at least one valid point
                    recent_values = values_curve[-self.moving_avg_window:] #Gets values for calculation
                    avg_resistance = np.nanmean(recent_values) #Calculates mean value
                    avg_time = times_curve[-1] #Gets most recent time value
                    self.avg_markers[i].setData([avg_time], [avg_resistance]) #Plots marker on top of circle

                # Error bars (use last computed CI from callback)
                yerr = [self.last_ci_top[i]] * len(times_curve) #Creates list of error values, It gives the 
                #same error value for each circle (INCORECT!!!), Value history is not stored!!!
                self.error_bars[i].setData( #Replaces all data in error bar with actual value (INCORECT!!!)
                    x=times_curve,
                    y=values_curve,
                    top=yerr,
                    bottom=yerr
                )

    def start_ros_spin(self): #Defines method for ROS spinning
        spin_thread = threading.Thread(target=rclpy.spin, args=(self,), daemon=True) #Continues spinning
        spin_thread.start() #Actually starts the thread, Incomming messages are processed in the background

    def destroy_node(self): #Overrides 'destroy_node()' method to add cleanup behaviour
        self.csv_file.close() #Closes csv file - it is written into disk
        self.get_logger().info(f"CSV log saved to {os.path.abspath(self.csv_filename)}") #Shows where csv is
        super().destroy_node() #Calls original destroy method to properly shut down node


def main(args=None): #Defines main entry function of script
    rclpy.init(args=args) #Initializes ROS2 client library
    node = BatteryResistanceEstimator() #Creates instance for node class, Sets up subscriber, etc.
    node.start_ros_spin() #Calls method for background thread
    try:
        node.app.exec_() #Starts Qt event loop for real-time plotting, Will stay there until close window
    finally: #Ensures that cleanup will always run
        node.destroy_node() #Calls for closing csv, saving messages, shut down ROS node
        rclpy.shutdown() #Shuts down ROS2 cleanly


if __name__ == '__main__': #Main is called only when script is executed directly, not as module
    main()