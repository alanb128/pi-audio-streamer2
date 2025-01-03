# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

"""
This test will initialize the display using displayio and draw a solid green
background, a smaller purple rectangle, and some yellow text.
"""
import board
import terminalio
import displayio
import digitalio
import busio
import time
import adafruit_adg72x

print("-- STARTING --")

# define GPIO
# gp6 = 3.3v enable - not currently used
pin_6 = digitalio.DigitalInOut(board.GP6)
pin_6.direction = digitalio.Direction.OUTPUT
# gp11 = pi power on (pi gp3 to gnd)
pin_11 = digitalio.DigitalInOut(board.GP11)
pin_11.direction = digitalio.Direction.OUTPUT
# gp12 = pwr button
pin_12 = digitalio.DigitalInOut(board.GP12)
pin_12.direction = digitalio.Direction.INPUT
pin_12.pull = digitalio.Pull.UP
# gp13 = pwr LED
pin_13 = digitalio.DigitalInOut(board.GP13)
pin_13.direction = digitalio.Direction.OUTPUT
# gp28 = pi shutdown sig
pin_28 = digitalio.DigitalInOut(board.GP28)
pin_28.direction = digitalio.Direction.OUTPUT
# gp27 = display BL
pin_27 = digitalio.DigitalInOut(board.GP27)
pin_27.direction = digitalio.Direction.OUTPUT

# TEST ONLY
# gp26 = test button
#pin_26 = digitalio.DigitalInOut(board.GP26)
#pin_26.direction = digitalio.Direction.INPUT
#pin_26.pull = digitalio.Pull.UP
#c = 0

# Define I2C for using ADG729 switches
i2c = busio.I2C(scl=board.GP3, sda=board.GP2)
switch = adafruit_adg72x.ADG72x(i2c, 0x44)
switch2 = adafruit_adg72x.ADG72x(i2c, 0x45)

# STARTING VALUES - assumne Pi will PWR ON when first plugged in

pin_13.value = False  # LED OFF
switch2.channels = 2, 6 # Switch display to Pico
switch.channels = 2, 6 # Switch display to Pico
pin_28.value = True  # Pi shutdown pin high
pin_11.value = True  # Pi startup pin high



# Starting in CircuitPython 9.x fourwire will be a seperate [sic] internal library
# rather than a component of the displayio library
try:
    from fourwire import FourWire
except ImportError:
    from displayio import FourWire
from adafruit_display_text import label
from adafruit_st7789 import ST7789

# Release any resources currently in use for the displays
displayio.release_displays()

#spi = board.SPI()
spi = busio.SPI(clock=board.GP18, MOSI=board.GP19, MISO=board.GP16)
tft_cs = board.GP17
tft_dc = board.GP15

display_bus = FourWire(spi, command=tft_dc, chip_select=tft_cs, reset=board.GP14)

display = ST7789(display_bus, width=320, height=240, rotation=270)

def WriteDisplay(msg):
    # Make the display context
    splash = displayio.Group()
    display.root_group = splash

    color_bitmap = displayio.Bitmap(320, 240, 1)
    color_palette = displayio.Palette(1)
    color_palette[0] = 0x0000F00  # Black

    bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)
    splash.append(bg_sprite)

    # Draw a smaller inner rectangle
    #inner_bitmap = displayio.Bitmap(280, 200, 1)
    #inner_palette = displayio.Palette(1)
    #inner_palette[0] = 0xAA0088  # Purple
    #inner_sprite = displayio.TileGrid(inner_bitmap, pixel_shader=inner_palette, x=20, y=20)
    #splash.append(inner_sprite)

    # Draw a label
    text_group = displayio.Group(scale=3, x=57, y=120)
    text = msg
    text_area = label.Label(terminalio.FONT, text=text, color=0xFFFFFF)
    text_group.append(text_area)  # Subgroup for text scaling
    splash.append(text_group)

def PowerSwitch(p):
    #print('power on: {}'.format(power_on))
    if p:
        # POWER ON
        print('Starting up...')
        #switch2.channels = 2, 6 # Switch display to Pico
        #switch.channels = 2, 6 # Switch display to Pico
        time.sleep(0.5)
        pin_13.value = False  # LED is OFF when pwr on
        pin_27.value = True  # Display BL ON
        #WriteDisplay('Please wait')
        
        switch2.channels = 3, 7 # Switch display to Pi
        switch.channels = 3, 7 # Switch display to Pi
        pin_11.value = False  # pi startup
        time.sleep(0.3)
        pin_11.value = True
        time.sleep(2)
        
        print('Power up complete... channels: {}/{}.'.format(switch.channels, switch2.channels))
    else:
        # POWER OFF
        print('Starting power down sequence...')
        #WriteDisplay('shutting down...')
        switch2.channels = 2, 6 # Switch display to Pico
        switch.channels = 2, 6 # Switch display to Pico
        WriteDisplay('shutting down...')
        time.sleep(0.5)
        #WriteDisplay('shutting down...')
        pin_28.value = False  # pi shutdown
        time.sleep(0.3)
        pin_28.value = True
        time.sleep(5)
        pin_27.value = False  # Display BL OFF
        WriteDisplay('Starting up...')
        pin_13.value = True  # LED is ON when pwr off
        print('Power down complete.')
        
# Finish start up sequence, assuming Pi is powering up...
# Now that display is setup, draw the wait message then switch the display
pin_27.value = True  # Display BL ON
WriteDisplay('Starting up...')
time.sleep(1)
switch2.channels = 3, 7 # Switch display to Pi
switch.channels = 3, 7 # Switch display to Pi
# ---------------------
# TEST - remove - start the Pi
#pin_11.value = False  # pi startup
#time.sleep(0.3)
#pin_11.value = True
# -----------------------

power_on = True
print('Start up complete... channels: {}/{}.'.format(switch.channels, switch2.channels))

# Main loop
while True:
    if pin_12.value == False:
        power_on = not power_on
        print('Power btn pressed; power on: {}'.format(power_on))
        PowerSwitch(power_on)
        # switch debounce:
        time.sleep(1.1)  # was 0.6 but switch is very dirty
        
