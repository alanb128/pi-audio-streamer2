from flask import Flask, jsonify, request
import RPi.GPIO as GPIO
import time
import requests
import digitalio
import board
import urllib.parse
import threading
import atexit

exit_event = threading.Event()

# -----------------
# Set up display

from PIL import Image, ImageDraw, ImageFont
from adafruit_rgb_display import ili9341
from adafruit_rgb_display import st7789  # pylint: disable=unused-import
from adafruit_rgb_display import hx8357  # pylint: disable=unused-import
from adafruit_rgb_display import st7735  # pylint: disable=unused-import
from adafruit_rgb_display import ssd1351  # pylint: disable=unused-import
from adafruit_rgb_display import ssd1331  # pylint: disable=unused-import

# First define some constants to allow easy resizing of shapes.
BORDER = 20
FONTSIZE = 24

# Configuration for CS and DC pins (these are PiTFT defaults):
cs_pin = digitalio.DigitalInOut(board.D15)
dc_pin = digitalio.DigitalInOut(board.D25)
reset_pin = digitalio.DigitalInOut(board.D24)

# Config for display baudrate (default max is 24mhz):
BAUDRATE = 24000000

# Setup SPI bus using hardware SPI:
spi = board.SPI()

# pylint: disable=line-too-long
# Create the display:
# 2.0" ST7789
disp = st7789.ST7789(spi, rotation=90,  cs=cs_pin, dc=dc_pin, rst=reset_pin, baudrate=BAUDRATE)
# pylint: enable=line-too-long

# Create blank image for drawing.
# Make sure to create image with mode 'RGB' for full color.
if disp.rotation % 180 == 90:
    height = disp.width  # we swap height/width to rotate it to landscape!
    width = disp.height
else:
    width = disp.width  # we swap height/width to rotate it to landscape!
    height = disp.height

image = Image.new("RGB", (width, height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# image for about screen
img_about = Image.new("RGB", (width, height))

# default moOde cover image
img_default = Image.new("RGB", (width, height))
url = "http://host.docker.internal/images/default-album-cover.png"
img_default = Image.open(requests.get(url, stream=True).raw)
img_default = img_default.resize((200, 200), Image.BICUBIC)

# List of playlist images
img_playlists = []

img_title = Image.new("RGB", (320, 35))
img_artist = Image.new("RGB", (320, 35))
alt_display = False
img_progress = Image.new("RGB", (114,6))

# End display setup
# -------------------

VERSION = 0.5
DISPLAY_RESUME = 2.66  # seconds
DEBOUNCE = 900

current_song = {"artist": "", "album": "", "title": "", "coverurl": "", "encoded": "", "bitrate": "", "volume": 0, "mute": 0, "state": "", "hostname": "hostname", "ip": "ip", "moode": "moode"}
display_mode = 0 # (0=current/info;1=current image;2=sys info)
playlists = []
playlist1 = ""  # preset 1 playlist
playlist2 = ""  # preset 2 playlist

current_playlist = ""  # current or most recently played playlist
sel_playlist = -1   # selected playlist index
playlist_mode = False
sel_timer = 0  # time in select playlist mode; reverts in 6 seconds
progress_tick = 0  # used to decide when to update progress bar

def checker_thread():
    global playlist_mode, sel_timer, alt_display, image, progress_tick
    position = 0
    while not exit_event.is_set():
        #print("Thread!")
        if (not playlist_mode) and (current_song["state"] != "stop"):
            if display_mode == 0 or display_mode == 1:
                if alt_display:
                    image.paste(img_artist,  (0,205))
                else:
                    image.paste(img_title,  (0,205))
                disp.image(image)
                alt_display = not alt_display
        if playlist_mode:
            sel_timer = sel_timer + 1
        progress_tick = progress_tick + 1
        if progress_tick > 1:  # adjust this value for how often to update progress bar
            progress_tick = 0
        if progress_tick == 1:
            if current_song["state"] != "stop":
                if (not playlist_mode) and (display_mode == 0):
                    # update progress bar here
                    r = requests.get('http://host.docker.internal/command/?cmd=status')
                    position = parse_status(r.json())
                    #print("position: {}".format(position))
                    progress_draw = ImageDraw.Draw(img_progress)
                    progress_draw.rectangle([(0, 0), (position, 6)], outline = 0, fill = (201,201,201))
                    progress_draw.rectangle([(position + 1, 0), (114, 6)], outline = 0, fill = (96,96,96))
                    image.paste(img_progress, (207, 194))
        if sel_timer > 1:
            sel_timer = 0
            playlist_mode = False
            lcd_current()
        time.sleep(4)
    print("Thread exiting...")

def lcd_current():
    #
    # Decides what to display based on display_mode
    # Called by Flask route whenever moode state changes
    #

    print("current: display_mode {}; state: {}".format(display_mode, current_song["state"]))
    if playlist_mode:
        lcd_playlist()
    else:
        if display_mode == 0 or display_mode == 1:
            lcd_song()
        else:
            lcd_info()

def lcd_song():
    #
    # Display current song
    #

    global draw, image, img_title, img_artist, img_progress
    # Get drawing object to draw on image.
    #draw = ImageDraw.Draw(image)
    b_adj = 0  # adjust bitrate x axis display
    # Draw a black filled box to clear the image.
    draw.rectangle((0, 0, width, height), outline=0, fill=(0, 0, 0))
    disp.image(image)
    text_draw = ImageDraw.Draw(image)
    title_text = ""
    #font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", FONTSIZE-4)
    if current_song["state"] == "stop":
        title_text = "(stopped)"
        cover_image = img_default
        #draw.rectangle([(0, 0), (200, 200)], outline = (160,160,160), fill = (0,0,0))
        codec = " "
        bitrate = " "
    else:
        title_text = current_song["title"]

        #image = Image.open(current_song["coverurl"])
        url = "http://host.docker.internal" + current_song["coverurl"]
        cover_image = Image.open(requests.get(url, stream=True).raw)
        if display_mode == 1:
            # Scale the image to the smaller screen dimension
            image_ratio = cover_image.width / cover_image.height
            screen_ratio = width / height
            if screen_ratio < image_ratio:
                scaled_width = cover_image.width * height // cover_image.height
                scaled_height = height
            else:
                scaled_width = width
                scaled_height = cover_image.height * width // cover_image.width
            cover_image = cover_image.resize((scaled_width, scaled_height), Image.BICUBIC)
            # Crop and center the image
            #x = scaled_width // 2 - width // 2
            #y = scaled_height // 2 - height // 2
            #image = image.crop((x, y, x + width, y + height))
        else:
            cover_image = cover_image.resize((200, 200), Image.BICUBIC)
            #image.paste(cover_image, (0,0))
            
            codec = get_codec(current_song["encoded"])
            sample_rate = get_sample_rate(current_song["encoded"], current_song["bitrate"])
            #codec0 = e.split(",")
            #codec1 = codec0[0].split()
            #codec = codec1[0]
            #bitrate = codec1[1] + " k"
            #sample = codec1[1].split("/")
            #sample_rate = float(sample[1])

            # Load a TTF Font
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", FONTSIZE)

            # Draw Some Text
            #text_draw = ImageDraw.Draw(image)

            #title_draw = ImageDraw.Draw(img_title)
            #title_draw.rectangle((0, 0, 320, 35), outline=0, fill=(0, 0, 0))
            #title_draw.text((2, 5), title_text, font=font, fill=(255, 255, 255),)

            #artist_draw = ImageDraw.Draw(img_artist)
            #artist_draw.rectangle((0, 0, 320, 35), outline=0, fill=(0, 0, 0))
            #artist_draw.text((2, 5), current_song["artist"], font=font, fill=(255, 255, 255),)

            #image.paste(img_title,  (0,205)) 
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", FONTSIZE-4)
            text_draw.text((250, 78), codec, font=font, fill=(201, 201, 201),)
            sr_len = len(sample_rate)
            if sr_len < 1 or sr_len > 10:
                sr_len = 8
            # offsets for centering the sample_rate
            b_adj = [0, 0, 10, 8, 9, 6, 2, 0, -3, -5][sr_len - 1]
            text_draw.text((230 + b_adj, 108), sample_rate, font=font, fill=(201, 201, 201),)

            #print("sample rate: {}".format(sample_rate))
            if is_hd(current_song["encoded"], current_song["bitrate"]):  # draw HD icon
                draw.rectangle([(253, 144), (295, 173)], fill = (0,0,0), outline = (245, 225, 0)) 
                text_draw.text((259, 147), "HD", font=font, fill=(245, 225, 0),)

            if current_song["state"] == "play": 
                # draw play triangle
                draw.polygon([(260,25), (285, 40), (260,55)], fill = (255,255,255))
            elif current_song["state"] == "pause":
                draw.rectangle([(260, 25), (270, 55)], fill = (255,255,255))
                draw.rectangle([(275, 25), (285, 55)], fill = (255,255,255))
            elif current_song["state"] == "stop":
                draw.rectangle([(260, 25), (285, 55)], fill = (255,255,255))

            if current_song["state"] != "stop":  # draw initail progress bar
                #progress_draw = ImageDraw.Draw(img_progress)
                #progress_draw.rectangle([(0, 0), (4, 6)], outline = 0, fill = (201,201,201))
                #progress_draw.rectangle([(0, 0), (114, 6)], outline = 0, fill = (96,96,96))
                #image.paste(img_progress, (207, 194))
                r = requests.get('http://host.docker.internal/command/?cmd=status')
                position = parse_status(r.json())
                progress_draw = ImageDraw.Draw(img_progress)
                progress_draw.rectangle([(0, 0), (position, 6)], outline = 0, fill = (201,201,201))
                progress_draw.rectangle([(position + 1, 0), (114, 6)], outline = 0, fill = (96,96,96))
                image.paste(img_progress, (207, 194))
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", FONTSIZE)
    title_draw = ImageDraw.Draw(img_title)
    title_draw.rectangle((0, 0, 320, 35), outline=0, fill=(0, 0, 0))
    title_draw.text((2, 5), title_text, font=font, fill=(255, 255, 255),)

    artist_draw = ImageDraw.Draw(img_artist)
    artist_draw.rectangle((0, 0, 320, 35), outline=0, fill=(0, 0, 0))
    artist_draw.text((2, 5), current_song["artist"], font=font, fill=(255, 255, 255),)

    image.paste(img_title,  (0,205)) 

    image.paste(cover_image, (0,0))
    # Display image.
    disp.image(image)

def lcd_playlist():
   
    global draw, image
    # Get drawing object to draw on image.

    # Draw a black filled box to clear the image.
    draw.rectangle((0, 0, width, height), outline=0, fill=(0, 0, 0))
    disp.image(image)
    
    cover_image = img_playlists[sel_playlist]
    cover_image = cover_image.resize((200, 200), Image.BICUBIC)

    # Load a TTF Font
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", FONTSIZE)

    # Draw Some Text
    text_draw = ImageDraw.Draw(image)
    text_draw.text((2, 210), playlists[sel_playlist], font=font, fill=(255, 255, 255),)

    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", FONTSIZE-4)
    text_draw.text((216, 80), "press play", font=font, fill=(201, 201, 201),)
    text_draw.text((230, 110), "to start", font=font, fill=(201, 201, 201),)
    text_draw.text((230, 140), "playlist", font=font, fill=(201, 201, 201),)
    image.paste(cover_image, (0,0))
    # Display image.
    disp.image(image)

def get_codec(encoded):
    #
    # Returns codec of song for display
    #

    e = encoded.split()
    return e[0]

def get_sample_rate(encoded, bitrate):
    #
    # Returns sample rate or bitrate for mp3
    #

    e = encoded.split()
    codec = e[0]
    if codec == "FLAC":
        return e[1] + " k"
    elif codec == "DSD":
        p = float(e[1])
        return str(round(p, 1)) + " M"
    else:
        # Currently just MP3, add others as needed
        b = bitrate.split()
        print(bitrate)
        print(b)
        return str(b[0]) + " k"

def is_hd(encoded, bitrate):
    #
    # Returns true if song is considered HD
    #

    e = encoded.split()
    if e[0] != "MP3":
        if e[1] in ["24/44.1", "24/48", "24/88.2", "24/96", "24/192", "24/256", "24/512"]:
            return True
        else:
            if e[0] == "DSD":
                return True
            else:
                return False 

def lcd_info():
    #
    # Display device/sw info on screen
    #

    global draw, image
    disp.image(img_about)

def get_device_info():
    #
    # Creates info page to display
    #
    
    global img_about
    draw_about = ImageDraw.Draw(img_about)
    draw_about.rectangle((0, 0, width, height), outline=0, fill=(0, 0, 0))
    font1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
    font2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    font3 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 6)
    draw_about.text((100, 5), "m", font=font1, fill=(160, 160, 160),)
    draw_about.text((140, 5), "oO", font=font1, fill=(204, 102, 0),)
    draw_about.text((200, 5), "de", font=font1, fill=(160, 160, 160),)
    draw_about.text((250, 8), "tm", font=font3, fill=(160, 160, 160),)
    draw_about.line([(10, 55), (315, 55)], fill=(160,160,160), width=2)
    draw_about.text((10, 65), "ver:", font=font2, fill=(160, 160, 160),)
    draw_about.text((75, 65), current_song["moode"], font=font2, fill=(255, 255, 255),)
    draw_about.text((10, 95), "host:", font=font2, fill=(160, 160, 160),)
    draw_about.text((75, 95), current_song["hostname"], font=font2, fill=(255, 255, 255),)
    draw_about.text((10, 125), "IP:", font=font2, fill=(160, 160, 160),)
    draw_about.text((75, 125), current_song["ip"], font=font2, fill=(255, 255, 255),)
    draw_about.text((10, 155), "hw:", font=font2, fill=(160, 160, 160),)
    hw = cpu_info["Model"].split()
    draw_about.text((75, 155), hw[0] + " " + hw[1] + " " + hw[2], font=font2, fill=(255, 255, 255),)
    draw_about.text((75, 185), hw[3] + " " + hw[4] + " " + hw[5] + " " + hw[6], font=font2, fill=(255, 255, 255),)


def parse_cpuinfo():
    #
    # Parses /proc/cpuinfo and returns a dictionary of CPU information.
    #

    cpu_info = {}
    with open("/proc/cpuinfo") as f:
        for line in f:
            if line.strip():
                key, value = line.split(":", 1)
                cpu_info[key.strip()] = value.strip()

    return cpu_info

def sanitizer(mystring):
    #
    # removes anything but letters and numbers from input string
    # strings from moode can contain strange characters
    #
    out_string = ''
    for i in mystring:
        s = ord(i)
        if (s > 31) and (s < 127):
            out_string = out_string + i

    return out_string

def get_current_state():
    #
    # get current state from moode api
    #
    global current_song, current_volume
    
    r = requests.get('http://host.docker.internal/command/?cmd=get_currentsong')
    current = r.json()
    current_song["artist"] = sanitizer(current["artist"])
    current_song["album"] = sanitizer(current["album"])
    current_song["title"] = sanitizer(current["title"])
    current_song["encoded"] = sanitizer(current["encoded"])
    current_song["bitrate"] = sanitizer(current["bitrate"])
    current_song["volume"] = sanitizer(current["volume"])
    current_song["mute"] = sanitizer(current["mute"])
    current_song["state"] = sanitizer(current["state"])
    current_song["coverurl"] = sanitizer(current["coverurl"])
    current_volume = int(current_song["volume"])

def button_press(channel):
    #
    # Catches any key presses and performs appropriate action
    #
    
    print("Pressed {}".format(channel))
    global display_mode, current_playlist, sel_playlist, sel_timer, playlist_mode

    if channel == 4:  # play/pause/sel
        if not playlist_mode:  # not in sel playlist mode
            if current_song["state"] == "play":
                # pause
                r = requests.get('http://host.docker.internal/command/?cmd=pause')
            else:
                # play
                r = requests.get('http://host.docker.internal/command/?cmd=play')
        else:  # in sel playlist mode
            playlist_mode = False
            
            playlist(playlists[sel_playlist])  # play selected playlist
            # do more playlist stuff here

    elif channel == 26:  # next
        r = requests.get('http://host.docker.internal/command/?cmd=next')
        
    elif channel == 16:  # prev
        r = requests.get('http://host.docker.internal/command/?cmd=prev')

    elif channel == 27:  # preset 1 playlist
        playlist(playlist1)

    elif channel == 23:  # preset 2 playlist
        playlist(playlist2)

    elif channel == 13:  # display
        display_mode = display_mode + 1
        if display_mode > 2:
            display_mode = 0
        print("Now in display_mode: {}".format(display_mode))
        lcd_current()

    elif channel == 12:  # next playlist browse
        sel_timer = 0
        sel_playlist = sel_playlist + 1
        if sel_playlist > len(playlists) - 1:
            sel_playlist = 0
        playlist_mode = True
        lcd_current()

    elif channel == 20:  # prev playlist browse
        sel_timer = 0
        sel_playlist = sel_playlist - 1
        if sel_playlist < 0:
            sel_playlist = len(playlists) - 1  # last playlist
        playlist_mode = True
        lcd_current()

def get_playlists():
    #
    # get playlists and add to dict for preset buttons
    #
    
    global playlist1, playlist2, img_playlists
    p = []
    
    url="http://host.docker.internal/command/playlist.php?cmd=get_playlists"
    cookies = {'PHPSESSID': 'ho7vk67sqrjua8sme0pqhsjgdq'}
    headers = {"Content-type": "application/json","Accept": "application/json"}
    r = requests.get(url, headers=headers, cookies=cookies)
    playlists = r.json()
    playlist_count = 0
    for playlist in playlists:
        playlist_count = playlist_count + 1
        for attribute, value in playlist.items():
            #print("a: {}; v: {}".format(attribute, value))
            if attribute == "name":
                p.append(value)
                # Get playlist cover image
                url = "http://host.docker.internal/imagesw/playlist-covers/" + urllib.parse.quote(value) + ".jpg"
                print(url)
                cover_image = Image.open(requests.get(url, stream=True).raw)
                img_playlists.append(cover_image)
    if playlist_count > 0:
        playlist1 = p[0]
    if playlist_count > 1:
        playlist2 = p[1]

    return p
    
def playlist(playlist):
    #
    # Plays a playlist
    #
    r = requests.get('http://host.docker.internal/command/?cmd=clear')
    r = requests.get('http://host.docker.internal/command/?cmd=load%20' + urllib.parse.quote(playlist))
    r = requests.get('http://host.docker.internal/command/?cmd=random%201')
    r = requests.get('http://host.docker.internal/command/?cmd=play')


def parse_status(resp):

    #print("resp15: {}".format(resp["15"]))
    dur = resp["15"].split(":")
    elap = resp["13"].split(":")
    duration = int(float(dur[1].strip()))
    elapsed = int(float(elap[1].strip()))
    progress = int(((elapsed/duration) * 1.14) * 100)
    #print("{} : {}".format(elapsed, duration))
    return progress

app = Flask(__name__)

@app.route('/', methods=['POST'])
def post_api():

    global current_song, current_volume
    
    current_song["artist"] = sanitizer(request.form["artist"])
    current_song["album"] = sanitizer(request.form["album"])
    current_song["title"] = sanitizer(request.form["title"])
    current_song["encoded"] = sanitizer(request.form["encoded"])
    current_song["bitrate"] = sanitizer(request.form["bitrate"])
    current_song["volume"] = sanitizer(request.form["volume"])
    current_song["mute"] = sanitizer(request.form["mute"])
    current_song["state"] = sanitizer(request.form["state"])
    current_song["hostname"] = request.form["h_name"] + ".local"
    if current_song["ip"] == "ip":
        update_info = True
    else:
        update_info = False
    current_song["moode"] = request.form["moode_ver"]
    current_song["ip"] = request.form["ip"]
    if update_info:
        get_device_info()
    current_song["coverurl"] = sanitizer(request.form["coverurl"])

    
    current_volume = int(current_song["volume"])
    #print("h, m, i: {0} - {1} - {2}".format(current_song["hostname"], current_song["moode"], current_song["ip"]))
    #lcd_display("post")
    print("Received! {}".format(current_song))
    #lcd_display(current_song["title"])
    lcd_current()
    return '', 204

@app.route('/shutdown', methods=['POST'])
def shutdown_api():

    lcd_display("shutdown")
    
    lcd.backlight = False
    GPIO.output(27, 0)  # grn off
    GPIO.output(22, 1)  # red on
    return '', 204

@app.route('/reboot', methods=['POST'])
def reboot_api():

    lcd_display("reboot")
    return '', 204

@app.route('/')
def get_api():
    return jsonify("this is the API")

def on_shutdown():
    print("Ctrl+C pressed, exiting...")
    exit_event.set()
    #thread.join()  #  ensures the main thread waits for the worker thread to finish before terminating.

#  main thread of execution

# -------------------------
# set up GPIO

GPIO.setmode(GPIO.BCM)


GPIO.setup(4, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(4, GPIO.RISING, callback=button_press, bouncetime=DEBOUNCE)
GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(27, GPIO.RISING, callback=button_press, bouncetime=DEBOUNCE)
GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(23, GPIO.RISING, callback=button_press, bouncetime=DEBOUNCE)
GPIO.setup(13, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(13, GPIO.RISING, callback=button_press, bouncetime=DEBOUNCE)
GPIO.setup(26, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(26, GPIO.RISING, callback=button_press, bouncetime=DEBOUNCE)
GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(16, GPIO.RISING, callback=button_press, bouncetime=DEBOUNCE)
GPIO.setup(12, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(12, GPIO.RISING, callback=button_press, bouncetime=DEBOUNCE)
GPIO.setup(20, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(20, GPIO.RISING, callback=button_press, bouncetime=DEBOUNCE)


get_current_state()
lcd_current()
cpu_info = parse_cpuinfo()
#print(cpu_info)
get_device_info()

playlists = get_playlists()
#print(playlists)

atexit.register(on_shutdown)
# start a checker thread
x = threading.Thread(target=checker_thread)
x.start()

# start API server
app.run(host="0.0.0.0",port=5000,debug=True,use_reloader=False)
