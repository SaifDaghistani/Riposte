#!/bin/bash

ARG=$1

if [ $ARG = "apply" ]
then
	echo "Stopping and disabling SSH"
	sudo systemctl stop ssh && sudo systemctl disable ssh
	echo "Stopping and disabling bluetooth"
	sudo systemctl stop bluetooth && sudo systemctl disable bluetooth
	echo "Stopping and disabling cron"
	sudo systemctl stop cron && sudo systemctl disable cron
	echo "Stopping and disabling exim4"
	sudo systemctl stop exim4 && sudo systemctl disable exim4
	echo "Stopping and disabling nfs-common"
	sudo systemctl stop nfs-common && sudo systemctl disable nfs-common
elif [ $ARG = "revert" ]
then
	echo "Starting and enabling SSH"
	sudo systemctl start ssh && sudo systemctl enable ssh
	echo "Starting and enabling bluetooth"
	sudo systemctl start bluetooth && sudo systemctl enable bluetooth
	echo "Starting and enabling cron"
	sudo systemctl start cron && sudo systemctl enable cron
	echo "Starting and enabling exim4"
	sudo systemctl start exim4 && sudo systemctl enable exim4
	echo "Starting and enabling nfs-common"
	sudo systemctl start nfs-common && sudo systemctl enable nfs-common
fi
