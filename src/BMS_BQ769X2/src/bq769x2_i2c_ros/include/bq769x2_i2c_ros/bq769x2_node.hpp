#pragma once

#include <stdio.h>
#include <cmath>
#include <functional>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/battery_state.hpp"

#include "bq769x2_i2c_ros/bq769x2.hpp"

class BQ769x2_Node: public rclcpp::Node {
    public:
        BQ769x2_Node();
    private:
        void timer_callback();
        BQ769x2 bms;
        int cell_interconnect;
        rclcpp::Publisher<sensor_msgs::msg::BatteryState>::SharedPtr pub_bat_state_;
        rclcpp::TimerBase::SharedPtr timer_;
};

