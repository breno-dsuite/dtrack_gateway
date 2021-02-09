#!/bin/bash

sudo apt install unixodbc-dev -y python-usb python3-usb python3-pip
sudo pip3 install -r /home/dtrack/dtrack_gateway/requirements.txt
sudo cp /home/dtrack/dtrack_gateway/dtrack/dtrack_gateway.service /etc/systemd/system/dtrack_gateway.service
sudo systemctl daemon-reload
sudo systemctl enable dtrack_gateway.service
sudo systemctl start dtrack_gateway.service

line="*/15 * * * * sh /home/dtrack/dtrack_gateway/dtrack/reload.sh"
(crontab -u root -l; echo "$line" ) | crontab -u root -
