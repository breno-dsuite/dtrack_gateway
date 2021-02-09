sudo apt install unixodbc-dev -y python-usb python3-usb python3-pip
sudo pip3 install -r /home/ubuntu/dtrack_gateway/requirements.txt
sudo cp /home/ubuntu/dtrack_gateway/ubuntu/dtrack_gateway.service /etc/systemd/system/dtrack_gateway.service
sudo systemctl daemon-reload
sudo systemctl enable dtrack_gateway.service
sudo systemctl start dtrack_gateway.service
