#!/bin/bash

ARG=$1

if [ $ARG = "apply" ]
then
	sudo reboot
elif [ $ARG = "revert" ]
then
	echo "revert"
fi
