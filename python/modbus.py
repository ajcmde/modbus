#
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
# 
# For more information, please refer to <https://unlicense.org>
#

import socket
import struct
from collections import namedtuple
from sunspec_specification import SunSpec_Specification

# https://github.com/sunspec/models/blob/master/json/model_1.json

# PLANTUML 
# @startuml
# class SolarEdge << T, #FF7700 >> {
#   -SmartMeter()
#   -Battery()
#   -GridProtectionTripLimits()
# }

# class SunSpec << T, #FF7700 >> {  
#   -__sunspec_adresses
#   -__sunspec_blocks_cache
# --
#   +ReadBlock()
# ..
#   +SunSpec()
# }

# class SunSpec_Specification << T, #FF7700 >> {
#   -Specification
# }

# class modbus << T, #FF7700 >> {
#   -__unpack_invalid
#   -__unpack_size
# --
#   +__unpack_from
#   +__req_uint16
#   +__res_bytes
#   +__res_string
#   +__read_register_req()
#   +__read_register_res()
# ..
#   +ReadRegister()
#   +tcp_send()
#   +tcp_recv()
#   +tcp_connect()
#   +tcp_close()
# }

# SolarEdge <|-- SunSpec
# SunSpec <|-- modbus
# SunSpec <|-- SunSpec_Specification  

# hide empty members
# @enduml

class Modbus:
    # transforms the Value (uint16) to a list of bytes in modbus byte order.
    def __req_uint16(self, Value):
        return [(Value >> 8) & 0xFF, Value & 0xFF]   # high byte, low byte

    # transforms the byte message to a list of bytes.
    # if the message is empty or None, it returns None
    def __res_bytes(self, Message):
        if Message is None or len(Message) == 0:
            return None
        for i in range(0, len(Message), 2):
            Message[i], Message[i + 1] = Message[i + 1], Message[i]
        return bytes(Message)
    
    # transforms the byte message to a string. the end of string is marked by a 0 byte or the end of the message.
    # if the message is empty or None, it returns None
    def __res_string(self, Message):
        if Message is None or len(Message) == 0:
            return None
        Result = ""
        for i in range(0, len(Message)):
            if Message[i] == 0:
                break
            Result += chr(Message[i])
        return Result

    __unpack_invalid = { "f": struct.unpack("f", bytes([255, 255, 127, 255]))[0], "h": -32768, "H": 0xffff, "l":-2147483648, "L": 0xffffffff, "q": -9223372036854775808, "Q": 0xffffffffffffffff }
    __unpack_size = { "f": 4, "h": 2, "H": 2, "l": 4, "L": 4, "q": 8, "Q": 8, "s": 1, "x": 1, " ": 0 }
    # @brief decodes the byte message based on the format string
    # format: ([n]{s|c|f|h|H|l|L|q|Q})+    
    # if n is not specified, it defaults to 1
    def __unpack_from(self, format, message):
        result = []
        while len(format) > 0:
            n = 0

            # decode number modifier
            while len(format) > 0 and format[0] >= '0' and format[0] <= '9':
                n = n * 10 + int(format[0])
                format = format[1:]
            if n == 0:
                # apply default length modifier
                n = 1

            # determine the size of the data type (same logic as in struct.unpack)
            nsize = self.__unpack_size.get(format[0])
            if nsize is None:
                raise ValueError("unknown format: " + format[0:])
            invalid = self.__unpack_invalid.get(format[0])

            if format[0] == 's':
                if message[1] == 0x80: # emtpy string
                    result.append("")
                else:
                    result.append(self.__res_string(self.__res_bytes(message[0:n])))
            elif format[0] == ' ' or format[0] == 'x':
                # ignore blanks and padding (registers)
                pass
            else:
                # unpack data
                result_ = list(struct.unpack(str(n) + format[0], bytes(message)[0:n*nsize]))
                for i in range(0, len(result_)):
                    if result_[i] == invalid:
                        result_[i] = None
                result += result_
            # next message chunk
            format = format[1:]
            message = message[n*nsize:]
        return result

    # @brief creates a modbus read register request message
    # @param MessageId: message ID (uint16)
    # @param UnitId: unit ID (uint8)
    # @param Address: register address (uint16)
    # @param Length: number of registers (uint16)
    def __read_register_req(self, MessageId: int, UnitId: int, Address: int, Length: int):
        message = []
        message += self.__req_uint16(MessageId)     # message ID
        message += self.__req_uint16(0)             # protocol ID  
        message.append(0x00)                        # message length (high)
        message.append(0x06)                        # message length (low)
        message.append(UnitId)                      # unit ID 
        message.append(3)                           # function code
        message += self.__req_uint16(Address)       # register address  
        message += self.__req_uint16(Length)        # number of registers   
        return message    

    # @brief: decodes the modbus read register response message
    # @param Message: message (byte array)
    # @param expected message ID (uint16)
    # @param UnitId: unit ID (uint8)
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
    # @brief Reads a registers from the device defined by the Format string. returns a dictionary with the labels as keys and the register 
    # register values as values.
    # @param UnitId: the unit ID of the device
    # @param Address: the address of the register to read
    # @param Format: the format string to decode the register value
    # @param Labels: the labels for the register values
    def ReadRegister(self, UnitId, Address, Format, Labels):
        formatsize = struct.calcsize(Format) >> 1
        messageId = 0x1248
        result = []

        # if the format is empty, return None
        if formatsize == 0:
            return None
        # split the format into chunks of 120 bytes (approx 256 - 9 / 2) as the modbus protocol has a limit 
        # of 256 bytes per message
        while formatsize > 0:
            chunk = formatsize if formatsize < 120 else 120   # approx 256 - 9 / 2
            message = self.__read_register_req(messageId, UnitId, Address, chunk)
            self.s.send(bytes(message))
            message = self.s.recv(300) 
            message = self.__read_register_res(message, messageId, UnitId)
            if message is None:
                return None
            result += message
            formatsize -= chunk
            Address += chunk
        #decode the byte message
        values = self.__unpack_from(Format, result)
        return dict(zip(Labels, values))

        
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

class SunSpec(Modbus, SunSpec_Specification):
    # SunSpec's addresses
    __sunspec_adresses = [0, 40000, 50000]
    # cache for the SunSpec blocks
    __sunspec_blocks_cache = { }
    #   data type for the SunSpec block definition      
    SunSpecBlock = namedtuple("SunSpecBlock", ["BlockId", "Address", "Length"])

    # @ brief Retrieves the SunSpec IDs and the length of the SunSpec blocks
    # the function returns a dictionary with the address as key and a tuple (blocktype, length) as value
    # If no SunSpecAddressId is given the function will iterate over the SunSpec addresses (0, 40000, 50000) 
    # until a valid block is found. 
    # @param Configuration_UnitID: the unit ID of the SunSpec device
    # @param SunSpecAddressId: the ID of the SunSpec block to read (0, 1, 2) 
    def SunSpec(self, Configuration_UnitID, SunSpecAddressId = -1):
        if SunSpecAddressId == -1:
            # if no SunSpecAddressId is given, iterate over the SunSpec addresses
            for i in range(0, len(self.__sunspec_adresses)):
                result = self.SunSpec(Configuration_UnitID, self.__sunspec_adresses[i])
                if result is not None:
                    return result
            return None
        
        if SunSpecAddressId < 0 or SunSpecAddressId >= len(self.__sunspec_adresses):
            # SunSpecAddressId is out of range
            return None
        if not self.__sunspec_blocks_cache.get(Configuration_UnitID) is None:
            # return the cached result
            return self.__sunspec_blocks_cache[Configuration_UnitID]; 
    
        Address = self.__sunspec_adresses[SunSpecAddressId]
        message = self.ReadRegister(Configuration_UnitID, Address, "L", ("C_SunSpec_ID", ))
        if message is None:
            # stop if the message is None
            return None
        # the message must contain the SunSpec ID
        sunspec = message["C_SunSpec_ID"]
        if sunspec != 1850954613:
            return None
        Address += 2
        
        result = []
        # process all SunSpec blocks until the end
        while Address < 0x10000:
            message = self.ReadRegister(Configuration_UnitID, Address, "HH", ("C_SunSpec_DID", "C_SunSpec_Length"))

            BlockId = message["C_SunSpec_DID"]
            Length =  message["C_SunSpec_Length"]
            if Length == 0 or BlockId == 0xffff:
                # end block reached
                break
            result.append(self.SunSpecBlock(BlockId, Address, Length))
            Address += Length + 2

        if(self.__sunspec_blocks_cache.get(Configuration_UnitID) is None):
            # add block list to cache
            self.__sunspec_blocks_cache[Configuration_UnitID] = result
        return result

    # @brief reads a SunSpec block for the given UnitId and Address.
    # @param UnitId: the unit ID of the SunSpec device
    # @param Address: the address of the SunSpec block
    # @param BlockId: ID of the SunSpec block; specifies the SunSpec specification to use
    def ReadBlock(self, UnitId, Address, BlockId):
        BlockDef = SunSpec_Specification.Specification.get(BlockId)
        if BlockDef is None:
            return None
        return self.ReadRegister(UnitId, Address, BlockDef[1], list(map(lambda item: BlockDef[0] + "_" + item, BlockDef[2])))
   
class SolarEdge(SunSpec):
    # @brief reads the SolarEdge SmartMeter data for the given UnitId and SmartMeterId.
    # @param UnitId: the unit ID of the SolarEdge device
    # @apram SmartMeterId: 1, 2 or 3
    def SmartMeter(self, UnitId, SmartMeterId):
        if SmartMeterId < 1 or SmartMeterId > 3:
            return None
        Address = (40121, 40295, 40469)[SmartMeterId - 1]
        block = self.ReadRegister(UnitId, Address, 
            "HH 32s32s16s16s32sH 4x 5h 9h 2h 5h 5h 5h 5h 8Lh 8Lh 16Lh H",  
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
     
    # @brief reads the SolarEdge Battery data for the given UnitId and BatteryId.
    # @param UnitId: the unit ID of the SolarEdge device
    # @apram BatteryId: 1 or 2
    def Battery(self, UnitId, BatteryId):
        if BatteryId < 1 or BatteryId > 2:
            return None
        Address = (0xE100, 0xE200)[BatteryId - 1]
        block1 = self.ReadRegister(UnitId, Address, 
            "32s32s32s32sH",  
            ("C_Manufacturer", "C_Model", "C_Version", "C_SerialNumber", "C_DeviceAddress"))
        if block1["C_Manufacturer"] == "":
            return None
        block2 = self.ReadRegister(UnitId, Address + 0x42, 
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

    # @brief reads the SolarEdge Grid Protection Trip Limits data for the given UnitId.
    # @param UnitId: the unit ID of the SolarEdge device
    def GridProtectionTripLimits(self, UnitId):
        Address = 0xF602
        block = self.ReadRegister(UnitId, Address, 
            "fLfLfLfLfL fLfLfLfLfL fLfLfLfLfL fLfLfLfLfL L",  
            ("VgMax1", "VgMax1_HoldTime", "VgMax2", "VgMax2_HoldTime", "VgMax3", "VgMax3_HoldTime", "VgMax4", "VgMax4_HoldTime", "VgMax5", "VgMax5_HoldTime",
            "VgMin1", "VgMin1_HoldTime", "VgMin2", "VgMin2_HoldTime", "VgMin3", "VgMin3_HoldTime", "VgMin4", "VgMin4_HoldTime", "VgMin5", "VgMin5_HoldTime",
            "FgMax1", "FgMax1_HoldTime", "FgMax2", "FgMax2_HoldTime", "FgMax3", "FgMax3_HoldTime", "FgMax4", "FgMax4_HoldTime", "FgMax5", "FgMax5_HoldTime",    
            "FgMin1", "FgMin1_HoldTime", "FgMin2", "FgMin2_HoldTime", "FgMin3", "FgMin3_HoldTime", "FgMin4", "FgMin4_HoldTime", "FgMin5", "FgMin5_HoldTime",
            "GRM_Time" ))
        return block

