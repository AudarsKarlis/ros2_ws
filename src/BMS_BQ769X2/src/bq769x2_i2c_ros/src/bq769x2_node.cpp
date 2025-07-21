#include <stdio.h>
#include <cmath>
#include <functional>
#include <vector>
#include <string>
#include <chrono>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/battery_state.hpp"

#include "bq769x2_i2c_ros/BQ769x2Header.h"
#include "bq769x2_i2c_ros/bq769x2.hpp"
#include "bq769x2_i2c_ros/bq769x2_node.hpp"

using namespace std::chrono_literals;

BQ769x2_Node::BQ769x2_Node() : Node("bq769x2_node") {
    this->declare_parameter("i2c_bus", "/dev/i2c-7");
    this->declare_parameter("cell_interconnections", 0xFFFF);

    std::string bus = this->get_parameter("i2c_bus").as_string();
    this->cell_interconnect = this->get_parameter("cell_interconnections").as_int();
    RCLCPP_INFO(this->get_logger(), "cell interconnections 0x%04x", this->cell_interconnect);

    this->bms = BQ769x2(bus.c_str());
    bms.BQ769x2_ReadRAMRegister(DefaultAlarmMask, 2);
    this->pub_bat_state_ = this->create_publisher<sensor_msgs::msg::BatteryState>("bat_state", 10);
    this->timer_ = rclcpp::create_timer(this, this->get_clock(), 20ms, std::bind(&BQ769x2_Node::timer_callback, this));
}

void BQ769x2_Node::timer_callback(){
    bms.BQ769x2_ReadAlarmStatus();
    if(bms.bms_state.alarm_status.reg_val & 0x80){
        RCLCPP_INFO(this->get_logger(), "AlarmStatus: 0x%04x", bms.bms_state.alarm_status.reg_val);
        bms.DirectCommands(AlarmStatus, 0x0080, W);  // Clear the FULLSCAN bit
   
        bms.BQ769x2_ReadAllVoltages();
        bms.BQ769x2_ReadCurrent();

        auto msg = sensor_msgs::msg::BatteryState();
        msg.header.stamp = this->get_clock()->now();
        msg.present = true;
        msg.voltage = bms.bms_state.Stack_Voltage*1e-3;
        msg.current = bms.bms_state.Current*1e-3;

        for(int i=0; i<16; ++i)
        {
            // check if cell is used for measurement      or     if standard of 0x0000 is used
            if((this->cell_interconnect & (1<<i))    ||  (this->cell_interconnect==0x0000)){
                msg.cell_voltage.push_back(bms.bms_state.CellVoltages[i]*1e-3);
                msg.cell_temperature.push_back(NAN);
            }
        }
        msg.temperature = NAN;
        msg.charge = NAN;
        msg.design_capacity = NAN;
        msg.percentage = NAN;
        this->pub_bat_state_->publish(msg);
    }
}