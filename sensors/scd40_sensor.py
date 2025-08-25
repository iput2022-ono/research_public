import board
import busio
import adafruit_scd4x

class SCD40Sensor:
    def __init__(self):
        i2c = busio.I2C(board.SCL, board.SDA)
        self.sensor = adafruit_scd4x.SCD4X(i2c)
        self.sensor.start_periodic_measurement()

    def read_values(self):
        if self.sensor.data_ready:
            return {
                "CO2": self.sensor.CO2,
                "temperature": self.sensor.temperature,
                "relative_humidity": self.sensor.relative_humidity
            }
        return None

if __name__ == '__main__':
    import time
    scd40 = SCD40Sensor()
    while True:
        try:
            data = scd40.read_values()
            if data:
                print(f"CO2: {data['CO2']} ppm, Temp: {data['temperature']:.2f} °C, RH: {data['relative_humidity']:.2f}%")
            time.sleep(1.0)
        except KeyboardInterrupt:
            print("終了します")
            break