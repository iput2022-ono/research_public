import time
from sensirion_i2c_driver import I2cConnection
from sensirion_i2c_scd import Scd4xI2cDevice
from sensirion_i2c_driver.linux_i2c_transceiver import LinuxI2cTransceiver

class SCD41Sensor:
    def __init__(self, temp_correction=0.0):
        self.temp_correction = temp_correction
        transceiver = LinuxI2cTransceiver('/dev/i2c-1')
        connection = I2cConnection(transceiver)
        self.device = Scd4xI2cDevice(connection)

        try:
            self.device.stop_periodic_measurement()
            time.sleep(0.5)
        except Exception:
            pass 
        self.device.start_periodic_measurement()

    def read_values(self):
        # time.sleep(5)
        co2, temperature, humidity = self.device.read_measurement()
        # print(f"co2 raw: {co2}, type: {type(co2)}, dir: {dir(co2)}")
        # print(f"temp raw: {temperature}, type: {type(temperature)}, dir: {dir(temperature)}")
        # print(f"RH raw: {humidity}, type: {type(humidity)}, dir: {dir(humidity)}")
        corrected_temp = temperature.degrees_celsius + self.temp_correction
        return {
            "CO2": co2.co2,
            # "temperature": temperature.degrees_celsius,   #手動補正反映前
            "temperature": corrected_temp,
            "relative_humidity":  humidity.percent_rh
        }

    # 気温オフセットを取得
    def get_temperature_offset(self):
        self.device.stop_periodic_measurement()
        time.sleep(0.5)
        offset = self.device.get_temperature_offset()
        self.device.start_periodic_measurement()
        return offset.degrees_celsius
    # 気温オフセットを設定（設定可能な温度オフセットは-10.0°C ～ +10.0°C）
    # def set_temperature_offset(self, offset_celsius: float):
    #     self.device.stop_periodic_measurement()
    # def persist_settings(self):
    #     self.device.stop_periodic_measurement()

if __name__ == '__main__':
    print("【SCD41センサ単体テストモード】")
    sensor = SCD41Sensor()
    try:
        while True:
            try:
                time.sleep(5)
                values = sensor.read_values()
                print(f"CO2: {values['CO2']} ppm, Temp: {values['temperature']:.2f} °C, RH: {values['relative_humidity']:.2f}%")
            except Exception as e:
                print(f"[エラー] 測定失敗: {e}")
    except KeyboardInterrupt:
        print("終了します")