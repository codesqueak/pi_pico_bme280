#
# Demonstration program for the Raspberry Pi Pico
#
# This program demonstrates how to interface a sensor (BME280) to the i2c bus of the Pico
#
# No 3rd party libraries are used so that all steps are visible
#

import time

import machine

# Define the i2c interface on pins 1 and 2. Ground is taken from pin 3 and 3.3v from pin 36 (3V3(OUT))
sda = machine.Pin(0)  # GP_0
scl = machine.Pin(1)  # GP_1

i2c = machine.I2C(0, sda=sda, scl=scl, freq=100000)

# scan the bus and show what we have. By default the BME280 module should be on address 0x76
print('i2c devices found at')
devices = i2c.scan()
if devices:
    for i in devices:
        print(hex(i))

print()

i2c_addr = 0x76  # Change this if the device is on another address
#
# All setup parameters are defined in the datasheet
# https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf
#
# humidity  oversampling
i2c.writeto_mem(i2c_addr, 0xf2, b'\x03')  # ctrl_hum 00000 011
#
# temp oversampling / pressure / oversampling / sensor mode
i2c.writeto_mem(i2c_addr, 0xf4, b'\x6F')  # ctrl_meas 011 011 11
#
# wait for it to take effect
time.sleep(0.1)

#
# The sensor presents as a memory mapped device on teh i2c bus
#
reg_base_addr = 0x88  # memory map is from 0x88 to 0xff
block_size = 0x100 - reg_base_addr  # bytes to read
r = i2c.readfrom_mem(i2c_addr, reg_base_addr, block_size)  # Read the sensor into a buffer

# dump all memory values
print('Sensor data')
offset = 0
for i in r:
    if offset % 8 == 0:
        print('\n' + hex(reg_base_addr + offset), end=': ')
    print('{0:02X} '.format(i), end='')
    offset = offset + 1

print()
print()


# read two bytes as an unsigned int
def read_const_u(a):
    return r[a - reg_base_addr] + (r[a - reg_base_addr + 1] << 8)


# read two bytes as a signed int
def read_const_s(a):
    v = r[a - reg_base_addr] + (r[a - reg_base_addr + 1] << 8)
    if v > 32767:
        v = v - 65536
    return v


# TEMPERATURE

# get raw temperature
temp_msb = r[0xfa - reg_base_addr]
temp_lsb = r[0xfb - reg_base_addr]
temp_xlsb = r[0xfc - reg_base_addr]
adc_t = (temp_msb << 12) + (temp_lsb << 4) + (temp_xlsb >> 4)

# get compensation parameters (These are constants, only read once in a production system)
dig_t1 = read_const_u(0x88)
dig_t2 = read_const_s(0x8a)
dig_t3 = read_const_s(0x8c)

# calc temperature
# Shown as done in the datasheet - can be tidied up
var1 = ((adc_t >> 3) - (dig_t1 << 1)) * (dig_t2 >> 11)
var2 = (((((adc_t >> 4) - dig_t1) * ((adc_t >> 4) - dig_t1)) >> 12) * dig_t3) >> 14
t_fine = (var1 + var2)
t = (t_fine * 5 + 128) >> 8

print("Temperature is " + str(t / 100) + " degrees")

# PRESSURE

# get raw pressure
press_msb = r[0xf7 - reg_base_addr]
press_lsb = r[0xf8 - reg_base_addr]
press_xlsb = r[0xf9 - reg_base_addr]
adc_p = (press_msb << 12) + (press_lsb << 4) + (press_xlsb >> 4)

# get compensation parameters (These are constants, only read once in a production system)

dig_p1 = read_const_u(0x8e)
dig_p2 = read_const_s(0x90)
dig_p3 = read_const_s(0x92)
dig_p4 = read_const_s(0x94)
dig_p5 = read_const_s(0x96)
dig_p6 = read_const_s(0x98)
dig_p7 = read_const_s(0x9a)
dig_p8 = read_const_s(0x9c)
dig_p9 = read_const_s(0x9e)

# calc pressure
# Shown as done in the datasheet - can be tidied up
var1 = t_fine - 128000
var2 = var1 * var1 * dig_p6
var2 = var2 + ((var1 * dig_p5) << 17)
var2 = var2 + (dig_p4 << 35)
var1 = ((var1 * var1 * dig_p3) >> 8) + ((var1 * dig_p2) << 12)
var1 = ((1 << 47) + var1) * dig_p1 >> 33
if var1 == 0:  # divide by zero check
    p = 0
else:
    p = 1048576 - adc_p
    p = int((((p << 31) - var2) * 3125) / var1)
    var1 = (dig_p9 * (p >> 13) * (p >> 13)) >> 25
    var2 = (dig_p8 * p) >> 19
    p = ((p + var1 + var2) >> 8) + (dig_p7 << 4)

print("Pressure is " + str(p / 25600) + " mbar")

# HUMIDITY

# get raw pressure
hum_msb = r[0xfd - reg_base_addr]
hum_lsb = r[0xfe - reg_base_addr]
adc_h = (hum_msb << 8) + hum_lsb

# get compensation parameters (These are constants, only read once in a production system)

dig_h1 = r[0xa1 - reg_base_addr]
dig_h2 = read_const_s(0xe1)
dig_h3 = r[0xe3 - reg_base_addr]
dig_h4 = (r[0xe4 - reg_base_addr] << 4) + (r[0xe5 - reg_base_addr] & 0x0f)
dig_h5 = (r[0xe6 - reg_base_addr] << 4) + ((r[0xe5 - reg_base_addr] & 0x00f0) >> 4)
dig_h6 = r[0xe7 - reg_base_addr]

# calc humidity
# Shown as done in the datasheet - can be tidied up
v_x1_u32r = t_fine - 76800

v_x1_u32r = (((((adc_h << 14) - (dig_h4 << 20) - (dig_h5 * v_x1_u32r)) + 16384) >> 15) * (((((((v_x1_u32r * (
    dig_h6)) >> 10) * (((v_x1_u32r * dig_h3) >> 11) + 32768)) >> 10) + 2097152) * dig_h2 + 8192) >> 14))

v_x1_u32r = (v_x1_u32r - (((((v_x1_u32r >> 15) * (v_x1_u32r >> 15)) >> 7) * dig_h1) >> 4))

# limit checks
if v_x1_u32r < 0:
    v_x1_u32r = 0

if v_x1_u32r > 0x19000000:
    v_x1_u32r = 0x19000000

h = v_x1_u32r >> 12

print("Humidity is " + str(h / 1024) + " %")
