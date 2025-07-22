import sys
import numpy as np
from MetaArray import MetaArray
from pyqtgraph.Qt.QtCore import Qt
from pyqtgraph.Qt.QtWidgets import (
# from PySide2.QtCore import Qt
# from PySide2.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QGridLayout,
    QLineEdit,
    QLabel,
    QWidget,
    QTabWidget,
    QScrollBar
)
import pyqtgraph as pg


class BMSWindow(QMainWindow):
    def __init__(self,parent=None):
        super().__init__(parent)
        lyt_main = QVBoxLayout()
        wgt_main = QWidget()
        self.wgt_tab = QTabWidget()
        
        # Voltage Tab
        wgt_txt = QWidget()
        lyt_txt = QGridLayout()
        self.le_voltages = {}
        for i in range(1,7):
            le_tmp = QLineEdit()
            le_tmp.setReadOnly(True)
            self.le_voltages[f"Cell {int(i)}"] = le_tmp
            lbl_temp = QLabel(f"Cell {int(i)}")
            lyt_txt.addWidget(lbl_temp, i, 0)
            lyt_txt.addWidget(le_tmp, i, 1)
        
        le_tos_voltage = QLineEdit()
        le_tos_voltage.setAlignment(Qt.AlignRight)
        le_tos_voltage.setReadOnly(True)
        
        lbl_tos_voltage = QLabel("Top Of Stack Voltage")
        le_bat_voltage = QLineEdit()
        le_bat_voltage.setAlignment(Qt.AlignRight)
        le_bat_voltage.setReadOnly(True)
        
        lbl_bat_voltage = QLabel("Battery Voltage")
        le_ld_voltage = QLineEdit()
        le_ld_voltage.setAlignment(Qt.AlignRight)
        le_ld_voltage.setReadOnly(True)
        lbl_ld_voltage = QLabel("Load Voltage")
        le_bat_current = QLineEdit()
        le_bat_current.setAlignment(Qt.AlignRight)
        le_bat_current.setReadOnly(True)
        lbl_bat_current = QLabel("Battery Current")
        
        self.le_voltages[f"Top Of Stack"] = le_tos_voltage
        self.le_voltages[f"Battery Voltage"] = le_bat_voltage
        self.le_voltages[f"Load Voltage"] = le_ld_voltage
        self.le_voltages[f"Load Current"] = le_bat_current
        lyt_txt.addWidget(lbl_tos_voltage, 1, 2, )
        lyt_txt.addWidget(le_tos_voltage, 1, 3)
        lyt_txt.addWidget(lbl_bat_voltage, 2, 2)
        lyt_txt.addWidget(le_bat_voltage, 2, 3)
        lyt_txt.addWidget(lbl_ld_voltage, 3, 2)
        lyt_txt.addWidget(le_ld_voltage, 3, 3)
        lyt_txt.addWidget(lbl_bat_current, 4, 2)
        lyt_txt.addWidget(le_bat_current, 4, 3)
        lyt_txt.setAlignment(Qt.AlignTop)
        wgt_txt.setLayout(lyt_txt)
        
        # graph tab
        wgt_graph = pg.MultiPlotWidget()
        wgt_graph.addScrollBarWidget(QScrollBar(), Qt.AlignRight)
        mitm_plt = wgt_graph.mPlotItem
        a = np.ones((8,1))
        a[0,:] = 1
        a[1,:] = 2
        a[2,:] = 3
        a[3,:] = 4
        a[4,:] = 5
        a[5,:] = 6
        col_info = [{"name": f"Battery Voltage", "units": "V"},
                    {"name": "Load Current", "units": "A"}]
        col_info += list({ "units": "V", "name": f"Cell {a}"} for a in range(1, 7))
        info = [{"name": "BatteryData", "cols": col_info}]
        info.append({"name": "Time", "units": "sec", "values": list(range(1))})
        a = MetaArray(a, info=info)
        # print(a)
        mitm_plt.plot(a)
        self.plot = {mitm_plt.plots[i][0].getAxis("left").labelText: mitm_plt.plots[i][0].curves[0] for i in range(8)}
        
        self.wgt_tab.addTab(wgt_txt, "text")
        self.wgt_tab.addTab(wgt_graph, "graph")
        lyt_main.addWidget(self.wgt_tab)
        
        wgt_main.setLayout(lyt_main)
        self.setCentralWidget(wgt_main)
        self.show()
        
    def update(self, key: str, t: float, val: float):
        if self.wgt_tab.currentIndex() == 0: # text
            if key in self.le_voltages.keys():
                self.le_voltages[key].setText(f"{val:.3f}")
            else:
                print(f"text key \"{key}\" not found")
        elif self.wgt_tab.currentIndex() == 1: # graph
            if key in self.plot.keys():
                data = self.plot[key].getData()
                print(data[0].shape)
                x = data[0].tolist()
                y = data[1].tolist()
                x.append(t)
                y.append(val)
                if x[-1] - x[0] > 100:
                    x.pop(0)
                    y.pop(0)
                self.plot[key].setData(x, y)
            else:
                print(f"graph key \"{key}\" not found")
        else:
            print("heeeeelp")



if __name__ == "__main__":
    app = QApplication()
    window = BMSWindow()
    sys.exit(app.exec_())
    
    
