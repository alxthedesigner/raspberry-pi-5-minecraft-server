"""
Player Portal - Flask web app.
Read-only view of server status for remote players.
Connects to the FastAPI backend running on the Pi.
"""
from dotenv import load_dotenv
load_dotenv()

import os
import requests
from flask import Flask, render_template, redirect, url_for, flash, jsonify, request, Response, stream_with_context

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "minecraft-portal-secret-change-me")

# FastAPI backend URL (same machine if hosted on Pi, or Tailscale IP)
API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8080")
API_KEY = os.environ.get("API_KEY", "")


def _api_headers() -> dict:
    return {"X-API-Key": API_KEY} if API_KEY else {}


def _api_get(path: str, default=None):
    try:
        r = requests.get(f"{API_BASE}{path}", headers=_api_headers(), timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return default


def _api_post(path: str):
    try:
        r = requests.post(f"{API_BASE}{path}", json={}, headers=_api_headers(), timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"success": False, "message": str(e)}


def _display_name(filename: str) -> str:
    """Strip .jar and version suffixes to get a human-readable mod name."""
    import re
    name = filename.removesuffix(".jar")
    # Remove version strings like -1.21.7-19.4.0, -forge-19.4.0, -mc1.21+build.42, etc.
    name = re.sub(r'[-_](?:mc|forge|neoforge|fabric|v)?[\d][\d._+\-]*.*$', '', name, flags=re.IGNORECASE)
    return name.replace("-", " ").replace("_", " ").strip().title()


@app.route("/")
def index():
    status = _api_get("/api/status", {})
    players_data = _api_get("/api/players", {})
    mods_data = _api_get("/api/mods", {})
    packages_data = _api_get("/api/packages", {})

    online = status.get("minecraft_online", False)
    players = players_data.get("players", [])
    enabled_mods = mods_data.get("enabled", [])
    mods = [{"filename": m["filename"], "display": _display_name(m["filename"])} for m in enabled_mods]
    active = packages_data.get("active", "")
    packages = [
        {"name": p["name"], "count": sum(1 for on in p.get("mods", {}).values() if on), "active": p["name"] == active}
        for p in packages_data.get("packages", [])
    ]
    packages = sorted((p for p in packages if p["count"]), key=lambda p: (not p["active"], p["name"].lower()))

    return render_template(
        "index.html",
        online=online,
        players=players,
        player_count=len(players),
        mods=mods,
        mod_count=len(mods),
        packages=packages,
        version=status.get("version", "?"),
        loader=status.get("loader", "NeoForge"),
    )


@app.route("/wake", methods=["POST"])
def wake_server():
    result = _api_post("/api/wake")
    if result.get("success"):
        flash("Server is starting up! Check back in a minute.", "success")
    else:
        flash(result.get("message", "Could not wake server."), "danger")
    return redirect(url_for("index"))


@app.route("/mods/download-all")
def download_all_mods():
    r = requests.get(f"{API_BASE}/api/mods/download-all", headers=_api_headers(), stream=True, timeout=300)
    if not r.ok:
        flash("Could not download mods.", "danger")
        return redirect(url_for("index"))
    return Response(
        stream_with_context(r.iter_content(chunk_size=8192)),
        content_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=mods.zip"},
    )


@app.route("/mods/download/<filename>")
def download_mod(filename: str):
    r = requests.get(f"{API_BASE}/api/mods/{filename}/download", headers=_api_headers(), stream=True, timeout=30)
    if not r.ok:
        flash("Mod not found.", "danger")
        return redirect(url_for("index"))
    return Response(
        stream_with_context(r.iter_content(chunk_size=8192)),
        content_type="application/java-archive",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/packages/download")
def download_packages():
    names = request.args.getlist("name")
    if not names:
        flash("Pick at least one package to download.", "danger")
        return redirect(url_for("index"))
    r = requests.get(f"{API_BASE}/api/packages/download", params=[("name", n) for n in names],
                     headers=_api_headers(), stream=True, timeout=300)
    if not r.ok:
        flash("Could not download that package.", "danger")
        return redirect(url_for("index"))
    return Response(
        stream_with_context(r.iter_content(chunk_size=64 * 1024)),
        content_type="application/zip",
        headers={"Content-Disposition": r.headers.get("Content-Disposition", "attachment; filename=mod-packages.zip")},
    )


@app.route("/api/status")
def api_status():
    """Proxy for AJAX polling from the frontend."""
    status = _api_get("/api/status", {})
    players = _api_get("/api/players", {}).get("players", [])
    return jsonify({
        "online": status.get("minecraft_online", False),
        "players": players,
        "player_count": len(players),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORTAL_PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=False)
