# Minecraft Server Manager

A management system for a modded NeoForge Minecraft server running on a Raspberry Pi. Tested with Minecraft 26.3 and NeoForge 26.3.0.60-beta / 26.3.0.76.

There are three parts:

| Part | Runs on | What it does |
|---|---|---|
| **API** (`pi-backend/`) | Raspberry Pi | FastAPI service that starts/stops the server, sends console commands over RCON, manages mods, whitelist and config files, and streams the server log over WebSocket. Port 8080. |
| **Admin app** (`admin-app/`) | Your Mac or PC | PyQt6 desktop dashboard for the API. |
| **Player portal** (`player-portal/`) | Raspberry Pi | Small Flask website where players see server status, download the mods and request whitelist access. Port 5000. |

Players and the admin reach the Pi over [Tailscale](https://tailscale.com), so none of these ports need to be opened to the internet.

---

## Admin app features

| Page | Features |
|---|---|
| **Dashboard** | Server status, Start / Stop / Restart / Wake, Pi CPU, memory, disk and temperature, non-whitelisted join alerts |
| **Console** | Live server log (last 200 lines on connect, follows the log across server restarts), send server commands, optional filter for RCON noise |
| **Players** | Online players, whitelist editor, approve/deny whitelist requests from the portal |
| **Mods** | Group mods into **packages**, tick which mods in each package are active, upload many `.jar` files at once, and switch the server to a package in one click |
| **Config** | Edit `server.properties`, JVM arguments and NeoForge/mod config files |

### Mod packages

- **+ New Package** creates a package from mod files, a folder of mods, or the mods currently enabled on the server.
- Each mod in a package has a checkbox. Use the filter plus **Check All / Uncheck All**, or Shift/⌘-click to highlight mods and use the **Highlighted** buttons.
- **Activate Package on Server** enables the checked mods in that package and moves every other mod into `mods_disabled/`. Nothing is deleted. Restart the server afterwards.
- Uploaded mods stay disabled until their package is activated.
- **Download Packages…** zips one or more packages' checked mods. One package gives a zip of jars ready for a `mods` folder; several give one zip with a folder per package.
- Packages are stored in the admin app's settings and published to the Pi (`mod_packages.json` in the server folder, mod file names only) shortly after every change, so the player portal can offer them.

---

## Part 1: API on the Raspberry Pi

### Prerequisites

```bash
sudo apt install tmux python3-venv

cd ~/minecraft-manager/pi-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Enable RCON in `server.properties`

```properties
enable-rcon=true
rcon.port=25575
rcon.password=choose-a-long-random-password
```

Never reuse this password anywhere else, and never commit `server.properties`.

### Configure

Copy `.env.example` to `.env` and fill in real values (`.env` is git-ignored):

- `MC_SERVER_DIR` — your Minecraft server folder, e.g. `/home/pi/minecraft_server`
- `RCON_PASSWORD` — must match `rcon.password`
- `RCON_PORT` — must match `rcon.port` (default 25575)
- `API_KEY` — a long random string. **Every API request must send it** (`X-API-Key` header), so set the same value in the admin app's Settings and in the player portal's `.env`. Generate one with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
- `ALLOWED_ORIGINS` — the player portal's address

Edit `minecraft-manager.service` and replace the example user `pi` and `/home/pi/...` paths with your own username and home folder.

### Install as a service (starts on boot)

```bash
sudo cp minecraft-manager.service /etc/systemd/system/
sudo mkdir -p /etc/systemd/system/minecraft-manager.service.d
sudo cp minecraft-manager.service.d/killmode.conf /etc/systemd/system/minecraft-manager.service.d/
sudo systemctl daemon-reload
sudo systemctl enable --now minecraft-manager
sudo systemctl status minecraft-manager
```

`killmode.conf` sets `KillMode=process`. Without it, restarting the API also kills a Minecraft server that was started from the app, because systemd treats the server as part of the API service.

### How the API starts the server

Start runs the same command you would type yourself:

```bash
tmux new-session -d -s minecraft -c "$MC_SERVER_DIR" './run.sh nogui'
```

`run.sh` is the launcher written by the NeoForge installer, so mods and `user_jvm_args.txt` are always used. The tmux session **must be named `minecraft`** for Status / Stop / Console commands to find it.

### Memory (`user_jvm_args.txt`)

`run.sh` reads Java settings from `user_jvm_args.txt` in the server folder. Out of the box every line is a comment, so Java only gets a quarter of the Pi's RAM. Add a line such as:

```
-Xmx6G
```

Leave roughly 1 GB for the operating system (on a 2 GB board use about `-Xmx1300M`). Make sure the file ends with a newline before appending. Note: the admin app's **Config → JVM Arguments** tab edits `jvm_args.txt`, which `run.sh` does not read.

---

## Part 2: Player portal on the Raspberry Pi

```bash
cd ~/minecraft-manager/player-portal
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # set API_KEY to the same value as the API, and a random FLASK_SECRET
```

Edit `player-portal.service` with your own username and paths, then:

```bash
sudo cp player-portal.service /etc/systemd/system/minecraft-player-portal.service
sudo systemctl daemon-reload
sudo systemctl enable --now minecraft-player-portal
```

The portal listens on `127.0.0.1:5000`. To share it with players over your tailnet only, use `tailscale serve` on the Pi.

Players can see server status and who's online, download the **active mod package** (or tick several packages and download them together), and follow the join steps. Downloads go through the portal to the API, so the API key never reaches players' browsers.

---

## Part 3: Admin app on your computer

```bash
cd server-manager/admin-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

On first launch, open **Settings** (bottom of the sidebar) and enter your Pi's Tailscale IP or MagicDNS name, SSH username, the server folder on the Pi, API port `8080`, the RCON password and the API key. These are saved only on your computer.

---

## Security notes

- Keep the API, RCON and portal reachable only over your LAN/tailnet. Do not port-forward 8080, 5000 or 25575.
- Set `white-list=true` and `online-mode=true` in `server.properties`.
- Never commit `.env`, `server.properties`, `whitelist.json`, `ops.json`, TLS certificates or keys, or your world folder. The repository's `.gitignore` excludes them.

---

## Troubleshooting

**Admin app can't connect** — check the Pi's Tailscale IP (`tailscale ip`), that `sudo systemctl status minecraft-manager` is running, and that the API key matches.

**Console is empty** — the API sends the last 200 log lines when the console connects. If nothing appears, check the API is running and the WebSocket (`ws://<pi>:8080/ws/log`) is reachable.

**Server won't start from the app** — check `tmux` is installed, `MC_SERVER_DIR` is correct and contains `run.sh`, and run `./run.sh nogui` by hand to see the error. A common cause after an upgrade is a missing required library mod; the error is near the top of `logs/latest.log`.
