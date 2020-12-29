#!/usr/bin/python3

import yaml
import sys

data = None
controller_ip = ""

with open(sys.argv[1]) as f:
	data = yaml.load(f, Loader=yaml.FullLoader)

fp = open("hosts", "w")

role = "controller"
fp.write("[" + str(role) + "]\n")
for n in data["nodes"]:
   if n["role"].strip() == role:   
      fp.write(n["oam_ip"] + "\n")
	
role = "compute"
fp.write("\n[" + str(role) + "]\n")
for n in data["nodes"]:
   if n["role"].strip() == role:   
      fp.write(n["oam_ip"] + "\n")

role = "storage"
fp.write("\n[" + str(role) + "]\n")
for n in data["nodes"]:
   if n["role"].strip() == role:   
      fp.write(n["oam_ip"] + "\n")


for n in data["nodes"]:
   fp.write("\n[" + str(n["name"]) + "]\n")
   fp.write(n["oam_ip"] + "\n")

fp.close()
