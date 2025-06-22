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

import modbus
from collections import namedtuple

Configuration_UnitID = 1
Configuration_IP = "wechselrichter1"
Configuration_Port = 1502
Configuration_Timeout = 1


tcpmodbus = modbus.SolarEdge()
tcpmodbus.tcp_connect(Configuration_IP, Configuration_Port, Configuration_Timeout)

if True:
    print("SunSpec")
    sunspec = tcpmodbus.SunSpec(Configuration_UnitID)
    print(sunspec)
    SunSpecBlocks = tcpmodbus.SunSpec(Configuration_UnitID)
    for Block in SunSpecBlocks:
        print("------------------------------")
        print("BlockId: ", Block.BlockId, " Address: ", Block.Address, " Length: ", Block.Length)
        if Block.BlockId == 101 or True:
            print(tcpmodbus.ReadBlock(Configuration_UnitID, Block.Address, Block.BlockId))
    print("------------------------------")

if True:
    print("SolarEdge SmartMeter 1")
    print(tcpmodbus.SmartMeter(Configuration_UnitID, 1))
    print("SolarEdge SmartMeter 2")
    print(tcpmodbus.SmartMeter(Configuration_UnitID, 2))
    print("SolarEdge SmartMeter 3")
    print(tcpmodbus.SmartMeter(Configuration_UnitID, 3))

if True:
    print("SolarEdge Battery 1")
    print(tcpmodbus.Battery(Configuration_UnitID, 1))
if False:    
    print("SolarEdge Battery 2")
    print(tcpmodbus.Battery(Configuration_UnitID, 2))

if True:
    print ("SolarEdge Grid Protection Trip Limits")
    print(tcpmodbus.GridProtectionTripLimits(Configuration_UnitID))

tcpmodbus.tcp_close()
