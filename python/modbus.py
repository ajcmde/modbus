import socket
import struct


# https://github.com/sunspec/models/blob/master/json/model_1.json


class Modbus:
    # transforms the Value (uint16) to a list of bytes in modbus byte order.
    def _req_uint16(self, Value):
        return [(Value >> 8) & 0xFF, Value & 0xFF]   # high byte, low byte

    # transforms the byte message to a list of bytes.
    # if the message is empty or None, it returns None
    def _res_bytes(self, Message):
        if Message is None or len(Message) == 0:
            return None
        for i in range(0, len(Message), 2):
            Message[i], Message[i + 1] = Message[i + 1], Message[i]
        return bytes(Message)
    
    # transforms the byte message to a string. the end of string is marked by a 0 byte or the end of the message.
    # if the message is empty or None, it returns None
    def _res_string(self, Message):
        if Message is None or len(Message) == 0:
            return None
        Result = ""
        for i in range(0, len(Message)):
            if Message[i] == 0:
                break
            Result += chr(Message[i])
        return Result

    __unpack_invalid = { "f": struct.unpack("f", bytes([255, 255, 127, 255]))[0], "h": -32768, "H": 0xffff, "L": 0xffffffff, "Q": 0xffffffffffffffff }
    __unpack_size = { "f": 4, "h": 2, "H": 2, "L": 4, "Q":8, "s": 1, "x": 1, " ": 0 }
    # decodes the byte message based on the format string
    # format: [n]s|c|f|h|H|L|Q    
    # if n is not specified, it defaults to 1
    def unpack_from(self, format, message):
        result = []
        while len(format) > 0:
            n = 0

            while len(format) > 0 and format[0] >= '0' and format[0] <= '9':
                n = n * 10 + int(format[0])
                format = format[1:]
            if n == 0:
                n = 1

            nsize = self.__unpack_size.get(format[0])
            if nsize is None:
                raise ValueError("unknown format: " + format[0:])
            invalid = self.__unpack_invalid.get(format[0])

            if format[0] == 's':
                # @@@ todp: empty strings start with 0x80
                result.append(self._res_string(self._res_bytes(message[0:n])))
            elif format[0] == ' ' or format[0] == 'x':
                pass
            else:
                result_ = list(struct.unpack(str(n) + format[0], bytes(message)[0:n*nsize]))
                for i in range(0, len(result_)):
                    if result_[i] == invalid:
                        result_[i] = None
                result += result_
            
            format = format[1:]
            message = message[n*nsize:]
        return result

    # creates a modbus read register request message
    # MessageId: message ID (uint16)
    # UnitId: unit ID (uint8)
    # Address: register address (uint16)
    # Length: number of registers (uint16)
    def __read_register_req(self, MessageId: int, UnitId: int, Address: int, Length: int):
        message = []
        message += self._req_uint16(MessageId)     # message ID
        message += self._req_uint16(0)             # protocol ID  
        message.append(0x00)                        # message length (high)
        message.append(0x06)                        # message length (low)
        message.append(UnitId)                      # unit ID 
        message.append(3)                           # function code
        message += self._req_uint16(Address)       # register address  
        message += self._req_uint16(Length)        # number of registers   
        return message    

    # decodes the modbus read register response message
    # Message: message (byte array)
    # expected message ID (uint16)
    # UnitId: unit ID (uint8)
    def __read_register_res(self, Message, MessageId: int, UnitId: int):
        if len(Message) < 9:
            return None
        if (Message[0] << 8) + Message[1] != MessageId: # message ID
            return None
        if Message[2] != 0x00 or Message[3] != 0x00: # protocol ID
            return None
        messageLength = (Message[4] << 8) + Message[5]
        if messageLength != len(Message) - 6:        # message length
            return None 
        if Message[6] != UnitId:                    # unit ID
            return None
        if Message[7] != 3:                         # function code 
            return None
        dataLength = Message[8]
        if dataLength + 3 > messageLength:         # data length
            return None 
        Message = Message[9:]
        ## swap high and low byte
        result = []
        for i in range(0, len(Message), 2):
            result.append(Message[i + 1])
            result.append(Message[i])
        return result


    # @@@ todo enable tcp/rs485/... mode
    def read_register(self, UnitId, Address, Format, Labels):
        formatsize = struct.calcsize(Format) >> 1

        messageId = 0x1248
        if formatsize == 0:
            return None
        try:
            result = []
            while formatsize > 0:
                chunk = formatsize if formatsize < 120 else 120   # approx 256 - 9 / 2
                message = self.__read_register_req(messageId, UnitId, Address, chunk)
                self.s.send(bytes(message))
                message = self.s.recv(512) 
                message = self.__read_register_res(message, messageId, UnitId)
                if message is None:
                    return None
                result += message
                formatsize -= chunk
                Address += chunk
            values = self.unpack_from(Format, result)
            return dict(zip(Labels, values))
        except:
            return None


    def tcp_send(self, Message):
        self.s.send(bytes(Message))

    def tcp_recv(self, Length):
        return self.s.recv(Length)

    def tcp_connect(self, ip, port, timeout):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((ip, port))
        self.s.settimeout(timeout)

    def tcp_close(self):
        self.s.close()
        self.s = None


class SunSpec(Modbus):
    __sunspec_adresses = [0, 40000, 50000]
    # retrieves the SunSpec IDs and the length of the SunSpec blocks
    # the function returns a dictionary with the address as key and a tuple (blocktype, length) as value
    # the blocktype is the SunSpec ID and the length is the length of the block in bytes
    # the function returns None if the SunSpecAddress (0, 40000, 50000) is not found or no valid block is found
    # the function will iterate over the SunSpec addresses (0, 40000, 50000) until a valid block is found if -1 is passed as SunSpecAddressId
    def SunSpec(self, Configuration_UnitID, SunSpecAddressId = -1):
        if SunSpecAddressId == -1:
            for i in range(0, len(self.__sunspec_adresses)):
                result = self.SunSpec(Configuration_UnitID, self.__sunspec_adresses[i])
                if result is not None:
                    return result
            return None
        
        if SunSpecAddressId < 0 or SunSpecAddressId >= len(self.__sunspec_adresses):
            return None
        result = { }
        Address = self.__sunspec_adresses[SunSpecAddressId]
        message = self.read_register(Configuration_UnitID, Address, "L", ("C_SunSpec_ID", ))
        if message  is None:
            return None
        sunspec = message["C_SunSpec_ID"]
        if sunspec != 1850954613:
            return None

        Address += 2
        while Address < 0x10000:
            message = self.read_register(Configuration_UnitID, Address, "HH", ("C_SunSpec_DID", "C_SunSpec_Length"))

            blocktype = message["C_SunSpec_DID"]
            length =  message["C_SunSpec_Length"]
            if length == 0 or blocktype == 0xffff:
                break
            result[Address] = (blocktype, length)
            Address += length + 2
        return result
    
    # SunSpec DER701: DER AC Measurement
    def DER701(self, Configuration_UnitID):
        Address = 40295
        block = self.read_register(Configuration_UnitID, Address, "HH HHHHLL hhhHh HHLQQQQ 9hH  hHHQQQQhhhHhHH4QhhhHhHH4QHL6h  4h16s", 
            ("DERMeasureAC_ID", "DERMeasureAC_L", 
            "DERMeasureAC_ACType", "DERMeasureAC_St", "DERMeasureAC_InvSt", "DERMeasureAC_ConnSt",  "DERMeasureAC_Alrm", 
            "DERMeasureAC_DERMode", "DERMeasureAC_W",  "DERMeasureAC_VA", "DERMeasureAC_Var", "DERMeasureAC_PF", 
            "DERMeasureAC_A", "DERMeasureAC_LLV", "DERMeasureAC_LNV", "DERMeasureAC_Hz",  "DERMeasureAC_TotWhInj", 
            "DERMeasureAC_TotWhAbs", "DERMeasureAC_TotVarhInj", "DERMeasureAC_TotVarhAbs", "DERMeasureAC_TmpAmb", "DERMeasureAC_TmpCab", 
            "DERMeasureAC_TmpSnk", "DERMeasureAC_TmpTrns", "DERMeasureAC_TmpSw", "DERMeasureAC_TmpOt", "DERMeasureAC_WL1", 
            "DERMeasureAC_VAL1", "DERMeasureAC_VarL1", "DERMeasureAC_PFL1",
            "DERMeasureAC_AL1", "DERMeasureAC_VL1L2", "DERMeasureAC_VL1", "DERMeasureAC_TotWhInjL1", "DERMeasureAC_TotWhAbsL1", 
            "DERMeasureAC_TotVarhInjL1", "DERMeasureAC_TotVarhAbsL1",  "DERMeasureAC_WL2", "DERMeasureAC_VAL2", "DERMeasureAC_VarL2", 
            "DERMeasureAC_PFL2", "DERMeasureAC_AL2", "DERMeasureAC_VL2L3", "DERMeasureAC_VL2", "DERMeasureAC_TotWhInjL2", 
            "DERMeasureAC_TotWhAbsL2", "DERMeasureAC_TotVarhInjL2", "DERMeasureAC_TotVarhAbsL2", "DERMeasureAC_WL3", "DERMeasureAC_VAL3",  
            "DERMeasureAC_VarL3", "DERMeasureAC_PFL3", "DERMeasureAC_AL3", "DERMeasureAC_VL3L1", "DERMeasureAC_VL3", "DERMeasureAC_TotWhInjL3", 
            "DERMeasureAC_TotWhAbsL3", "DERMeasureAC_TotVarhInjL3", "DERMeasureAC_TotVarhAbsL3", "DERMeasureAC_ThrotPct", "DERMeasureAC_ThrotSrc", 
            "DERMeasureAC_A_SF", "DERMeasureAC_V_SF", "DERMeasureAC_Hz_SF", "DERMeasureAC_W_SF", "DERMeasureAC_PF_SF", 
            "DERMeasureAC_VA_SF", "DERMeasureAC_Var_SF", "DERMeasureAC_TotWh_SF", "DERMeasureAC_TotVarh_SF", "DERMeasureAC_Tmp_SF", 
            "DERMeasureAC_MnAlrmInfo" ))
        return block




class SolarEdge(SunSpec):
    def Inverter(self, UnitId):
        Address = 40000
        block1 = self.read_register(UnitId, Address, 
            "LHH 32s32s16x16s32sH" , 
            ("C_SunSpec_ID", "C_SunSpec_DID1", "C_SunSpec_Length1", "C_Manufacturer", "C_Model", "C_Version", "C_SerialNumber", "C_DeviceAddress"))
        Address = 40069 
        block2 = self.read_register(UnitId, Address, 
            "HH HHHHh HHHHHHh Hh Hh hh hh hh Lh Hh Hh hh xxhxxxxh HH",  
            ("C_SunSpec_DID2", "C_SunSpec_Length2", 
                "I_AC_Current", "I_AC_Current_A", "I_AC_Current_B", "I_AC_Current_C", "I_AC_Current_SF",
                "I_AC_VoltageAB", "I_AC_VoltageBC", "I_AC_VoltageCA", "I_AC_VoltageAN", "I_AC_VoltageBN", "I_AC_VoltageCN", "I_AC_Voltage_SF", 
                "I_AC_Power", "I_AC_Power_SF",
                "I_AC_Frequency", "I_AC_Frequency_SF",
                "I_AC_VA", "I_AC_VA_SF",
                "I_AC_VAR", "I_AC_VAR_SF",
                "I_AC_PF", "I_AC_PF_SF",
                "I_AC_Energy_WH", "I_AC_Energy_WH_SF",
                "I_DC_Current", "I_DC_Current_SF",
                "I_DC_Voltage", "I_DC_Voltage_SF",
                "I_DC_Power", "I_DC_Power_SF",
                "I_Temp_Sink", "I_Temp_SF",
                "I_Status", "I_Status_Vendor"))
        return block1 | block2
    

    def SmartMeter(self, UnitId, SmartMeterId):
        # @@@ 3phase inverters
        if SmartMeterId < 1 or SmartMeterId > 3:
            return None
        Address = (40121, 40295, 40469)[SmartMeterId - 1]
        block = self.read_register(UnitId, Address, 
            "HH 32s32s16s16s32sH xxxx 5h 9h 2h 5h 5h 5h 5h 8Lh 8Lh 16Lh H",  
            ("C_SunSpec_DID", "C_SunSpec_Length",
                "C_Manufacturer", "C_Model", "C_Option", "C_Version", "C_SerialNumber", "C_DeviceAddress",
                "M_AC_Current", "M_AC_Current_A", "M_AC_Current_B", "M_AC_Current_C", "M_AC_Current_SF",
                "M_AC_Voltage_L_N", "M_AC_Voltage_A_N", "M_AC_Voltage_B_N", "M_AC_Voltage_C_N", "M_AC_Voltage_L_N", "M_AC_Voltage_A_B", "M_AC_Voltage_B_C", "M_AC_Voltage_A_C", "M_AC_Voltage_SF",
                "M_AC_Freq", "M_AC_Freq_SF",
                "M_AC_Power", "M_AC_Power_A", "M_AC_Power_B", "M_AC_Power_C", "M_AC_Power_SF",
                "M_AC_VA", "M_AC_VA_A", "M_AC_VA_B", "M_AC_VA_C", "M_AC_VA_SF",
                "M_AC_VAR", "M_AC_VAR_A", "M_AC_VAR_B", "M_AC_VAR_C", "M_AC_VAR_SF",
                "M_AC_PF", "M_AC_PF_A", "M_AC_PF_B", "M_AC_PF_C", "M_AC_PF_SF",
                "M_Exported", "M_Exported_A", "M_Exported_B", "M_Exported_C", "M_Imported", "M_Imported_A", "M_Imported_B", "M_Imported_C", "M_Energy_WH_SF",
                "M_Exported_VA", "M_Exported_VA_A", "M_Exported_VA_B", "M_Exported_VA_C", "M_Imported_VA", "M_Imported_VA_A", "M_Imported_VA_B", "M_Imported_VA_C", "M_Energy_VA_SF",
                "M_Import_VARh_Q1", "M_Import_VARh_Q1a", "M_Import_VARh_Q1b", "M_Import_VARh_Q1c", "M_Import_VARh_Q2", "M_Import_VARh_Q2a", "M_Import_VARh_Q2b", "M_Import_VARh_Q2c",
                "M_Import_VARh_Q3", "M_Import_VARh_Q3a", "M_Import_VARh_Q3b", "M_Import_VARh_Q3c", "M_Import_VARh_Q4", "M_Import_VARh_Q4a", "M_Import_VARh_Q4b", "M_Import_VARh_Q4c",
                "M_Import_VAR_SF",
                "M_Events"))
        if block["C_Manufacturer"] == "":
            return None
        return block
    
    
    def Battery(self, UnitId, BatteryId):
        # @@@ 3phase inverters
        if BatteryId < 1 or BatteryId > 2:
            return None
        Address = (0xE100, 0xE200)[BatteryId - 1]
        block1 = self.read_register(UnitId, Address, 
            "32s32s32s32sH",  
            ("C_Manufacturer", "C_Model", "C_Version", "C_SerialNumber", "C_DeviceAddress"))
        if block1["C_Manufacturer"] == "":
            return None
        block2 = self.read_register(UnitId, Address + 0x42, 
            "5f 64x 5f QQ 4f LL 8H8H",  
            ("RatedEnergy", "MaxChargeContinuesPower", "MaxDischargeContinuesPower", "MaxChargePeakPower", "MaxDischargePeakPower",
                "AverageTemperature", "MaxTemperature", "InstantaneousVoltage", "InstantaneousCurrent", "InstantaneousPower",
                "LifetimeExportEnergyCounter", "LifetimeImportEnergyCounter",
                "MaxEnergy", "AvailableEngergy", "StateOfHealth", "StateOfEnergy",
                "Status", "StatusInternal", "EventLog0", 
                "EventLog1", "EventLog2", "EventLog3", "EventLog4", "EventLog5", "EventLog6", "EventLog7",
                "EventLogInternal0", "EventLogInternal1", "EventLogInternal2", "EventLogInternal3",
                "EventLogInternal4", "EventLogInternal5", "EventLogInternal6", "EventLogInternal7"))
        return block1 | block2

    def GridProtectionTripLimits(self, UnitId):
        Address = 0xF602
        block = self.read_register(UnitId, Address, 
            "fLfLfLfLfL fLfLfLfLfL fLfLfLfLfL fLfLfLfLfL L",  
            ("VgMax1", "VgMax1_HoldTime", "VgMax2", "VgMax2_HoldTime", "VgMax3", "VgMax3_HoldTime", "VgMax4", "VgMax4_HoldTime", "VgMax5", "VgMax5_HoldTime",
            "VgMin1", "VgMin1_HoldTime", "VgMin2", "VgMin2_HoldTime", "VgMin3", "VgMin3_HoldTime", "VgMin4", "VgMin4_HoldTime", "VgMin5", "VgMin5_HoldTime",
            "FgMax1", "FgMax1_HoldTime", "FgMax2", "FgMax2_HoldTime", "FgMax3", "FgMax3_HoldTime", "FgMax4", "FgMax4_HoldTime", "FgMax5", "FgMax5_HoldTime",    
            "FgMin1", "FgMin1_HoldTime", "FgMin2", "FgMin2_HoldTime", "FgMin3", "FgMin3_HoldTime", "FgMin4", "FgMin4_HoldTime", "FgMin5", "FgMin5_HoldTime",
            "GRM_Time" ))
        return block

