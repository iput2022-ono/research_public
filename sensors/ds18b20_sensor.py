from w1thermsensor import W1ThermSensor, Unit
import time

class DS18B20Sensor:
    def __init__(self):
        self.sensor = W1ThermSensor()

    def read_temperature(self):
        return self.sensor.get_temperature(Unit.DEGREES_C)

if __name__ == '__main__':
    print("【DS18b20センサ単体テストモード】")
    ds18b20 = DS18B20Sensor()
    while True:
        try:
            temp = ds18b20.read_temperature()
            print("Water_temp: {:.3f}°C".format(temp))
            time.sleep(1.0)
        except KeyboardInterrupt:
            print("終了します")
            break