# Create a Modded NeoForge Minecraft Server on Raspberry Pi 5
This document is for Minecraft users who want a continuously running Minecraft server but do not want to keep their main laptop/desktop running at all times. You will learn how to set up a raspberry pi, how to set up your Minecraft server with your world + mods, and how to enable friends to connect to the world remotely.

- 16GB Raspberry Pi 5 with a 128GB micro SD card (Fall 2025)
- Minecraft version 26.3
- NeoForge version 26.3.0.60-beta (26.3.0.76, the first stable 26.3 build, also works)
- Java 25

This repo also includes a [Server Manager](server-manager/README.md): a desktop admin app, a Pi API and a player website for running the server without typing commands.

## Table of Contents
1. Prerequisites
2. Image OS onto the SD card
3. Raspberry Pi Setup
4. Install Java 25
5. Install the NeoForge Server
6. Run the NeoForge Server
7. Connect to Server with Friends
8. Upgrading from Minecraft 1.21.7 to 26.3
9. Performance Tips
10. Playing on a Steam Deck

## 1. Prerequisites:
- Raspberry Pi 5 (16GB)
- 128GB A1 SD Card
- Laptop (for imaging and connecting to the raspberry pi)
- [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
- Tailscale account (its free!)

## 2. Image OS onto the SD card
The SD card will hold the operating system (OS) and store your files. To get the OS onto the Raspberry Pi, use the Raspberry Pi Imager to put the OS image onto the SD card.
- Within the Raspberry Pi Imager, select the Raspberry Pi OS Lite (64-bit) operating system to put onto the SD card.
- Within the settings, choose a username, password, SSID for your wifi, and the password.
- Set up a hostname and Enable SSH. Remember all of these credentials as they will be used to set up the server

## 3. Raspberry Pi Setup
1. `ssh` into the Raspberry Pi and enable internet access to set up the server
2. Ping the **hostname** using the **username** set in the imager settings: `ping hostname.local`
3. Copy IP address that appears in each `ping` and `ssh` into the Raspberry Pi. The part before the `@` is your **username**, not the hostname: `ssh username@ip_address`
4. Run sudo `raspi-config`, then choose the first option to enter the wifi information
5. `sudo reboot` the Raspberry Pi

> **"Permission denied (publickey)"?** Check that you used your username (not the hostname) before the `@`. If the Pi only allows SSH keys, each computer you connect from needs its public key (`~/.ssh/id_ed25519.pub`) added to `~/.ssh/authorized_keys` on the Pi.

## 4. Install Java 25
Minecraft 26.3 requires Java 25. Install JDK 25 onto the Raspberry Pi now that we have internet access:
```
mkdir minecraft_server
cd minecraft_server
sudo apt update
sudo apt install -y gnupg2
sudo apt-key adv --keyserver hkps://keyserver.ubuntu.com --recv-keys 0xB1998361219BD9C9
echo "deb http://repos.azul.com/zulu/deb stable main" | sudo tee /etc/apt/sources.list.d/zulu.list
sudo apt update
sudo apt install -y zulu25-ca-jdk-headless
java -version
```
`java -version` should print version 25. Older Java versions can stay installed alongside it.

## 5. Install the NeoForge Server
1. Download the server installer from [NeoForge's Maven](https://maven.neoforged.net/releases/net/neoforged/neoforge/) (the version number starts with the Minecraft version, e.g. `26.3.0.60-beta` is for Minecraft 26.3):
   ```
   wget https://maven.neoforged.net/releases/net/neoforged/neoforge/26.3.0.60-beta/neoforge-26.3.0.60-beta-installer.jar
   ```
2. Install the server onto the raspberry pi: `java -jar neoforge-26.3.0.60-beta-installer.jar --installServer`
3. Run the server to generate and edit the eula.txt file: `./run.sh`
4. Edit the `eula.txt` file. Turn the eula variable from false to true, then save and exit the file

The installer writes `run.sh`. Its last line decides which NeoForge (and therefore Minecraft) version runs, for example `@libraries/net/neoforged/neoforge/26.3.0.60-beta/unix_args.txt`. To pin the server to Java 25 even if the default Java changes later, edit that line to start with `exec /usr/lib/jvm/zulu25/bin/java`.

## 6. Run the NeoForge Server
Configure server settings and run the NeoForge Server
1. Run server to generate server files: `./run.sh`
2. Exit the server (`ctrl + c`) and there will be new files. Set your whitelist and server properties here
3. Give Java enough memory: open `user_jvm_args.txt`, which is all comments by default (so Java only gets a quarter of your RAM), and add a line with no `#` in front, e.g. `-Xmx8G` on a 16GB Pi. Make sure the file ends with a new line first.
4. If a `/mods` folder is not present, create one. This is where you will copy/move all of your .jar mod files to. If you have a different world you want to play, copy/move the file into the `/world` folder
5. Move the Neoforge mod files from your desktop to your raspberry pi: `scp /path/to/local/file.jar username@your_pi_ip_address:/path/to/destination/on/pi/`
6. Run the server again to make sure you can connect: `./run.sh`

## 7. Connect to Server with Friends
1. Shut down the server and install Tailscale onto the Pi: `curl -fsSL https://tailscale.com/install.sh | sh`
2. From the Pi, start and log into Tailscale: `sudo tailscale up`
3. In Tailscale, go to **Add Device > Linux** and add the Raspberry Pi as a device. Copy the IP address
4. Send Tailscale requests to friends for them to join. Everyone you invited to Tailscale will be able to connect to the IP address of the Raspberry Pi device from the previous step.
5. In Minecraft, go to **Multiplayer > Add Server**, then paste the IP address from step 3. On the same Wi-Fi as the Pi you can also use its local IP address.
6. Leave server running in the background. This one command starts the server in a detached `tmux` session called `minecraft`:
```
sudo apt update
sudo apt install tmux
tmux new-session -d -s minecraft -c ~/minecraft_server './run.sh nogui'
```
7. Watch it start with `tail -f ~/minecraft_server/logs/latest.log`. It's ready when you see `Done (...)! For help, type "help"`. Press `ctrl+c` to stop watching (the server keeps running). You can now type `exit` to leave the Raspberry Pi terminal and the server will still be on.
8. To open the server console later: `tmux attach-session -t minecraft`. Press `ctrl+b`, then `d` to detach again. To shut the server down safely, type `stop` in the console.

> Keep the session name `minecraft` if you use the [Server Manager](server-manager/README.md); it looks for a session with exactly that name.

## 8. Upgrading from Minecraft 1.21.7 to 26.3
Upgrading converts your world permanently, so do it carefully:
1. **Back up the world first.** Stop the server and copy the `world` folder to another computer, e.g. `scp -r username@your_pi_ip_address:minecraft_server/world ~/Documents/world-backup`.
2. **Get 26.3 NeoForge versions of every mod.** Mods built for 1.21.7 will not load. On CurseForge, filter the **Files** tab by game version 26.3 and loader NeoForge. Some mods have separate Forge and NeoForge pages (e.g. TerraBlender), so check you have the NeoForge one.
3. **Add every required library.** A missing required mod stops the whole server from starting. Each mod's **Relations** tab on CurseForge lists its required dependencies. Libraries we needed: TerraBlender (for Biomes O' Plenty), Collective (Stack Refill), Shogi (Waystones), SuperMartijn642's Core Lib (Connected Glass). Fusion (Connected Textures) is only needed on players' computers. Watch out for different mods with the same name — check the author.
4. **Blocks from mods you drop are deleted** from the world when each chunk loads. Blocks from mods you keep, and anything vanilla, stay.
5. Install Java 25 and the 26.3 NeoForge server (sections 4 and 5). The old NeoForge version stays installed, so you can switch back by restoring your world backup and the old `run.sh`.
6. Start the server and read `logs/latest.log`. The first start converts the world and takes longer.

Known issues we hit on 26.3:
- Old Serene Seasons game rules can't be read by 26.3, so the world's game rules reset to defaults. Re-apply any custom ones with `/gamerule`.
- More Decorative Blocks 1.3.0 references block tags that don't exist, which breaks the `minecraft:wall_post_override` tag and, through it, Incendium's special weapons and castle mobs. Update or remove More Decorative Blocks to fix Incendium.

## 9. Performance Tips
- Lower `view-distance` and `simulation-distance` in `server.properties` (e.g. 6 and 5). This cuts the server's work by more than half.
- Keep the Pi cool. Check with `vcgencmd measure_temp`; above about 80°C it slows itself down.
- Exploring new land is the heaviest work. Pre-generating the area around spawn (e.g. with the Chunky mod) helps.
- Set `max-players` to what your Pi can actually handle.

## 10. Playing on a Steam Deck
1. In Desktop Mode, install **Prism Launcher** from Discover and sign in with your Microsoft account.
2. **Add Instance** → Minecraft **26.3**, mod loader **NeoForge**, same version as the server. Let Prism download Java 25 if it asks.
3. **Edit → Settings → Java**: set maximum memory to about 6144 MB.
4. Right-click the instance → **Folder**, open `minecraft/mods` and copy in the same mod `.jar` files as the server (plus any client-only libraries like Fusion).
5. To launch from Gaming Mode, add Prism Launcher to Steam as a non-Steam game.
