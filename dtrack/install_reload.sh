#!/bin/bash

line="*/15 * * * * sh /home/dtrack/dtrack_gateway/dtrack/reload.sh"
(sudo crontab -l; echo "$line" ) | sudo crontab -
