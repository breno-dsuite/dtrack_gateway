pip3 install -r /home/pi/dtrack_gateway/requirements.txt
sudo cp /home/pi/dtrack_gateway/dtrack_gateway.service /etc/systemd/system/dtrack_gateway.service
sudo systemctl enable dtrack_gateway.service
sudo systemctl start dtrack_gateway.service