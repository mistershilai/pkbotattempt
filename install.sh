#!/bin/bash

if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

apt install postgresql



apt install python3-venv

python3 -m venv venv
source venv/bin/activate

pip install discord.py
pip install psycopg2
