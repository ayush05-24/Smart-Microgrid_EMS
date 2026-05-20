from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import websockets
except ImportError:
    print("Please install websockets package or run in environment where websockets is available.")
    sys.exit(1)


def find_chrome() -> str | None:
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in paths:
        if os.path.exists(path):
            return path
    return None


async def capture_screenshot() -> None:
    print("=== Starting Smart Microgrid EMS Automation ===")
    
    # 1. Start API Server in background
    print("Starting API Server...")
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    # 2. Start Frontend dev server in background
    print("Starting React Frontend dev server...")
    frontend_process = subprocess.Popen(
        "npm run dev",
        shell=True,
        cwd=str(PROJECT_ROOT / "frontend"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    # Wait for servers to start
    print("Waiting 5 seconds for local servers to bind to ports...")
    await asyncio.sleep(5)
    
    # Start live simulator
    print("Calling API to start Live Simulator...")
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8000/live/start",
            data=json.dumps({"interval_seconds": 0.5, "reset": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as response:
            print("Simulator started response:", response.read().decode())
    except Exception as e:
        print("Warning: Failed to auto-start live simulator over API:", e)
        
    chrome_path = find_chrome()
    if not chrome_path:
        print("Error: Google Chrome application was not found in standard paths.")
        api_process.terminate()
        frontend_process.terminate()
        return

    print(f"Launching Chrome in headless debug mode from: {chrome_path}")
    chrome_process = subprocess.Popen([
        chrome_path,
        "--headless",
        "--remote-debugging-port=9222",
        "--window-size=1440,900",
        "--disable-gpu",
        "http://127.0.0.1:5173",
    ])
    
    print("Waiting 8 seconds for React page to hydrate and chart to animate...")
    await asyncio.sleep(8)
    
    try:
        print("Querying Chrome target page context...")
        with urllib.request.urlopen("http://127.0.0.1:9222/json") as response:
            pages = json.loads(response.read().decode())
            
        ws_url = None
        for page in pages:
            url = page.get("url", "")
            if "5173" in url or "localhost" in url or "127.0.0.1" in url:
                ws_url = page.get("webSocketDebuggerUrl")
                break
        
        if not ws_url and pages:
            ws_url = pages[0].get("webSocketDebuggerUrl")
            
        if not ws_url:
            print("Error: Could not determine WebSocketDebuggerUrl for headless tab.")
            return
            
        print(f"Connecting WebSocket client to Chrome debugger at: {ws_url}")
        async with websockets.connect(ws_url) as ws:
            print("Connected. Running simulator live telemetry for 3 more seconds...")
            await asyncio.sleep(3)
            
            print("Sending Page.captureScreenshot command to DevTools Protocol...")
            cmd = {
                "id": 1,
                "method": "Page.captureScreenshot",
                "params": {"format": "png", "captureBeyondViewport": False},
            }
            await ws.send(json.dumps(cmd))
            
            resp_str = await ws.recv()
            resp = json.loads(resp_str)
            
            if "result" in resp and "data" in resp["result"]:
                img_data = base64.b64decode(resp["result"]["data"])
                
                docs_dir = PROJECT_ROOT / "docs"
                docs_dir.mkdir(parents=True, exist_ok=True)
                screenshot_path = docs_dir / "dashboard_active.png"
                
                with open(screenshot_path, "wb") as f:
                    f.write(img_data)
                print(f"Success! Screenshot saved to: {screenshot_path}")
            else:
                print("Error: Screenshot response did not contain image data:", resp)
                
    except Exception as e:
        print("Error during automation capture:", e)
    finally:
        print("Cleaning up background processes...")
        chrome_process.terminate()
        api_process.terminate()
        
        # Kill dev servers and python processes clean
        subprocess.run("taskkill /f /im node.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
        try:
            api_process.kill()
        except Exception:
            pass
        print("=== Automation run finished ===")


if __name__ == "__main__":
    asyncio.run(capture_screenshot())
