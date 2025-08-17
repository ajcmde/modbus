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
    def __res_words(self, Message):
        if Message is None or len(Message) == 0:
            return None
        for i in range(0, len(Message), 2):
            Message[i], Message[i + 1] = Message[i + 1], Message[i]
        return bytes(Message)  

    # @brief transforms the byte message to a string. the end of string is marked by a 0 byte or the end of the message.
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

    __DefinitionRegister = namedtuple("DefinitionRegister", ["name", "type", "length"])
    __UnpackNotImplemented = {
        "int16": [0x80, 0x00], 
        "uint16": [0xff, 0xff], 
        "acc16": [0x00, 0x00], 
        "enum16": [0xff, 0xff], 
        "bitfield16": [0xff, 0xff], 
        "pad": [0x80, 0x00],
        "int32": [0x80, 0x00, 0x00, 0x00], 
        "uint32": [0xff, 0xff, 0xff, 0xff], 
        "acc32": [0x00, 0x00, 0x00, 0x00], 
        "enum32": [0xff, 0xff, 0xff, 0xff], 
        "bitfield32": [0xff, 0xff, 0xff, 0xff], 
        "int64": [0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], 
        "uint64": [0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff], 
        "acc64" : [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
        "float32": [0xff, 0xff, 0x7f, 0xff],
        "float64": [0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x7f, 0xff],
        "string": [0x00, 0x80],
        "sunssf": [0x80, 0x00], 
        "ipaddr": [0, 0, 0, 0],
        "ipv6addr": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
     }
    __UnpackStructFormat = {
        "int16": "h", "uint16": "H", "acc16": "H", "enum16": "H", "bitfield16": "H", 
        "int32": "i", 
        "uint32": "I", 
        "acc32": "I", "enum32": "I", "bitfield32": "I", 
        "int64": "q", 
        "uint64": "Q", "acc64" : "Q",
        "float32": 'f', 
        "float64": 'd',
        "sunssf": "h",
        "count": "H" 
        # string, ipaddr and, ipv6addr are handled separately
     }    
    
    # @brief decodes the byte message based on the defintion passed in the Format string.
    # @param definition: the format string to decode the message
    # if n is not specified, it defaults to 1
    def __Unpack(self, definition, message):
        result = {}
        for key in definition:
            item_ = self.__DefinitionRegister._make(definition[key])
            item_length = item_.length * 2
            item_notimplemented = self.__UnpackNotImplemented.get(item_.type, None)
            result_ = None
            # print("1. item notimplemented: ", item_notimplemented, " item type: ", item_.type, " message : ", message)
            if item_notimplemented == None or item_notimplemented != message[0:len(item_notimplemented)]:
                try:
                    struct_format = self.__UnpackStructFormat[item_.type]
                    result_ = struct.unpack("<" + struct_format, self.__res_words(message[0:item_length]))
                    if len(result_) == 1:
                        result_ = result_[0]
                except:
                    if item_.type == "string":
                        result_ = self.__res_string(message[0:item_length])
                    elif item_.type =="ipaddr" or item_.type == "ipv6addr":
                        result_ = message[0:item_length]
                
                if not result_ is None:
                    result[item_.name] = result_
            message = message[item_length:]
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
        if messageLength != len(Message) - 6:       # message length
            return None 
        if Message[6] != UnitId:                    # unit ID
            return None
        if Message[7] != 3:                         # function code 
            return None
        dataLength = Message[8]
        if dataLength + 3 > messageLength:          # data length
            return None 
        Message = Message[9:]
        return Message

    # @todo support rs485
    # @brief Reads a registers from the device defined by the Format string. returns a dictionary with the labels as keys and the register 
    # register values as values.
    # @param UnitId: the unit ID of the device
    # @param Address: the address of the register to read
    # @param Format: the format string to decode the register value
    # @param Labels: the labels for the register values
    def ReadRegister(self, UnitId, Address, Definitions):
        last_def = list(Definitions)[-1] 
        formatsize = last_def + self.__DefinitionRegister._make(Definitions[last_def]).length
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
        values = self.__Unpack(Definitions, result)
        return values

    # @brief send a message via TCP        
    def tcp_send(self, Message):
        self.s.send(bytes(Message))

    # @brief receive a message via TCP        
    def tcp_recv(self, Length):
        return self.s.recv(Length)

    # @brief connect a TCP socket to the given IP and port
    # @param ip: the IP address of the device
    # @param port: the port of the device
    # @param timeout: the timeout for the connection in seconds when receiving data or sending data        
    def tcp_connect(self, ip, port, timeout):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((ip, port))
        self.s.settimeout(timeout)

    # @brief closes the TCP socket
    def tcp_close(self):
        self.s.close()
        self.s = None


class SunSpec(Modbus, SunSpec_Specification):
    # SunSpec's addresses
    __sunspec_adresses = [0, 40000, 50000]
    # cache for the SunSpec blocks
    __sunspec_blocks_cache = { }
    #   data type for the SunSpec block definition      
    SunSpecBlock = namedtuple("SunSpecBlock", ["BlockId", "SubBlockId", "Address", "Length"])

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
        message = self.ReadRegister(Configuration_UnitID, Address, {0: ('C_SunSpec_ID', 'string', 2)})
        if message is None:
            # stop if the message is None
            return None
        # the message must contain the SunSpec ID
        sunspec = message["C_SunSpec_ID"]
        if sunspec != "SunS":
             return None
        Address += 2
        
        result = []
        # process all SunSpec blocks until the end
        while Address < 0x10000:
            message = self.ReadRegister(Configuration_UnitID, Address, {0: ('C_SunSpec_DID', 'uint16', 1), 1: ('C_SunSpec_Length', 'uint16', 1)})

            BlockId = message.get("C_SunSpec_DID", 0xffff) # id might be discared due to not implemented logic
            Length =  message["C_SunSpec_Length"]
            if Length == 0 or BlockId == 0xffff:
                # end block reached
                break
            result.append(self.SunSpecBlock(BlockId , 0, Address, Length))
            Address += Length + 2

        if(self.__sunspec_blocks_cache.get(Configuration_UnitID) is None):
            # add block list to cache
            self.__sunspec_blocks_cache[Configuration_UnitID] = result
        return result

    # @brief reads a SunSpec block for the given UnitId and Address.
    # @param UnitId: the unit ID of the SunSpec device
    # @param Address: the address of the SunSpec block
    # @param BlockId: ID of the SunSpec block; specifies the SunSpec specification to use
    def ReadBlock(self, UnitId, Address, BlockId, SubBlockId = 0):
        BlockDef = SunSpec_Specification.Specification.get((BlockId, SubBlockId))
        if BlockDef is None:
            return None
    #@@@ defblock[0] to be considered
        return self.ReadRegister(UnitId, Address, BlockDef[1])
   
class SolarEdge(SunSpec):
    # @brief reads the SolarEdge SmartMeter data for the given UnitId and SmartMeterId.
    # @param UnitId: the unit ID of the SolarEdge device
    # @apram SmartMeterId: 1, 2 or 3
    def SmartMeter(self, UnitId, SmartMeterId):
        if SmartMeterId < 1 or SmartMeterId > 3:
            return None
        Address = (40121, 40295, 40469)[SmartMeterId - 1]
   
        block = self.ReadRegister(UnitId, Address, 
            {0: ("C_SunSpec_DID", "uint16", 1),
            1: ("C_SunSpec_Length", "uint16", 1),
            2: ("C_Manufacturer", "string", 16),
            18: ("C_Model", "string", 16),
            34: ("C_Option", "string", 8),
            42: ("C_Version", "string", 8),
            50: ("C_SerialNumber", "string", 16),
            66: ("C_DeviceAddress", "uint16", 1),

            67: ("C_SunSpec_DID", "uint16", 1),
            68: ("C_SunSpec_Length", "uint16", 1),
             
            69: ("M_AC_Current", "int16", 1),
            70: ("M_AC_Current_A", "int16", 1),
            71: ("M_AC_Current_B", "int16", 1),
            72: ("M_AC_Current_C", "int16", 1),
            73: ("M_AC_Current_SF", "sunssf", 1),
             
            74: ("M_AC_Voltage_L_N", "int16", 1),
            75: ("M_AC_Voltage_A_N", "int16", 1),
            76: ("M_AC_Voltage_B_N", "int16", 1),
            77: ("M_AC_Voltage_C_N", "int16", 1),
            78: ("M_AC_Voltage_L_N", "int16", 1),
            79: ("M_AC_Voltage_A_B", "int16", 1),
            80: ("M_AC_Voltage_B_C", "int16", 1),
            81: ("M_AC_Voltage_A_C", "int16", 1),
            82: ("M_AC_Voltage_SF", "sunssf", 1),
             
            83: ("M_AC_Freq", "int16", 1),
            84: ("M_AC_Freq_SF", "sunssf", 1),
             
            85: ("M_AC_Power", "int16", 1),
            86: ("M_AC_Power_A", "int16", 1),
            87: ("M_AC_Power_B", "int16", 1),
            88: ("M_AC_Power_C", "int16", 1),
            89: ("M_AC_Power_SF", "sunssf", 1),
             
            90: ("M_AC_VA", "int16", 1),
            91: ("C_AC_VA_A", "int16", 1),
            92: ("M_AC_VA_B", "int16", 1),
            93: ("M_AC_VA_C", "int16", 1),
            94: ("M_AC_VA_SF", "sunssf", 1),
             
            95: ("M_AC_VAR", "int16", 1),
            96: ("M_AC_VAR_A", "int16", 1),
            97: ("M_AC_VAR_B", "int16", 1),
            98: ("M_AC_VAR_C", "int16", 1),
            99: ("M_AC_VAR_SF", "sunssf", 1),
             
            100: ("M_AC_PF", "int16", 1),
            101: ("M_AC_PF_A", "int16", 1),
            102: ("M_AC_PF_B", "int16", 1),
            103: ("M_AC_PF_C", "int16", 1),
            104: ("M_AC_PF_SF", "sunssf", 1),
            
            105: ("M_Exported", "uint32", 2),
            107: ("M_Exported_A", "uint32", 2),
            109: ("M_Exported_B", "uint32", 2),
            111: ("M_Exported_C", "uint32", 2),
            113: ("M_Imported", "uint32", 2),
            115: ("M_Imported_A", "uint32", 2),
            117: ("M_Imported_B", "uint32", 2),
            119: ("M_Imported_C", "uint32", 2),
            121: ("M_Energy_WH_SF", "sunssf", 1),
             
            122: ("M_Exported_VA", "uint32", 2),
            124: ("M_Exported_VA_A", "uint32", 2),
            126: ("M_Exported_VA_B", "uint32", 2),
            128: ("M_Exported_VA_C", "uint32", 2),
            130: ("M_Imported_VA", "uint32", 2),
            132: ("M_Imported_VA_A", "uint32", 2),
            134: ("M_Imported_VA_B", "uint32", 2),
            136: ("M_Imported_VA_C", "uint32", 2),
            138: ("M_Energy_VA_SF", "sunssf", 1),
             
            139: ("M_Import_VARh_Q1", "uint32", 2),
            141: ("M_Import_VARh_Q1a", "uint32", 2),
            143: ("M_Import_VARh_Q1b", "uint32", 2),
            145: ("M_Import_VARh_Q1c", "uint32", 2),
            147: ("M_Import_VARh_Q2", "uint32", 2),
            149: ("M_Import_VARh_Q2a", "uint32", 2),
            151: ("M_Import_VARh_Q2b", "uint32", 2),
            153: ("M_Import_VARh_Q2c", "uint32", 2),
            155: ("M_Import_VARh_Q3", "uint32", 2),
            157: ("M_Import_VARh_Q3a", "uint32", 2),
            159: ("M_Import_VARh_Q3b", "uint32", 2),
            161: ("M_Import_VARh_Q3c", "uint32", 2),
            163: ("M_Import_VARh_Q4", "uint32", 2),
            165: ("M_Import_VARh_Q4a", "uint32", 2),
            167: ("M_Import_VARh_Q4b", "uint32", 2),
            169: ("M_Import_VARh_Q4c", "uint32", 2),
            171: ("M_Import_VAR_SF", "sunssf", 1),
            172: ("M_Events", "uint32", 2)})
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
            {
            0: ("C_Manufacturer", "string", 16),
            16: ("C_Model", "string", 16),
            32: ("C_Version", "string", 16),
            44: ("C_SerialNumber", "string", 16),
            64: ("C_DeviceAddress", "uint16", 1),
            })
        if block1["C_Manufacturer"] == "":
            return None
        # unfortunatley the gap between the blocks can't be read, so we have to read the second 
        # block separately
        block2 = self.ReadRegister(UnitId, Address + 0x42,
            {
              0: ("RatedEnergy", "float32", 2),
              2: ("MaxChargeContinuesPower", "float32", 2),
              4: ("MaxDischargeContinuesPower", "float32", 2),
              6: ("MaxChargePeakPower", "float32", 2),
              8: ("MaxDischargePeakPower", "float32", 2),
              10: ("Reserved", "pad", 32),
              42: ("AverageTemperature", "float32", 2),
              44: ("MaxTemperature", "float32", 2),
              46: ("InstantaneousVoltage", "float32", 2),
              48: ("InstantaneousCurrent", "float32", 2),
              50: ("InstantaneousPower", "float32", 2),
              52: ("LifetimeExportEnergyCounter", "uint64", 4),
              56: ("LifetimeImportEnergyCounter", "uint64", 4),
              60: ("MaxEnergy", "float32", 2),
              62: ("AvailableEngergy", "float32", 2),
              64: ("StateOfHealth", "float32", 2),
              66: ("StateOfEnergy", "float32", 2),
              68: ("Status", "uint32", 2),
              70: ("StatusInternal", "uint32", 2),
              72: ("EventLog", "8unit16", 8),
              80: ("EventLogInternal0", "uint16", 8)
            }) 
        return block1 | block2

    # @brief reads the SolarEdge Grid Protection Trip Limits data for the given UnitId.
    # @param UnitId: the unit ID of the SolarEdge device
    def GridProtectionTripLimits(self, UnitId):
        Address = 0xF602
        block = self.ReadRegister(UnitId, Address, 
            {
                0: ("VgMax1", "float32", 2),
                2: ("VgMax1_HoldTime", "uint32", 2),
                4: ("VgMax2", "float32", 2),
                6: ("VgMax2_HoldTime", "uint32", 2),
                8: ("VgMax3", "float32", 2),
                10: ("VgMax3_HoldTime", "uint32", 2),
                12: ("VgMax4", "float32", 2),
                14: ("VgMax4_HoldTime", "uint32", 2),
                16: ("VgMax5", "float32", 2),
                18: ("VgMax5_HoldTime", "uint32", 2),
                20: ("VgMin1", "float32", 2),
                22: ("VgMin1_HoldTime", "uint32", 2),
                24: ("VgMin2", "float32", 2),
                26: ("VgMin2_HoldTime", "uint32", 2),
                28: ("VgMin3", "float32", 2),
                30: ("VgMin3_HoldTime", "uint32", 2),
                32: ("VgMin4", "float32", 2),
                34: ("VgMin4_HoldTime", "uint32", 2),
                36: ("VgMin5", "float32", 2),
                38: ("VgMin5_HoldTime", "uint32", 2),
                40: ("FgMax1", "float32", 2),
                42: ("FgMax1_HoldTime", "uint32", 2),
                44: ("FgMax2", "float32", 2),
                46: ("FgMax2_HoldTime", "uint32", 2),
                48: ("FgMax3", "float32", 2),
                50: ("FgMax3_HoldTime", "uint32", 2),
                52: ("FgMax4", "float32", 2),
                54: ("FgMax4_HoldTime", "uint32", 2),
                56: ("FgMax5", "float32", 2),
                58: ("FgMax5_HoldTime", "uint32", 2),
                60: ("FgMin1", "float32", 2),
                62: ("FgMin1_HoldTime", "uint32", 2),
                64: ("FgMin2", "float32", 2),
                66: ("FgMin2_HoldTime", "uint32", 2),
                68: ("FgMin3", "float32", 2),
                70: ("FgMin3_HoldTime", "uint32", 2),
                72: ("FgMin4", "float32", 2),
                74: ("FgMin4_HoldTime", "uint32", 2),
                76: ("FgMin5", "float32", 2),
                78: ("FgMin5_HoldTime", "uint32", 2),
                80: ("GRM_Time", "uint32", 2),
            }
        )
        return block
