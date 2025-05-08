
import modbus

Configuration_UnitID = 1
Configuration_IP = "wechselrichter1"
Configuration_Port = 1502
Configuration_Timeout = 1

tcpmodbus = modbus.SolarEdge()
tcpmodbus.tcp_connect(Configuration_IP, Configuration_Port, Configuration_Timeout)

print("SunSpec")
sunspec = tcpmodbus.SunSpec(Configuration_UnitID)
print(sunspec)


print("Inverter 1")
print(tcpmodbus.Inverter(Configuration_UnitID))

print("Inverter 2")
print(tcpmodbus.Inverter(Configuration_UnitID + 1))

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

print("DER701")
print(tcpmodbus.DER701(Configuration_UnitID))


tcpmodbus.tcp_close()



   
