#!/usr/bin/python3
#
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2014 The moOde audio player project / Tim Curtis
#

#
# Stub script for lcd-updater.sh daemon
#

import requests
import socket
import subprocess

mydict = {}

with open("/var/local/www/currentsong.txt") as file1:
    for line in file1:
        mysplit = line.split("=")
        mydict[mysplit[0]] = mysplit[1].strip('\n')

#print(mydict)
mydict["h_name"] = socket.gethostname()
ips = subprocess.check_output(['hostname', '--all-ip-addresses'])
mydict["ip"] = ips.decode().split()[0]
moode_ver = result = subprocess.run(['moodeutl', '--mooderel'], stdout=subprocess.PIPE)
mydict["moode_ver"] = result.stdout.decode('utf-8')
try:
    r = requests.post('http://localhost:8080', data=mydict)
except Exception as e:
    print("Exception posting to localhost:8080 {}".format(e))
    pass
