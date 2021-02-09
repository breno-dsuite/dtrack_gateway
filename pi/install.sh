#!/bin/bash

sudo apt install unixodbc-dev -y python-usb python3-usb
sudo pip3 install -r /home/pi/dtrack_gateway/requirements.txt
sudo cp /home/pi/dtrack_gateway/pi/dtrack_gateway.service /etc/systemd/system/dtrack_gateway.service
sudo systemctl daemon-reload
sudo systemctl enable dtrack_gateway.service
sudo systemctl start dtrack_gateway.service

line="*/15 * * * * sh /home/pi/dtrack_gateway/pi/reload.sh"
(crontab -u pi -l; echo "$line" ) | crontab -u pi -
