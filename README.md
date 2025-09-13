# Raspberry Pi 5 Modded Minecraft Server
This document is for users who want a continuously running Minecraft server but do not want to keep their mail laptop/desktop running at all times. This will show you how to set up a raspberry pi to host your Minecraft server, and how to enable friends to connect to it remotely. 

Using a 16GB Raspberry Pi 5 with a 128GB micro SD card.
Minecraft version 1.21.7.
NeoForge version 21.7.25-beta.

## Table of Contents
0. Prerequisites
1. Imaging onto the SD card
2. Raspberry Pi Setup
3. Install Java 21
4. Install the NeoForge Server
5. Run the NeoForge Server
6. Connect to Serve with Friends

## 0. Prerequisites:
- Raspberry Pi 5 (16GB)
- 128GB A1 SD Card
- Laptop (for imaging and connecting to the raspberry pi)
- [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
- Tailscale account (its free!)

## 1. Imaging onto the SD card
- Within the Raspberry Pi Imager, select the Raspberry Pi OS Lite (64-bit) operating system to put onto the SD card.
- Within the settings, choose a username, password, SSID for your wifi, and the password.
- Set up a hostname and Enable SSH. Remember all of these credentials as they will be used to set up the server

## 2. Raspberry Pi Setup
1. `ssh` into the Raspberry Pi and enable internet access to set up the server
2. Ping the **hostname** using the **username** set in the imager settings: `ping hostname.local`
3. Copy IP address that appears in each `ping` and `ssh` into the Raspberry Pi: `ssh username@ip_address`
4. Run sudo `raspi-config`, then choose the first option to enter the wifi information
5. `sudo reboot` the Raspberry Pi

## 3. Install Java 21
Install JDK 21 onto the Raspberry Pi to use the server now that we have internet access:
```
mkdir minecraft_server. Then, cd minecraft_server
sudo apt update
sudo apt install -y gnupg2
sudo apt-key adv --keyserver hkps://keyserver.ubuntu.com --recv-keys 0xB1998361219BD9C9
echo "deb http://repos.azul.com/zulu/deb stable main" | sudo tee /etc/apt/sources.list.d/zulu.list
sudo apt update
sudo apt install -y zulu21-jdk-headless
java -version
```
## 4. Install the NeoForge Server
1. Install the server onto the raspberry pi: `java -jar neoforge-21.7.25-beta-installer.jar`
2. Run the server to generate and edit the eula.txt file: `./run.sh`
3. Edit the `eula.txt` file. Turn the eula variable from false to true, then save and exit the file

## 5. Run the NeoForge Server
Configure server settings and run the NeoForge Server
1. Run server to generate server files: `./run.sh`
2. Exit the server (`ctrl + c`) and there will be new files. Set your whitelist and server properties here
3. If a `/mods` folder is not present, create one. This is where you will copy/move all of your .jar mod files to. If you have a different world you want to play, copy/move the file into the `/world` folder
4. Move the Neoforge mod files from your desktop to your raspberry pi: `scp /path/to/local/file.jar pi@your_pi_ip_address:/path/to/destination/on/pi/`
5. Run the server again to make sure you can connect: `./run.sh`

## 6. Connect to Server with Friends
1. Shut down the server and install Tailscale onto the Pi: `curl -fsSL https://tailscale.com/install.sh | sh`
2. From the Pi, start and log into Tailscale: `sudo tailscale up`
3. In Tailscale, go to **Add Device > Linux** and add the Raspberry Pi as a device. Copy the IP address
4. Send Tailscale requests to friends for them to join
5. In Minecraft, go to **Multiplayer > Add Server**, then paste the IP address from step c
6. Run the server one more time: `./run.sh`
7. You should be connected! Everyone you invited to Tailscale will be able to connect to this IP address
