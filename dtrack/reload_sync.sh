cd /home/dtrack/dtrack_gateway && git stash && git pull
sudo cp /home/dtrack/dtrack_gateway/dtrack/dtrack_sync.service /etc/systemd/system/dtrack_sync.service
sudo systemctl daemon-reload
sudo systemctl restart dtrack_sync.service
