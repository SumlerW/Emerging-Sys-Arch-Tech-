from time import sleep
from datetime import datetime
from statemachine import StateMachine, State
import board
import adafruit_ahtx0
import digitalio
import adafruit_character_lcd.character_lcd as characterlcd
import serial
from gpiozero import Button, PWMLED
from threading import Thread
from math import floor

DEBUG = True  #Enable debug messages to print status info

#Setup I2C communication and temperature sensor (AHT20)
i2c = board.I2C()
thSensor = adafruit_ahtx0.AHTx0(i2c)

#Setup UART serial communication
ser = serial.Serial(
    port='/dev/ttyS0',
    baudrate=115200,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
)

#Define LED pins using PWM for fading capability
redLight = PWMLED(18)   #Red LED for heat
blueLight = PWMLED(23)  #Blue LED for cool

#Class to manage 16x2 LCD display
class ManagedDisplay():
    def __init__(self):
        #Define LCD control pins
        self.lcd_rs = digitalio.DigitalInOut(board.D17)
        self.lcd_en = digitalio.DigitalInOut(board.D27)
        self.lcd_d4 = digitalio.DigitalInOut(board.D5)
        self.lcd_d5 = digitalio.DigitalInOut(board.D6)
        self.lcd_d6 = digitalio.DigitalInOut(board.D13)
        self.lcd_d7 = digitalio.DigitalInOut(board.D26)

        self.lcd_columns = 16  #16 columns
        self.lcd_rows = 2      #2 rows

        #Create LCD object
        self.lcd = characterlcd.Character_LCD_Mono(
            self.lcd_rs, self.lcd_en,
            self.lcd_d4, self.lcd_d5,
            self.lcd_d6, self.lcd_d7,
            self.lcd_columns, self.lcd_rows)
        self.lcd.clear()

    def cleanupDisplay(self):
        self.lcd.clear()
        self.lcd_rs.deinit()
        self.lcd_en.deinit()
        self.lcd_d4.deinit()
        self.lcd_d5.deinit()
        self.lcd_d6.deinit()
        self.lcd_d7.deinit()

    def clear(self):
        self.lcd.clear()

    def updateScreen(self, message):
        self.lcd.clear()
        self.lcd.message = message  #Display a message

#Create display instance
screen = ManagedDisplay()

#Thermostat state machine class
class TemperatureMachine(StateMachine):
    off = State(initial=True)  #Thermostat is off
    heat = State()             #Heating mode
    cool = State()             #Cooling mode

    setPoint = 72  #Default temperature set point (°F)

    cycle = (off.to(heat) | heat.to(cool) | cool.to(off))  #Cycle through states

    def on_enter_heat(self):
        redLight.pulse()  #Red LED fades to show heating
        if DEBUG:
            print("* Changing state to heat")

    def on_exit_heat(self):
        redLight.off()  #Turn off red LED

    def on_enter_cool(self):
        blueLight.pulse()  #Blue LED fades to show cooling
        if DEBUG:
            print("* Changing state to cool")

    def on_exit_cool(self):
        blueLight.off()  #Turn off blue LED

    def on_enter_off(self):
        redLight.off()
        blueLight.off()
        if DEBUG:
            print("* Changing state to off")

    #Cycle button pressed
    def processTempStateButton(self):
        if DEBUG:
            print("Cycling Temperature State")
        self.cycle()
        self.updateLights()

    #Increase temperature set point
    def processTempIncButton(self):
        if DEBUG:
            print("Increasing Set Point")
        self.setPoint += 1
        self.updateLights()

    #Decrease temperature set point
    def processTempDecButton(self):
        if DEBUG:
            print("Decreasing Set Point")
        self.setPoint -= 1
        self.updateLights()

    #Control LED behavior based on state and temp
    def updateLights(self):
        temp = floor(self.getFahrenheit())
        redLight.off()
        blueLight.off()

        if DEBUG:
            print(f"State: {self.current_state.id}")
            print(f"SetPoint: {self.setPoint}")
            print(f"Temp: {temp}")

        if self.current_state.id == 'heat':
            if temp < self.setPoint:
                redLight.pulse()  #Fade if heating required
            else:
                redLight.value = 1.0  #Solid if heating done
        elif self.current_state.id == 'cool':
            if temp > self.setPoint:
                blueLight.pulse()  # Fade if cooling required
            else:
                blueLight.value = 1.0  #Solid if cooling done

    #Start LCD update thread
    def run(self):
        myThread = Thread(target=self.manageMyDisplay)
        myThread.start()

    def getFahrenheit(self):
        t = thSensor.temperature
        return (((9 / 5) * t) + 32)  #Convert C to F

    #Format UART string
    def setupSerialOutput(self):
        temp = floor(self.getFahrenheit())
        output = f"{self.current_state.id},{temp},{self.setPoint}"
        return output

    endDisplay = False

    #Background thread to update LCD + UART
    def manageMyDisplay(self):
        counter = 1
        altCounter = 1
        while not self.endDisplay:
            if DEBUG:
                print("Processing Display Info...")

            current_time = datetime.now()
            lcd_line_1 = current_time.strftime("%m/%d %H:%M") + "\n"  #Line 1: time

            if altCounter < 6:
                lcd_line_2 = f"Temp: {floor(self.getFahrenheit())}F"  #Line 2: temperature
                altCounter += 1
            else:
                lcd_line_2 = f"{self.current_state.id.upper()} @ {self.setPoint}F"  #Line 2: mode + set point
                altCounter += 1
                if altCounter >= 11:
                    self.updateLights()  #Refresh LEDs every 10s
                    altCounter = 1

            screen.updateScreen(lcd_line_1 + lcd_line_2)

            if DEBUG:
                print(f"Counter: {counter}")
            if (counter % 30) == 0:
                ser.write((self.setupSerialOutput() + "\n").encode())  #Send UART message
                counter = 1
            else:
                counter += 1
            sleep(1)

        screen.cleanupDisplay()

#Instantiate and run state machine
tsm = TemperatureMachine()
tsm.run()

#Setup GPIO buttons
greenButton = Button(24)
greenButton.when_pressed = tsm.processTempStateButton  #Toggle state

redButton = Button(20)
redButton.when_pressed = tsm.processTempIncButton  #Increase setpoint

blueButton = Button(25)
blueButton.when_pressed = tsm.processTempDecButton  #Decrease setpoint

#Main loop – keep program running
repeat = True
while repeat:
    try:
        sleep(30)
    except KeyboardInterrupt:
        print("Cleaning up. Exiting...")
        repeat = False
        tsm.endDisplay = True
        sleep(1)
