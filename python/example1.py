
import modbus
from collections import namedtuple

Configuration_UnitID = 1
Configuration_IP = "wechselrichter1"
Configuration_Port = 1502
Configuration_Timeout = 1

tcpmodbus = modbus.SolarEdge()
tcpmodbus.tcp_connect(Configuration_IP, Configuration_Port, Configuration_Timeout)

print("SunSpec")
sunspec = tcpmodbus.SunSpec(Configuration_UnitID)
print(sunspec)
SunSpecBlocks = tcpmodbus.SunSpec(Configuration_UnitID)
for Block in SunSpecBlocks:
    print("------------------------------")
    print("BlockId: ", Block.BlockId, " Address: ", Block.Address, " Length: ", Block.Length)

    print(tcpmodbus.read_sunspec_block(Configuration_UnitID, Block.Address, Block.BlockId))
print("------------------------------")

print("Smart Meter 1")
print(tcpmodbus.SmartMeter(Configuration_UnitID, 1))
print("Smart Meter 2")
print(tcpmodbus.SmartMeter(Configuration_UnitID, 2))
print("Smart Meter 3")
print(tcpmodbus.SmartMeter(Configuration_UnitID, 3))

print("Battery 1")
print(tcpmodbus.Battery(Configuration_UnitID, 1))
print("Battery 2")
print(tcpmodbus.Battery(Configuration_UnitID, 2))

print ("Grid Protection Trip Limits")
print(tcpmodbus.GridProtectionTripLimits(Configuration_UnitID))

tcpmodbus.tcp_close()
