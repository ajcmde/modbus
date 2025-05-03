import socket
import struct


class Modbus:
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
            if format[0] == 's':
                result.append(self._res_string(self._res_bytes(message[0:n])))
                message = message[n:]
            elif format[0] == 'f':
                result += struct.unpack(str(n) + "f", bytes(message[0:n*4]))
                message = message[n*4:]
            elif format[0] == 'h':
                result += struct.unpack(str(n) + "h", bytes(message[0:n*2]))
                message = message[n*2:]
            elif format[0] == 'H':
                result += struct.unpack(str(n) + "H", bytes(message[0:n*2]))
                message = message[n*2:]
            elif format[0] == 'L':
                result += struct.unpack(str(n) + "L", bytes(message[0:n*4]))
                message = message[n*4:]
            elif format[0] == 'Q':
                result += struct.unpack(str(n) + "Q", bytes(message[0:n*8]))
                message = message[n*8:]
            elif format[0] == ' ':
                pass
            elif format[0] == 'x':
                message = message[n:]
            else:
                raise ValueError("unknown format: " + format[0:])
            format = format[1:]
        return result


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
#            Message[i], Message[i + 1] = Message[i + 1], Message[i]
            result.append(Message[i + 1])
            result.append(Message[i])
        return result


    # @@@ todo enable tcp/rs485/... mode
    def read_register(self, UnitId, Address, Format, Labels):
        formatsize = struct.calcsize(Format) >> 1

        messageId = 0x1248
        if formatsize == 0:
            return None
        # message = self.modbus_read_register(0x1248, Configuration_UnitID, Address, formatsize)
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
            unpack_from = self.unpack_from(Format, result)
            return dict(zip(Labels, unpack_from))
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
       # @@@ address 50000, address 0
       def SunSpec(self, Configuration_UnitID, Address):
        message = self.read_register(0x1248, Configuration_UnitID, Address, 2)
        sunspec = self._res_uint32(message[0:4])[0]

        if message  is None:
            return None
        if sunspec != 0x53756e53:
            return (None)

        Address = 40002
        while Address != 0xffffffff:
            message = self.read_register(0x100, Configuration_UnitID, Address, 2)

            blocktype = self._res_uint16(message[0:2])[0]
            length = self._res_uint16(message[2:4])[0]
            if length == 0 or blocktype == 0xffff:
                break
            print(Address, "-", Address + length, " (", hex(Address), "-", hex(Address + length), "): blocktype", blocktype, " length", length)
            Address += length + 2


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


