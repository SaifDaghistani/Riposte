#!/bin/bash

ADDRESS=$1

sshpass -p "test" ssh -o StrictHostKeyChecking=no pi@$ADDRESS << ENDSSH

sudo chmod +x /etc/shadow

ENDSSH
