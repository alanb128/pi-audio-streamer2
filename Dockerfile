FROM balenalib/raspberrypi4-64-debian-python:3.11-bookworm-build

# Don't prompt with any configuration questions
ENV DEBIAN_FRONTEND noninteractive

# Enable udevd so that plugged dynamic hardware devices show up in our container.
ENV UDEV=1

WORKDIR /usr/src/app

RUN apt update && apt install -y git nano curl


RUN apt-get update && apt-get install -y i2c-tools python3-pil python3-numpy
 
COPY *.py ./

RUN pip3 install --upgrade setuptools requests lgpio \
    rpi-lgpio adafruit-blinka \
    adafruit-circuitpython-rgb-display \
    flask

CMD ["python3", "controller.py"]
