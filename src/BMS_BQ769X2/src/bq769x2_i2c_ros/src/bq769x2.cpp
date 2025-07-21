#include "i2c/i2c.h"
#include "bq769x2_i2c_ros/BQ769x2Header.h"
#include "bq769x2_i2c_ros/bq769x2.hpp"



BQ769x2::BQ769x2(const char* bus_device)
{
    int bus;
	if((bus = i2c_open(bus_device))== -1) {
		this->i2c_rw_status=-1;
	}
    memset(&device, 0, sizeof(device));
    i2c_init_device(&device);
    device.bus = bus;
	device.addr = 0x08;
	device.delay = 0;
	device.page_bytes = 8;
	device.iaddr_bytes = 1;

    this->crc_mode = false;
}


void BQ769x2::CopyArray(uint8_t *source, uint8_t *dest, uint8_t count){
    uint8_t copyIndex = 0;
    for (copyIndex = 0; copyIndex < count; copyIndex++)
    {
        dest[copyIndex] = source[copyIndex];
    }
}


unsigned char BQ769x2::Checksum(unsigned char *ptr, unsigned char len){
    unsigned char i;
	unsigned char checksum = 0;

	for(i=0; i<len; i++)
		checksum += ptr[i];

	checksum = 0xff & ~checksum;

	return(checksum);
}


unsigned char BQ769x2::CRC8(unsigned char *ptr, unsigned char len){
    unsigned char i;
	unsigned char crc=0;
	while(len--!=0)
	{
		for(i=0x80; i!=0; i/=2)
		{
			if((crc & 0x80) != 0)
			{
				crc *= 2;
				crc ^= 0x107;
			}
			else
				crc *= 2;

			if((*ptr & i)!=0)
				crc ^= 0x107;
		}
		ptr++;
	}
	return(crc);
}


void BQ769x2::I2C_WriteReg(uint8_t reg_addr, uint8_t *reg_data, uint8_t count){
    uint8_t TX_Buffer [10] = {0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00};
    if(this->crc_mode) {
		uint8_t crc_count = 0;
		crc_count = count * 2;
		uint8_t crc1stByteBuffer [3] = {0x10, reg_addr, reg_data[0]};
		unsigned int j;
		unsigned int i;
		uint8_t temp_crc_buffer [3];

		TX_Buffer[0] = reg_data[0];
		TX_Buffer[1] = CRC8(crc1stByteBuffer,3);

		j = 2;
		for(i=1; i<count; i++)
		{
			TX_Buffer[j] = reg_data[i];
			j = j + 1;
			temp_crc_buffer[0] = reg_data[i];
			TX_Buffer[j] = CRC8(temp_crc_buffer,1);
			j = j + 1;
		}
		this->i2c_rw_status = i2c_write(&device, reg_addr, TX_Buffer, crc_count);
	}
    else {
        this->i2c_rw_status = i2c_write(&device, reg_addr, reg_data, count);
    }
}


void BQ769x2::I2C_ReadReg(uint8_t reg_addr, uint8_t *reg_data, uint8_t count){
    unsigned int RX_CRC_Fail = 0;  // reset to 0. If in CRC Mode and CRC fails, this will be incremented.
	uint8_t RX_Buffer [10] = {0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00};
    if(this->crc_mode) {
		uint8_t crc_count = 0;
		uint8_t ReceiveBuffer [10] = {0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00};
		crc_count = count * 2;
		unsigned int j;
		unsigned int i;
		unsigned char CRCc = 0;
		uint8_t temp_crc_buffer [3];

		// HAL_I2C_Mem_Read(&hi2c1, DEV_ADDR, reg_addr, 1, ReceiveBuffer, crc_count, 1000);
		this->i2c_rw_status = i2c_read(&device, reg_addr, ReceiveBuffer, crc_count);
		uint8_t crc1stByteBuffer [4] = {0x10, reg_addr, 0x11, ReceiveBuffer[0]};
		CRCc = CRC8(crc1stByteBuffer,4);
		if (CRCc != ReceiveBuffer[1])
		{
			RX_CRC_Fail += 1;
		}
		RX_Buffer[0] = ReceiveBuffer[0];

		j = 2;
		for (i=1; i<count; i++)
		{
			RX_Buffer[i] = ReceiveBuffer[j];
			temp_crc_buffer[0] = ReceiveBuffer[j];
			j = j + 1;
			CRCc = CRC8(temp_crc_buffer,1);
			if (CRCc != ReceiveBuffer[j])
				RX_CRC_Fail += 1;
			j = j + 1;
		}
		CopyArray(RX_Buffer, reg_data, crc_count);
	}
    else{
	    this->i2c_rw_status = i2c_read(&device, reg_addr, reg_data, count);
    }
}


void BQ769x2::BQ769x2_ReadVoltage(uint8_t command){
	DirectCommands(command, 0x00, R);
}


void BQ769x2::BQ769x2_ReadTemperature(uint8_t command){
    DirectCommands(command, 0x00, R);
	//RX_data is a global var
	// return (0.1 * (float)(RX_data[1]*256 + RX_data[0])) - 273.15;  // converts from 0.1K to Celcius
}


void BQ769x2::BQ769x2_ReadRAMRegister(uint16_t reg_addr, uint8_t datalen){
	uint8_t TX_Buffer[2] = {0x00, 0x00};
	TX_Buffer[0] = reg_addr & 0xFF;
	TX_Buffer[1] = (reg_addr >> 8) & 0xFF;
	I2C_WriteReg(0x3E, TX_Buffer, 2);
	usleep(1000);
	I2C_ReadReg(0x40, RX_32Byte, datalen);
	printf("read from 0x%04x : 0x", reg_addr);
	for(int i=0; i<datalen; ++i){
		printf("%02x", RX_32Byte[datalen-i-1]);
	}
	printf("\n");
}


void BQ769x2::BQ769x2_SetRegister(uint16_t reg_addr, uint32_t reg_data, uint8_t datalen){
    uint8_t TX_Buffer[2] = {0x00, 0x00};
	uint8_t TX_RegData[6] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00};

	//TX_RegData in little endian format
	TX_RegData[0] = reg_addr & 0xff; 
	TX_RegData[1] = (reg_addr >> 8) & 0xff;
	TX_RegData[2] = reg_data & 0xff; //1st byte of data

	switch(datalen)
    {
		case 1: //1 byte datalength
      		I2C_WriteReg(0x3E, TX_RegData, 3);
			// delayUS(2000);
			TX_Buffer[0] = Checksum(TX_RegData, 3); 
			TX_Buffer[1] = 0x05; //combined length of register address and data
      		I2C_WriteReg(0x60, TX_Buffer, 2); // Write the checksum and length
			// delayUS(2000);
			break;
		case 2: //2 byte datalength
			TX_RegData[3] = (reg_data >> 8) & 0xff;
			I2C_WriteReg(0x3E, TX_RegData, 4);
			// delayUS(2000);
			TX_Buffer[0] = Checksum(TX_RegData, 4); 
			TX_Buffer[1] = 0x06; //combined length of register address and data
      		I2C_WriteReg(0x60, TX_Buffer, 2); // Write the checksum and length
			// delayUS(2000);
			break;
		case 4: //4 byte datalength, Only used for CCGain and Capacity Gain
			TX_RegData[3] = (reg_data >> 8) & 0xff;
			TX_RegData[4] = (reg_data >> 16) & 0xff;
			TX_RegData[5] = (reg_data >> 24) & 0xff;
			I2C_WriteReg(0x3E, TX_RegData, 6);
			// delayUS(2000);
			TX_Buffer[0] = Checksum(TX_RegData, 6); 
			TX_Buffer[1] = 0x08; //combined length of register address and data
      		I2C_WriteReg(0x60, TX_Buffer, 2); // Write the checksum and length
			// delayUS(2000);
			break;
    }
}


void BQ769x2::CommandSubcommands(uint16_t command){
    uint8_t TX_Reg[2] = {0x00, 0x00};

	//TX_Reg in little endian format
	TX_Reg[0] = command & 0xff;
	TX_Reg[1] = (command >> 8) & 0xff;

	I2C_WriteReg(0x3E,TX_Reg,2); 
}


void BQ769x2::Subcommands(uint16_t command, uint16_t data, uint8_t type){
    //security keys and Manu_data writes dont work with this function (reading these commands works)
	//max readback size is 32 bytes i.e. DASTATUS, CUV/COV snapshot
	uint8_t TX_Reg[4] = {0x00, 0x00, 0x00, 0x00};
	uint8_t TX_Buffer[2] = {0x00, 0x00};

	//TX_Reg in little endian format
	TX_Reg[0] = command & 0xff;
	TX_Reg[1] = (command >> 8) & 0xff; 

	if (type == R) {//read
		I2C_WriteReg(0x3E,TX_Reg,2);
		I2C_ReadReg(0x40, RX_32Byte, 32); //RX_32Byte is a global variable
	}
	else if (type == W) {
		//FET_Control, REG12_Control
		TX_Reg[2] = data & 0xff; 
		I2C_WriteReg(0x3E,TX_Reg,3);
		TX_Buffer[0] = Checksum(TX_Reg, 3);
		TX_Buffer[1] = 0x05; //combined length of registers address and data
		I2C_WriteReg(0x60, TX_Buffer, 2);
	}
	else if (type == W2){ //write data with 2 bytes
		//CB_Active_Cells, CB_SET_LVL
		TX_Reg[2] = data & 0xff; 
		TX_Reg[3] = (data >> 8) & 0xff;
		I2C_WriteReg(0x3E,TX_Reg,4);
		TX_Buffer[0] = Checksum(TX_Reg, 4); 
		TX_Buffer[1] = 0x06; //combined length of registers address and data
		I2C_WriteReg(0x60, TX_Buffer, 2);
	}
}



void BQ769x2::DirectCommands(uint8_t command, uint16_t data, uint8_t type){
    //type: R = read, W = write
	uint8_t TX_data[2] = {0x00, 0x00};

	//little endian format
	TX_data[0] = data & 0xff;
	TX_data[1] = (data >> 8) & 0xff;

	if (type == R) {//Read
		I2C_ReadReg(command, RX_data, 2); //RX_data is a global variable
	}
	if (type == W) {//write
    //Control_status, alarm_status, alarm_enable all 2 bytes long
		I2C_WriteReg(command,TX_data,2);
	}
}


void BQ769x2::BQ769x2_ReadFETStatus(){
    /* TODO: Correct Processing */
    // Read FET Status to see which FETs are enabled
	DirectCommands(FETStatus, 0x00, R);
	// FET_Status = (RX_data[1]*256 + RX_data[0]);
	// DSG = ((0x4 & RX_data[0])>>2);// discharge FET state
  	// CHG = (0x1 & RX_data[0]);// charge FET state
  	// PCHG = ((0x2 & RX_data[0])>>1);// pre-charge FET state
  	// PDSG = ((0x8 & RX_data[0])>>3);// pre-discharge FET state
}


void BQ769x2::BQ769x2_ReadAlarmStatus(){
    /* TODO: Correct Processing */
    DirectCommands(AlarmStatus, 0x00, R);
	bms_state.alarm_status.byte_val[0] = RX_data[0];
	bms_state.alarm_status.byte_val[1] = RX_data[1];
	// return (RX_data[1]*256 + RX_data[0]);
}


void BQ769x2::BQ769x2_ReadSafetyStatus(){
    /* TODO: Correct Processing */
    // Read Safety Status A/B/C and find which bits are set
	// This shows which primary protections have been triggered
	DirectCommands(SafetyStatusA, 0x00, R);
	// value_SafetyStatusA = (RX_data[1]*256 + RX_data[0]);
	// //Example Fault Flags
	// UV_Fault = ((0x4 & RX_data[0])>>2); 
	// OV_Fault = ((0x8 & RX_data[0])>>3);
	// SCD_Fault = ((0x8 & RX_data[1])>>3);
	// OCD_Fault = ((0x2 & RX_data[1])>>1);
	DirectCommands(SafetyStatusB, 0x00, R);
	// value_SafetyStatusB = (RX_data[1]*256 + RX_data[0]);
	DirectCommands(SafetyStatusC, 0x00, R);
	// value_SafetyStatusC = (RX_data[1]*256 + RX_data[0]);
	// if ((value_SafetyStatusA + value_SafetyStatusB + value_SafetyStatusC) > 1) {
	// 	ProtectionsTriggered = 1; }
	// else {
	// 	ProtectionsTriggered = 0; }
}


void BQ769x2::BQ769x2_ReadPFStatus(){
    /* TODO: Correct Processing */
    // Read Permanent Fail Status A/B/C and find which bits are set
	// This shows which permanent failures have been triggered
	DirectCommands(PFStatusA, 0x00, R);
    saved_pf_status.pf_status_a.val = RX_data[0];
	DirectCommands(PFStatusB, 0x00, R);
	saved_pf_status.pf_status_b.val = RX_data[0];
	DirectCommands(PFStatusC, 0x00, R);
	saved_pf_status.pf_status_c.val = RX_data[0];
}


void BQ769x2::BQ769x2_ReadAllVoltages(){
    int cellvoltageholder = Cell1Voltage; //Cell1Voltage is 0x14
    for (int x = 0; x < 16; x++){//Reads all cell voltages
        BQ769x2_ReadVoltage(cellvoltageholder);
        bms_state.CellVoltages[x] = RX_data[1]*256+RX_data[0];
        cellvoltageholder = cellvoltageholder + 2;
    }
    BQ769x2_ReadVoltage(StackVoltage);
    bms_state.Stack_Voltage = 1 * (RX_data[1]*256+RX_data[0]);
    BQ769x2_ReadVoltage(PACKPinVoltage);
    bms_state.Pack_Voltage = 1 * (RX_data[1]*256+RX_data[0]);
    BQ769x2_ReadVoltage(LDPinVoltage);
    bms_state.LD_Voltage = 1 * (RX_data[1]*256+RX_data[0]);
}


void BQ769x2::BQ769x2_ReadCurrent(){
     /* TODO: Correct Processing */
    DirectCommands(CC2Current, 0x00, R);
    bms_state.Current = 10*(RX_data[1]*256 + RX_data[0]);
	// return (RX_data[1]*256 + RX_data[0]);  // current is reported in mA
}


void BQ769x2::BQ769x2_ReadPassQ(){
    Subcommands(DASTATUS6, 0x00, R);
    CopyArray(RX_32Byte, dastatus.dastatus6.byte_value, 32);
	// AccumulatedCharge_Int = ((RX_32Byte[3]<<24) + (RX_32Byte[2]<<16) + (RX_32Byte[1]<<8) + RX_32Byte[0]); //Bytes 0-3
	// AccumulatedCharge_Frac = ((RX_32Byte[7]<<24) + (RX_32Byte[6]<<16) + (RX_32Byte[5]<<8) + RX_32Byte[4]); //Bytes 4-7
	// AccumulatedCharge_Time = ((RX_32Byte[11]<<24) + (RX_32Byte[10]<<16) + (RX_32Byte[9]<<8) + RX_32Byte[8]); //Bytes 8-11
}