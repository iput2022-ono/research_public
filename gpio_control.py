import RPi.GPIO as GPIO
import time
import threading
import os

class GpioController:
    RED = "\033[91m"
    RESET = "\033[0m"

    PWR_LED_TRIGGER = "/sys/class/leds/PWR/trigger"
    PWR_LED_BRIGHTNESS = "/sys/class/leds/PWR/brightness"

    def __init__(self, measure_led_pin=16, toggle_pin=20, shutdown_pin=21):
        self.MEASURE_LED = measure_led_pin
        self.BTN_TOGGLE = toggle_pin
        self.BTN_SHUTDOWN = shutdown_pin

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.MEASURE_LED, GPIO.OUT)
        GPIO.output(self.MEASURE_LED, GPIO.LOW)
        GPIO.setup(self.BTN_TOGGLE, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.BTN_SHUTDOWN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        self.set_pwr_led_trigger("none")
        self.set_pwr_led(False)

        self.measurement_active = False
        self.shutdown_requested = False
        self._shutdown_mode = False
        self._allow_cancel = False
        self._blinker_stop = None

        # 長押し監視用
        self._hold_thread = None
        self._hold_stop = threading.Event()
        self._in_hold_check = False  # 長押し判定フラグ

        GPIO.add_event_detect(self.BTN_TOGGLE, GPIO.RISING,
                              callback=self._measurement_event, bouncetime=300)
        GPIO.add_event_detect(self.BTN_SHUTDOWN, GPIO.RISING,
                              callback=self._shutdown_event, bouncetime=300)

    # PWR LED制御
    def set_pwr_led_trigger(self, mode="none"):
        with open(self.PWR_LED_TRIGGER, "w") as f:
            f.write(mode)

    def set_pwr_led(self, state: bool):
        with open(self.PWR_LED_BRIGHTNESS, "w") as f:
            f.write("1" if state else "0")

    def startup_blink(self):
        print("＞測定開始・終了は黒SW、シャットダウンは青SWを3秒長押し")
        GPIO.output(self.MEASURE_LED, GPIO.HIGH)
        time.sleep(0.5)
        GPIO.output(self.MEASURE_LED, GPIO.LOW)

    # 計測ON/OFF機能
    def _measurement_event(self, channel):
        if self._shutdown_mode or self._in_hold_check:  # 長押し判定中は無効
            print(self.RED + "[警告] シャットダウン処理中は計測できません。" + self.RESET)
            return
        self.measurement_active = not self.measurement_active
        GPIO.output(self.MEASURE_LED, GPIO.HIGH if self.measurement_active else GPIO.LOW)
        print(f"＞測定: {'ON' if self.measurement_active else 'OFF'}")

    # 青SW押下時
    def _shutdown_event(self, channel):
        if self._shutdown_mode:
            if self._allow_cancel:
                print("＞シャットダウンをキャンセルしました")
                self._stop_shutdown_sequence()
            return
        if self.measurement_active:
            print(self.RED + "[警告] 計測中はシャットダウンできません。" + self.RESET)
            return

        # 長押し監視スレッド開始
        self._hold_stop.clear()
        self._in_hold_check = True
        self._hold_thread = threading.Thread(target=self._hold_check)
        self._hold_thread.start()

    # 長押し判定
    def _hold_check(self):
        start = time.time()
        while not self._hold_stop.is_set():
            if GPIO.input(self.BTN_SHUTDOWN) == GPIO.LOW:
                self._in_hold_check = False
                return
            if time.time() - start >= 3:  # 3秒押し続けた
                self._start_shutdown_sequence()
                self._in_hold_check = False
                return
            time.sleep(0.05)
        self._in_hold_check = False

    # シャットダウン機能（猶予60秒）
    def _start_shutdown_sequence(self):
        if self._shutdown_mode:
            return
        print("＞シャットダウンモード開始")
        self.shutdown_requested = True
        self._shutdown_mode = True
        self._allow_cancel = False
        print("＞60秒後にシャットダウンします。キャンセルは青SWを押す")

        # LED点滅スレッド
        self._blinker_stop = threading.Event()
        blinker = threading.Thread(target=self._countdown_blink, args=(self._blinker_stop,))
        blinker.start()

        # ボタンが一度離されるのを待ってからキャンセル受付
        while GPIO.input(self.BTN_SHUTDOWN) == GPIO.HIGH:
            time.sleep(0.05)
        self._allow_cancel = True

        # 猶予60秒
        start = time.time()
        while time.time() - start < 60:
            if not self.shutdown_requested:
                return
            time.sleep(0.1)

        self._blinker_stop.set()
        print("＞シャットダウン実行します")
        self._reset_state()
        os.system("sudo shutdown -h now")

    # キャンセル
    def _stop_shutdown_sequence(self):
        self.shutdown_requested = False
        self._shutdown_mode = False
        self._allow_cancel = False
        if self._blinker_stop:
            self._blinker_stop.set()
        self.set_pwr_led(False)

    def _reset_state(self):
        self._stop_shutdown_sequence()
        self.set_pwr_led(False)

    # 赤LED点滅（猶予中）
    def _countdown_blink(self, stop_event):
        start = time.time()
        while not stop_event.is_set():
            elapsed = time.time() - start
            interval = 0.1 if elapsed >= 55 else 0.5
            self.set_pwr_led(True)
            time.sleep(interval)
            self.set_pwr_led(False)
            time.sleep(interval)

    def cleanup(self):
        self.set_pwr_led_trigger("default-on")
        GPIO.cleanup()