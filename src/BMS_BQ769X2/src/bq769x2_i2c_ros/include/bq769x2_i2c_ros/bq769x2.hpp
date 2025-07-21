#pragma once


#include <stdio.h>
#include <iostream>
#include <fstream>
#include <iomanip>
#include <unistd.h> // For usleep
#include <string.h>
#include <sstream>
#include <thread>
#include <chrono>

#include "bq769x2_i2c_ros/BQ769x2Header.h"
#include "i2c/i2c.h"

#include <rclcpp/rclcpp.hpp>

#define R 0  // Read; Used in DirectCommands and Subcommands functions
#define W 1  // Write; Used in DirectCommands and Subcommands functions
#define W2 2 // Write data with two bytes; Used in Subcommands function


class BQ769x2{
    // FUNCTIONS and PROCEDURES
    public:
        BQ769x2(){};
        BQ769x2(const char* bus_device);
        void BQ769x2_ReadRAMRegister(uint16_t reg_addr, uint8_t datalen);
        void BQ769x2_SetRegister(uint16_t reg_addr, uint32_t reg_data, uint8_t datalen);
        void CommandSubcommands(uint16_t command);
        void Subcommands(uint16_t command, uint16_t data, uint8_t type);
        void DirectCommands(uint8_t command, uint16_t data, uint8_t type);
        void BQ769x2_ReadFETStatus();
        void BQ769x2_ReadAlarmStatus();
        void BQ769x2_ReadSafetyStatus();
        void BQ769x2_ReadPFStatus();
        void BQ769x2_ReadAllVoltages();
        void BQ769x2_ReadCurrent();
        void BQ769x2_ReadPassQ();
    private:
        inline void delayUS(uint32_t us){usleep(us);};
        void CopyArray(uint8_t *source, uint8_t *dest, uint8_t count);
        unsigned char Checksum(unsigned char *ptr, unsigned char len);
        unsigned char CRC8(unsigned char *ptr, unsigned char len);
        void I2C_WriteReg(uint8_t reg_addr, uint8_t *reg_data, uint8_t count);
        void I2C_ReadReg(uint8_t reg_addr, uint8_t *reg_data, uint8_t count);
        void BQ769x2_ReadVoltage(uint8_t command);
        void BQ769x2_ReadTemperature(uint8_t command);
    public:
        bool crc_mode;
        int i2c_rw_status;
        struct state_t {
            uint16_t CellVoltages[16];
            uint16_t Stack_Voltage;
            uint16_t LD_Voltage;
            uint16_t Pack_Voltage;
            int16_t Current;
            union {
                uint8_t byte_val[2];
                uint16_t reg_val;
                struct{
                    bool WAKE:1;
                    bool ADSCAN:1;
                    bool CB:1;
                    bool FUSE:1;
                    bool SHUTV:1;
                    bool XDSG:1;
                    bool XCHG:1;
                    bool FULLSCAN:1;
                    bool RSVD:1;
                    bool INITCOMP:1;
                    bool INITSTART:1;
                    bool MSK_PFALERT:1;
                    bool MSK_SFALERT:1;
                    bool PF:1;
                    bool SSA:1;
                    bool SSBC:1;
                } bit_val;
            } alarm_status;
        } bms_state;
    /**
     *  DIRECT COMMANDS Data
     */


    /** 
     *  SUBCOMMANDS with Data
     */
        union device_number_t{
            uint8_t byte_value[2];
            uint16_t device_number;
        } device_number;
        union fw_version_t{
            uint8_t byte_value[6];
            struct {
                uint16_t device_number_be;
                uint16_t fw_version_be;
                uint16_t build_version_be;
            };
        } fw_version;
        union hw_version_t {
            uint8_t byte_value[2];
            uint16_t hw_version;
        } hw_version;
        union irom_sig_t {
            uint8_t byte_value[2];
            uint16_t irom_sig;
        } irom_sig;
        union static_cfg_sig_t {
            uint8_t byte_value[2];
            uint16_t static_cfg_sig;
        } static_cfg_sig;
        union saved_pf_status_t {
            uint8_t byte_value[5];
            struct{
                union {
                    uint8_t val;
                    struct{
                        bool SUV:1;
                        bool SOV:1;
                        bool SOCC:1;
                        bool SOCD:1;
                        bool SOT:1;
                        bool SOTF:1;
                        bool RSVD:1;
                        bool CUDEP:1;
                    };
                }pf_status_a;
                union {
                    uint8_t val;
                    struct{
                        bool CFETF:1;
                        bool DFETF:1;
                        bool LVL2:1;
                        bool VIMR:1;
                        bool VIMA:1;
                        bool RSVD:2;
                        bool SCDL:1;
                    };
                }pf_status_b;
                union {
                    uint8_t val;
                    struct{
                        bool OTPF:1;
                        bool DRMF:1;
                        bool IRMF:1;
                        bool LFOF:1;
                        bool VREF:1;
                        bool VSSF:1;
                        bool HWMX:1;
                        bool CMDF:1;
                    };
                }pf_status_c;
                union {
                    uint8_t val;
                    struct{
                        bool TOSF:1;
                        bool RSVD:7;
                    };
                }pf_status_d;
            };
        }saved_pf_status;
        union manufacturing_status_t {
            uint8_t byte_value[2];
            struct{
                bool PCHG_TEST:1;
                bool CHG_TEST:1;
                bool DSG_TEST:1;
                bool RSVD_0:1;
                bool FET_EN:1;
                bool PDSG_TEST:1;
                bool PF_TEST:1;
                bool OTPW_EN:1;
                uint8_t RSVD_1:8;
            } manufacturing_status;
        } manufacturing_status;
        union manufacturing_data_t {
            uint8_t byte_value[32];
            unsigned char txt[32];
        } manufacturing_data;
        struct dastatus_t{
            union{
                uint8_t byte_value[32];
                struct{
                    int32_t Cell1V_ADCcounts;
                    int32_t Cell1I_ADCcounts;
                    int32_t Cell2V_ADCcounts;
                    int32_t Cell2I_ADCcounts;
                    int32_t Cell3V_ADCcounts;
                    int32_t Cell3I_ADCcounts;
                    int32_t Cell4V_ADCcounts;
                    int32_t Cell4I_ADCcounts;
                };
            } dastatus1;
            union{
                uint8_t byte_value[32];
                struct{
                    int32_t Cell5V_ADCcounts;
                    int32_t Cell5I_ADCcounts;
                    int32_t Cell6V_ADCcounts;
                    int32_t Cell6I_ADCcounts;
                    int32_t Cell7V_ADCcounts;
                    int32_t Cell7I_ADCcounts;
                    int32_t Cell8V_ADCcounts;
                    int32_t Cell8I_ADCcounts;
                };
            } dastatus2;
            union{
                uint8_t byte_value[32];
                struct{
                    int32_t Cell9V_ADCcounts;
                    int32_t Cell9I_ADCcounts;
                    int32_t Cell10V_ADCcounts;
                    int32_t Cell10I_ADCcounts;
                    int32_t Cell11V_ADCcounts;
                    int32_t Cell11I_ADCcounts;
                    int32_t Cell12V_ADCcounts;
                    int32_t Cell12I_ADCcounts;
                };
            } dastatus3;
            union{
                uint8_t byte_value[32];
                struct{
                    int32_t Cell13V_ADCcounts;
                    int32_t Cell13I_ADCcounts;
                    int32_t Cell14V_ADCcounts;
                    int32_t Cell14I_ADCcounts;
                    int32_t Cell15V_ADCcounts;
                    int32_t Cell15I_ADCcounts;
                    int32_t Cell16V_ADCcounts;
                    int32_t Cell16I_ADCcounts;
                };
            } dastatus4;
            union{
                uint8_t byte_value[32];
                struct{
                    int16_t VREG18;
                    int16_t VSS;
                    int16_t MaxCellmV;
                    int16_t MinCellmV;
                    int16_t BatVsum;
                    int16_t CellTemp;
                    int16_t FetTemp;
                    int16_t MaxCellTemp_;
                    int16_t MinCellTemp_;
                    int16_t AvgCellTemp;
                    int16_t CC3Current;
                    int16_t CC1Current;
                    int32_t CC2Counts;
                    int32_t CC3Counts;
                };
            } dastatus5;
            union{
                uint8_t byte_value[32];
                struct{
                    int32_t AccumCharge;
                    uint32_t AccumChargeFraction;
                    uint32_t AccumTime_s;
                    int32_t CFETOFF_Counts;
                    int32_t DFETOFF_Counts;
                    int32_t ALERT_Counts;
                    int32_t TS1_Counts;
                    int32_t TS2_Counts;
                };
            } dastatus6;
            union{
                uint8_t byte_value[32];
                struct{
                    int32_t TS3_Counts;
                    int32_t HDQ_Counts;
                    int32_t DCHG_Counts;
                    int32_t DDSG_Counts;
                    int32_t RSVD[4];
                };
            } dastatus7;
        } dastatus;
        union cuv_snapshot_t {
            uint8_t byte_value[32];
            uint16_t cell_x_voltage_mV_at_cuv_event[16];
        }cuv_snapshot;
        union cov_snapshot_t {
            uint8_t byte_value[32];
            uint16_t cell_x_voltage_mV_at_cov_event[16];
        }cov_snapshot;
        union cb_active_cells_t {
            uint8_t byte_value[2];
            uint16_t value;
            struct {
                bool CELL1:1;
                bool CELL2:1;
                bool CELL3:1;
                bool CELL4:1;
                bool CELL5:1;
                bool CELL6:1;
                bool CELL7:1;
                bool CELL8:1;
                bool CELL9:1;
                bool CELL10:1;
                bool CELL11:1;
                bool CELL12:1;
                bool CELL13:1;
                bool CELL14:1;
                bool CELL15:1;
                bool CELL16:1;
            };
        } cb_active_cells;
        union cb_set_lvl_t {
            uint8_t byte_value[2];
            uint16_t cb_set_lvl_mV;
        } cb_set_lvl;
        struct cb_status_t {
            union {
                uint8_t byte_value[2];
                uint16_t cb_active_time_s;
            }cb_status1;
            union {
                uint8_t byte_value[32];
                struct {
                    uint32_t cell1_cb_active_time_s;
                    uint32_t cell2_cb_active_time_s;
                    uint32_t cell3_cb_active_time_s;
                    uint32_t cell4_cb_active_time_s;
                    uint32_t cell5_cb_active_time_s;
                    uint32_t cell6_cb_active_time_s;
                    uint32_t cell7_cb_active_time_s;
                    uint32_t cell8_cb_active_time_s;
                };
            }cb_status2;
            union {
                uint8_t byte_value[32];
                struct {
                    uint32_t cell9_cb_active_time_s;
                    uint32_t cell10_cb_active_time_s;
                    uint32_t cell11_cb_active_time_s;
                    uint32_t cell12_cb_active_time_s;
                    uint32_t cell13_cb_active_time_s;
                    uint32_t cell14_cb_active_time_s;
                    uint32_t cell15_cb_active_time_s;
                    uint32_t cell16_cb_active_time_s;
                };
            }cb_status3;
        } cb_status;
    private:
        I2CDevice device;
        uint8_t RX_data[2];
        uint8_t RX_32Byte[32];
        
};