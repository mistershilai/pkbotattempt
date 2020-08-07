#!/bin/bash

# ssh pi@raspberrypi.local "rm -r ~/bot/src/"
scp -r $PWD/../src/* pi@raspberrypi.local:~/bot/src
