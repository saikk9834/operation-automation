"""
Flask REST API — wraps the existing Operation Automation backend.
Run with:  python api.py

IMPORTANT — macOS NSException fix
----------------------------------
main.py creates a tk.Tk() window at module level.  Importing it from a
background thread (or even from Flask on macOS) triggers an NSException
because AppKit requires all UI work on the main thread.

Fix: we defer the import of run_script until it is actually needed inside
the worker thread, AND we guard the Tkinter root-window creation in main.py
(see note below).  The safest long-term solution is to extract run_script
into a separate file that has no Tkinter imports at all.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json, os, threading

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".operation_automation_config.json")

app = Flask(__name__)
CORS(app, origins=[
    "http://localhost:5173",   # Vite dev server
    "http://localhost:3000",   # CRA / other dev servers
    "https://operation-automation.vercel.app/"
])

@app.after_request
def add_cors_headers(response):
    allowed_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://operation-automation.vercel.app",
    ]
    origin = request.headers.get("Origin")
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/api/<path:path>", methods=["OPTIONS"])
def handle_options(path):
    return "", 204

# ── helpers ────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

# Shared run-state
_run_state = {"running": False, "log": [], "error": None, "done": False}

def _append_log(msg: str):
    _run_state["log"].append(msg)
    print(msg)   # also visible in the terminal running api.py

# ── routes ─────────────────────────────────────────────────────────────────

@app.get("/api/settings")
def get_settings():
    return jsonify(load_config())


@app.post("/api/settings")
def post_settings():
    body = request.get_json(force=True)
    allowed = {"all_in_one_path", "destination_path", "recipient_email", "cc_email"}
    cfg = load_config()
    cfg.update({k: v for k, v in body.items() if k in allowed})
    save_config(cfg)
    return jsonify({"ok": True})


@app.get("/api/status")
def get_status():
    return jsonify(_run_state)


# ── Folder browser ──────────────────────────────────────────────────────────
@app.get("/api/browse")
def browse():
    """
    Return a list of sub-directories inside a given path.
    Query params:
      ?path=/some/dir   - directory to list  (defaults to user home)
    The frontend uses this to build a folder-picker modal.
    """
    root_path = request.args.get("path", os.path.expanduser("~"))
    root_path = os.path.realpath(root_path)

    if not os.path.isdir(root_path):
        return jsonify({"error": "Not a directory"}), 400

    try:
        entries = []
        with os.scandir(root_path) as it:
            for entry in sorted(it, key=lambda e: e.name.lower()):
                if entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                    has_children = False
                    if os.access(entry.path, os.R_OK):
                        try:
                            has_children = any(
                                e.is_dir() and not e.name.startswith(".")
                                for e in os.scandir(entry.path)
                            )
                        except PermissionError:
                            pass
                    entries.append({
                        "name": entry.name,
                        "path": entry.path,
                        "has_children": has_children,
                    })
    except PermissionError:
        return jsonify({"error": "Permission denied"}), 403

    # Build breadcrumb chain
    parts = []
    p = root_path
    while True:
        parent = os.path.dirname(p)
        parts.insert(0, {"name": os.path.basename(p) or p, "path": p})
        if parent == p:
            break
        p = parent

    return jsonify({
        "current": root_path,
        "breadcrumbs": parts,
        "entries": entries,
    })


# ── Run pipeline ────────────────────────────────────────────────────────────
@app.post("/api/run")
def post_run():
    if _run_state["running"]:
        return jsonify({"error": "Already running"}), 409

    body = request.get_json(force=True)
    all_in_one      = body.get("all_in_one_path", "").strip()
    destination     = body.get("destination_path", "").strip()
    recipient_email = body.get("recipient_email", "").strip()
    cc_email        = body.get("cc_email", "").strip()

    missing = [f for f, v in [
        ("all_in_one_path", all_in_one),
        ("destination_path", destination),
        ("recipient_email", recipient_email),
    ] if not v]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    if not os.path.exists(all_in_one):
        return jsonify({"error": f"Path does not exist on server: {all_in_one}"}), 400
    if not os.path.exists(destination):
        return jsonify({"error": f"Path does not exist on server: {destination}"}), 400

    save_config({
        "all_in_one_path": all_in_one,
        "destination_path": destination,
        "recipient_email": recipient_email,
        "cc_email": cc_email,
    })

    _run_state.update({"running": True, "log": [], "error": None, "done": False})

    def worker():
        try:
            # Deferred import — this is the NSException fix.
            # See the long comment in the module docstring above.
            from main import run_script
            _append_log("Starting pipeline…")
            run_script(all_in_one, destination, recipient_email, cc_email)
            _append_log("✅  Pipeline finished.")
        except Exception as exc:
            _run_state["error"] = str(exc)
            _append_log(f"❌ Error: {exc}")
        finally:
            _run_state["running"] = False
            _run_state["done"] = True

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"ok": True, "message": "Job started"})


@app.post("/api/reset")
def post_reset():
    _run_state.update({"running": False, "log": [], "error": None, "done": False})
    return jsonify({"ok": True})


# ── entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
    #                                          ^^^^^
    # Keep debug=False — debug=True spawns a reloader child process that
    # imports your app twice and can re-trigger the Tk initialisation crash.