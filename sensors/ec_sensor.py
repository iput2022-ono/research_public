import spidev

class ECSensor:
    def __init__(self,
                 channel=0,
                 vref=3.3,
                 r_series=1000, 
                 ra=25.0,
                 k_cell=2.8,
                 temp_coef=0.019,
                 spi_bus=0,
                 spi_dev=0):
        self.channel = channel
        self.vref = vref
        self.r1 = r_series + ra
        self.ra = ra
        self.k_cell = k_cell
        self.tcoef = temp_coef
        self.temp_c = 25.0  # 初期温度

        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_dev)
        self.spi.max_speed_hz = 100000
        self.spi.mode = 0b00

    def read_raw(self):     # MCP3208のためのSPI命令フォーマット
        cmd1 = 0b00000110 | ((self.channel & 0x04) >> 2)
        cmd2 = ((self.channel & 0x03) << 6)
        resp = self.spi.xfer2([cmd1, cmd2, 0x00])
        return ((resp[1] & 0x0F) << 8) | resp[2]

    def read_voltage(self):
        raw = self.read_raw()
        return (raw / 4095.0) * self.vref, raw

    def read_ec(self):
        v, _ = self.read_voltage()
        if v <= 0 or v >= self.vref:
            return None
        rc = (v * self.r1) / (self.vref - v) - self.ra
        ec = 1000.0 / (rc * self.k_cell)
        ec25 = ec / (1 + self.tcoef * (self.temp_c - 25.0))
        return ec25

if __name__ == '__main__':
    import time
    from ds18b20_sensor import DS18B20Sensor

    print("【ECセンサ単体テストモード】 DS18B20の温度を使用して補正")
    ds18b20 = DS18B20Sensor()
    sensor = ECSensor()

    try:
        while True:
            try:
                water_temp = ds18b20.read_temperature()
                sensor.temp_c = water_temp
                ec25 = sensor.read_ec()
                v, raw = sensor.read_voltage()

                print(f"Water_temp: {water_temp:.2f} °C, EC25: {ec25:.2f} µS/cm")
                time.sleep(1.0)
            except Exception as e:
                print(f"[エラー] 測定失敗: {e}")
    except KeyboardInterrupt:
        print("終了します")