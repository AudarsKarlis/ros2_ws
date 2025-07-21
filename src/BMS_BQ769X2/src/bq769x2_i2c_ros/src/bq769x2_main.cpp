#include <cstdio>
#include "bq769x2_i2c_ros/bq769x2_node.hpp"

int main(int argc, char ** argv)
{
  // (void) argc;
  // (void) argv;
  // BQ769x2 bms = BQ769x2("/dev/i2c-7");
  // if(bms.i2c_rw_status<0)
  // {
  //   printf("failed to open bus");
  //   return -1;
  // }
  // bms.CommandSubcommands(BQ769x2_RESET);
  // if(bms.i2c_rw_status<0)
  // {
  //   printf("failed to reset device");
  //   return -1;
  // }
  // usleep(600000);
  // bms.CommandSubcommands(SET_CFGUPDATE);
	// usleep(500000);
	// bms.BQ769x2_SetRegister(DefaultAlarmMask, 0xF882, 2);
	// usleep(10000);
	// bms.BQ769x2_SetRegister(VCellMode, 0x901F, 2);
	// usleep(10000);
	// int16_t cellgain[6] = {11049, 11117, 12811, 10899, 12280, 13154};
	// int16_t celloffset = -143;
	// bms.BQ769x2_SetRegister(Cell1Gain, cellgain[0], 2);
	// bms.BQ769x2_SetRegister(Cell2Gain, cellgain[1], 2);
	// bms.BQ769x2_SetRegister(Cell3Gain, cellgain[2], 2);
	// bms.BQ769x2_SetRegister(Cell4Gain, cellgain[3], 2);
	// bms.BQ769x2_SetRegister(Cell14Gain, cellgain[4], 2);
	// bms.BQ769x2_SetRegister(Cell16Gain, cellgain[5], 2);
	// bms.BQ769x2_SetRegister(VcellOffset, celloffset, 2);
	// bms.CommandSubcommands(EXIT_CFGUPDATE);
	// usleep(500000);
	// bms.CommandSubcommands(SLEEP_DISABLE);
	// usleep(60000); usleep(60000); usleep(60000); usleep(60000);

  // while (1)
  // {
  //   bms.BQ769x2_ReadAllVoltages();
  //   bms.BQ769x2_ReadCurrent();
  //   std::string tmp;
  //   for(int x=0; x<16; ++x){
  //     tmp += std::to_string(bms.bms_state.CellVoltages[x]) + ", ";
  //   }
  //   tmp += std::to_string(bms.bms_state.Stack_Voltage) + ", ";
  //   tmp += std::to_string(bms.bms_state.Pack_Voltage) + ", ";
  //   tmp += std::to_string(bms.bms_state.LD_Voltage) + ", ";
  //   tmp += std::to_string(bms.bms_state.Current) + '\n';
  //   printf(tmp.c_str());
  //   usleep(200000);
  // }

  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<BQ769x2_Node>());
  rclcpp::shutdown();
  // printf("hello world bq769x2_i2c_ros package\n");
  return 0;
}
