from ubidots import ApiClient
import time
import json
import serial
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
from gpiozero import MCP3008
import board
import busio
import adafruit_ina219
from gpiozero import DigitalOutputDevice

# Inisialisasi I2C
i2c = busio.I2C(board.SCL, board.SDA)
ina219 = adafruit_ina219.INA219(i2c)

# Konfigurasi MCP3008
mcp3008 = MCP3008(channel=1)  # Saluran ADC MCP3008 yang terhubung

# Connect to the slave
serial = serial.Serial(
                       port='/dev/ttyUSB0',
                       baudrate=9600,
                       bytesize=8,
                       parity='N',
                       stopbits=1,
                       xonxoff=0
                      )
master = modbus_rtu.RtuMaster(serial)
master.set_timeout(2.0)
master.set_verbose(True)

# Konfigurasi Ubidots
api = ApiClient(token="")
solar_panel_variable = api.get_variable("")
treshold_switcher_variable = api.get_variable("")
switcher_pln_variable = api.get_variable("")
battery_variable = api.get_variable("")
output_daya_rumah_variable = api.get_variable("")

# Inisialisasi relay PLN dan PLTS
relay_pln = DigitalOutputDevice(pin=17)  # Ganti dengan pin yang sesuai
relay_plts = DigitalOutputDevice(pin=18)  # Ganti dengan pin yang sesuai

def get_solar_panel_value(data):
    return (data[3] + (data[4] << 16)) / 10.0

def get_battery_voltage():
    return mcp3008.value * 3.3 * 5

def get_battery_percentage(battery_voltage):
    return ((battery_voltage - 11.0) / (14.2 - 11.0)) * 100.0

def get_output_daya_rumah(solar_panel_value, treshold_switcher_value, switcher_pln_value):
    return solar_panel_value * (1 - treshold_switcher_value) * switcher_pln_value

def control_relays(switcher_pln_value, output_daya_rumah_value, treshold_value):
    if switcher_pln_value == 1:
        relay_pln.on()
        relay_plts.off()
    elif switcher_pln_value == 0:
        if output_daya_rumah_value > treshold_value:
            relay_pln.on()
            relay_plts.off()
        else:
            relay_pln.off()
            relay_plts.on()

def update_ubidots_variables(solar_panel_value, treshold_switcher_value, switcher_pln_value, battery_value, output_daya_rumah_value):
    solar_panel_variable.save_value({"value": solar_panel_value})
    treshold_switcher_variable.save_value({"value": treshold_switcher_value})
    switcher_pln_variable.save_value({"value": switcher_pln_value})
    battery_variable.save_value({"value": battery_value})
    output_daya_rumah_variable.save_value({"value": output_daya_rumah_value})

if __name__ == "__main__":
    try:
        while True:
            data = master.execute(1, cst.READ_INPUT_REGISTERS, 0, 10)

            solar_panel_value = get_solar_panel_value(data)
            battery_voltage = get_battery_voltage()
            battery_percentage = get_battery_percentage(battery_voltage)
            
            
            treshold_switcher_value = treshold_switcher_variable.get_values(1)[5000]['value']
            treshold_switcher_value = max(1, min(treshold_switcher_value, 2000))  # Pastikan nilai dalam rentang 1-2000

            switcher_pln_value = switcher_pln_variable.get_values(1)[0]['value']
            switcher_pln_value = max(0, min(switcher_pln_value, 1))  # Pastikan nilai dalam rentang 0-1

            
            output_daya_rumah_value = get_output_daya_rumah(solar_panel_value, treshold_switcher_value, switcher_pln_value)
            
           
            update_ubidots_variables(solar_panel_value, treshold_switcher_value, switcher_pln_value, battery_percentage, output_daya_rumah_value)
            
            treshold_value = treshold_switcher_value  
            
            control_relays(switcher_pln_value, output_daya_rumah_value, treshold_value)
            
            dict_payload = {
                "voltage": data[0] / 10.0,
                "current_A": (data[1] + (data[2] << 16)) / 1000.0,
                "power_W": (data[3] + (data[4] << 16)) / 10.0
            }
            
            str_payload = json.dumps(dict_payload, indent=2)
            print(str_payload)
            print("Tegangan Baterai: {:.2f}V".format(battery_voltage))
            print("Persentase Baterai: {:.2f}%".format(battery_percentage))

            time.sleep(1)
        
    except KeyboardInterrupt:
        print('Exiting script')
    except Exception as e:
        print(e)
    finally:
        master.close()
