import time
from sensors.ds18b20_sensor import DS18B20Sensor
from sensors.ec_sensor import ECSensor
from sensors.scd41_sensor   import SCD41Sensor
# from utils.buffer_utils import has_buffer, load_buffer, save_buffer_csv, send_buffered
from gpio_control import GpioController
import socket
import ambient
from datetime import datetime, timezone
import argparse
from dotenv import load_dotenv
import os

# .env
load_dotenv()
# AMBIENT_CHANNEL_ID = os.getenv("AMBIENT_CHANEL_ID")
# AMBIENT_WRITE_KEY = os.getenv("AMBIENT_WRITE_KEY")
AMBIENT_CHANNEL_ID_TEST = os.getenv("AMBIENT_CHANEL_ID_TEST")
AMBIENT_WRITE_KEY_TEST = os.getenv("AMBIENT_WRITE_KEY_TEST")
# Ambient設定
# ambi = ambient.Ambient(AMBIENT_CHANNEL_ID, AMBIENT_WRITE_KEY)
ambi = ambient.Ambient(AMBIENT_CHANNEL_ID_TEST, AMBIENT_WRITE_KEY_TEST)

# インターネット接続確認
def is_connected(host="8.8.8.8", port=53, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

# 有効桁数（有効３桁）
def fmt_sig(val, sig_digits=3):
    if val is None:
        return None
    if val == 0:
        return 0.0
    from math import log10, floor
    digits = sig_digits - int(floor(log10(abs(val)))) - 1
    return round(val, digits)
# 小数点以下桁数（小数第２位）
def fmt_fixed(val, digits=2):
    return round(val, digits) if val is not None else None
# モード切り替え：有効3桁 or 小数第2位
USE_SIG_DIGITS = False

def format_val(val):
    return fmt_sig(val) if USE_SIG_DIGITS else fmt_fixed(val)

# CLI処理
parser = argparse.ArgumentParser(description="センサ制御用CLI")
parser.add_argument('--get-offset', action='store_true', help='SCD41の温度オフセットを取得')
parser.add_argument('--temp-correction', type=float, default=0.0, help='表示温度に加える手動補正値（例：--temp-correction 2.0）')
args = parser.parse_args()
# センサ初期化
ds18b20 = DS18B20Sensor()
scd41 = SCD41Sensor(temp_correction=args.temp_correction)
ec_sensor = ECSensor()
gpio = GpioController()
time.sleep(2)
# オフセットの取得
if args.get_offset:
    try:
        offset = scd41.get_temperature_offset()
        print(f"＞現在のセンサ内温度オフセット: {offset:.2f} °C")
    except Exception as e:
        print(f"[エラー] オフセット取得失敗: {e}")
    exit(0)
else:
    print(f"＞SCD41手動補正値 (temp_correction): {args.temp_correction} °Cで設定されています")

INTERVAL = 20  # 秒

print("＞起動しました...しばらくお待ちください")
time.sleep(5)
gpio.startup_blink() # 起動時1回点滅

try:
    while True:

        if gpio.measurement_active:
            start = time.time()
            # センサ読み取りの時刻を取得
            sensortime = datetime.now(timezone.utc).isoformat()

            # DS18B20（水温）の読み取り
            try:
                water_temp = ds18b20.read_temperature()
                print(f"[DS18B20] Water_temp: {water_temp:.2f} °C")
            except Exception as e:
                print(f"[DS18B20] 読み取りエラー: {e}")
                water_temp = None

            # 電源プラグ（EC）の読み取り
            try:
                ec_sensor.temp_c = water_temp
                ec25 = ec_sensor.read_ec()
                if ec25 is not None:
                    print(f"[EC] EC25: {ec25:.2f} µS/cm")
                else:
                    print("[EC] 測定エラー（電圧範囲外）")
            except Exception as e:
                print(f"[EC] 測定例外: {e}")
                ec25 = None

            # SCD41（CO2 / 気温 / 湿度）の読み取り
            try:
                scd = scd41.read_values()
                co2  = scd['CO2']
                temp = scd['temperature']
                hum  = scd['relative_humidity']
                print(f"[SCD41] CO₂: {co2} ppm, Temp: {temp:.2f} °C, RH: {hum:.2f}%")
            except Exception as e:
                print(f"[SCD41] 読み取りエラー: {e}")
                co2 = temp = hum = None

            # Ambient送信
            t0 = time.time()
            if None not in (water_temp, co2, temp, hum, ec25):        
                # Ambient送信の時刻を取得
                ambitime = datetime.now(timezone.utc).isoformat()
                print("センサ取得時間: ",sensortime)
                print("ambient送信時間: ",ambitime)

                f_water_temp = format_val(water_temp)
                f_co2 = format_val(co2)
                f_temp = format_val(temp)
                f_hum = format_val(hum)
                f_ec25 = format_val(ec25)

                if is_connected():
                    try:
                        # # バッファがあれば先に送信
                        # if has_buffer():
                        #     send_buffered(ambi, format_val)

                        r = ambi.send({
                            "created": sensortime,
                            "d1": f_water_temp,
                            "d2": f_co2,
                            "d3": f_temp,
                            "d4": f_hum,
                            "d5": f_ec25
                        })
                        if r:
                            print("[Ambient] 送信成功")
                        else:
                            print("[Ambient] 送信失敗 CSV保存")
                            # save_buffer_csv(f_water_temp, f_co2, f_temp, f_hum, sensortime)

                    except Exception as e:
                        print("[Ambient] 例外:", e)
                        # save_buffer_csv(f_water_temp, f_co2, f_temp, f_hum, sensortime)
                else:
                    print("[Ambient] ネットワーク未接続のためCSV保存")
                    # save_buffer_csv(f_water_temp, f_co2, f_temp, f_hum, sensortime)
            else:
                print("[Ambient] センサデータが不完全なため送信を中止しました")

            # 処理時間
            end = time.time()
            elapsed = end - start
            print(f"送信までの処理時間: {t0 - start:.4f} 秒", f"処理時間: {elapsed:.4f} 秒")
            print("-" * 40)
            time.sleep(INTERVAL)
        else:
            time.sleep(0.1)

except KeyboardInterrupt:
    print("＞プログラムを終了します")
finally:
    gpio.cleanup()
