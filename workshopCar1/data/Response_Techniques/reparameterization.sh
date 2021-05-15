#!/bin/bash

ARG=$1

if [ $ARG = "apply" ]
then
	sudo chattr +i /etc/shadow
elif [ $ARG = "revert" ]
then
	sudo chattr -i /etc/shadow
fi
