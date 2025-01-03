# pi-audio-streamer2
An updated audiophile component Pi music player/streamer using [moOde Audio](https://moodeaudio.org/).

This updated version of the [previous streamer](https://github.com/alanb128/audio-streaming-box) adds a full color display, Pi Pico microcontroller for powewr management and display switching. See the new video!

## Hardware required


## Setup

### Hardware

### Software - Pi
- add the following to `/boot/firmware/config.txt`:
```
dtparam=spi=on
dtoverlay=gpio-shutdown,gpio_pin=14 
```
- In the moode UI, under "Other peripherals" in the "Peripherals" menu, turn on  "LCD updater".
(The LCD update engine runs the lcd-updater.py script whenever UI state changes.
A stub lcd-updater.py script is located in the /var/local/www/commandw/ directory. It also originally updated ~/lcd.txt via /var/local/www/currentsong.txt but has since been removed.)

- SSH into your Moode Pi (Using the username/password entered when flashing the SD card) - You can use the convenient "Web SSH" in the "Security" section of the "System" page in moOde
  
- Install Docker on the pi: https://raspberrytips.com/docker-on-raspberry-pi/ - make sure it starts automatically
  
- Clone this repo to ~ on device
  
- Update /var/local/www/commandw/lcd_updater.py and restart.sh with the included modified files.
  
- Issue docker compose up -d to start the container. It should always load on its own going forward.

## Software - Pico

- install CircuitPython
  
- Load drivers for

- Load the file
