cd /home/ubuntu/dtrack_gateway && git stash && git pull
sudo cp /home/ubuntu/dtrack_gateway/dtrack/dtrack_gateway.service /etc/systemd/system/dtrack_gateway.service
sudo systemctl daemon-reload
sudo systemctl restart dtrack_gateway.service
