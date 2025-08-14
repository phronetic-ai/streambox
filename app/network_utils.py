import os
import psutil
import shutil
import subprocess
import time
import json


REPO_ROOT = os.path.expanduser("~/code/phronetics/streambox")

def get_active_interfaces():
    # Virtual / loopback prefixes
    skip_prefixes = ("lo", "docker", "br-", "veth", "virbr", "tun", "tap")
    active_interfaces = []
    for name, stats in psutil.net_if_stats().items():
        if not stats.isup:
            continue  # skip down interfaces
        if name.startswith(skip_prefixes):
            continue  # skip virtual/loopback
        # if stats.speed == 0 and not re.match(r"(eth|enp|wlan|wlp|wwan)", name):
        #     continue  # skip if no speed and doesn't look like a real NIC
        active_interfaces.append(name)
    return active_interfaces

def get_current_bytes_sent(interfaces: list[str]):
    counters = psutil.net_io_counters(pernic=True)
    return sum(
        c.bytes_sent
        for iface, c in counters.items()
        if iface in interfaces
    )

def get_upload_bitrate(interval=1.0):
    """Returns actual upload bitrate in Mbps."""
    try:
        active_interfaces = get_active_interfaces()
        bytes_sent1 = get_current_bytes_sent(active_interfaces)
        time.sleep(interval)
        bytes_sent2 = get_current_bytes_sent(active_interfaces)
        # Convert bytes/sec → bits/sec → Mbps
        return (bytes_sent2 - bytes_sent1) * 8 / interval / 1_000_000
    except Exception as e:
        print(f"Failed to get upload bitrate: {e}")
        return 0

def _install_ookla_speedtest_noninteractive():
    """Attempts to install Ookla speedtest non-interactively. Returns True if installed."""
    install_script = f"{REPO_ROOT}/scripts/install_speedtest.sh"
    try:
        # Use sudo -n to avoid prompting for a password. If password is required, this will fail immediately.
        result = subprocess.run(
            ["sudo", "-n", "bash", install_script], capture_output=True, text=True
        )
        if result.returncode == 0:
            return shutil.which("speedtest") is not None

        # If sudo asked for a password or installation failed, fall through to return False
        stderr = (result.stderr or "").strip()
        if stderr:
            print(f"Ookla speedtest install skipped/failure: {stderr}")
        return False
    except Exception as e:
        print(f"Failed running Ookla install script: {e}")
        return False


def _install_python_speedtest_cli():
    """Installs python-based speedtest-cli using uv. Returns True if installed."""
    script = f"{REPO_ROOT}/scripts/install_speedtest_cli_python.sh"
    try:
        res = subprocess.run(["bash", script], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Python speedtest-cli install failed: {res.stderr}")
            return False
        # speedtest-cli typically installs both `speedtest` and `speedtest-cli` entry points
        return (shutil.which("speedtest") is not None) or (
            shutil.which("speedtest-cli") is not None
        )
    except Exception as e:
        print(f"Failed to run python speedtest-cli install script: {e}")
        return False


def detect_speedtest_variant():
    """Detects which speedtest variant is available: 'ookla', 'python', or None."""
    speedtest_cmd = shutil.which("speedtest")
    speedtest_cli_cmd = shutil.which("speedtest-cli")

    if speedtest_cmd:
        try:
            # Ookla prints 'Speedtest by Ookla' in version/help output
            res = subprocess.run(
                [speedtest_cmd, "--version"], capture_output=True, text=True
            )
            out = (res.stdout or "") + (res.stderr or "")
            if "Ookla" in out:
                return "ookla"
        except Exception:
            pass
        try:
            res = subprocess.run(
                [speedtest_cmd, "--help"], capture_output=True, text=True
            )
            out = (res.stdout or "") + (res.stderr or "")
            if "Ookla" in out or "by Ookla" in out:
                return "ookla"
        except Exception:
            pass
        # If `speedtest-cli` is present as well, prefer python classification
        if speedtest_cli_cmd:
            return "python"
        # Default to python style if we cannot prove it's Ookla
        return "python"

    if speedtest_cli_cmd:
        return "python"

    return None


def check_speedtest_cli():
    """Ensures a speedtest tool is installed. Tries Ookla first (non-interactive), falls back to python speedtest-cli.

    Returns the path to the chosen executable ("speedtest" or "speedtest-cli"), or None on failure.
    """
    # If already installed, prefer the Ookla binary when present
    existing_speedtest = shutil.which("speedtest")
    existing_speedtest_cli = shutil.which("speedtest-cli")
    if existing_speedtest or existing_speedtest_cli:
        return existing_speedtest or existing_speedtest_cli

    # Try to install Ookla non-interactively
    if _install_ookla_speedtest_noninteractive():
        cmd = shutil.which("speedtest")
        if cmd:
            return cmd

    # Fallback: install python speedtest-cli via uv
    if _install_python_speedtest_cli():
        return shutil.which("speedtest") or shutil.which("speedtest-cli")

    return None


def get_network_speedtest():
    """Runs speedtest and returns {"download_mbps": float, "upload_mbps": float} depending on installed variant."""
    variant = detect_speedtest_variant()
    if variant is None:
        # Attempt installation, then re-detect
        cmd = check_speedtest_cli()
        if not cmd:
            return None
        variant = detect_speedtest_variant()
        if variant is None:
            return None

    try:
        t = time.time()
        if variant == "ookla":
            cmd = shutil.which("speedtest")
            result = subprocess.run(
                [cmd, "--accept-license", "--accept-gdpr", "-f", "json"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                print(f"Speedtest (Ookla) failed: {result.stderr}")
                return None

            data = json.loads(result.stdout)
            # bandwidth is in Bytes/s; convert to bits/s then Mbps
            download_bps = data["download"]["bandwidth"] * 8
            upload_bps = data["upload"]["bandwidth"] * 8
            download_mbps = download_bps / 1_000_000
            upload_mbps = upload_bps / 1_000_000
        else:
            # python speedtest-cli
            cmd = shutil.which("speedtest-cli") or shutil.which("speedtest")
            result = subprocess.run(
                [cmd, "--json"], capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                print(f"Speedtest (python) failed: {result.stderr}")
                return None
            data = json.loads(result.stdout)
            # speedtest-cli reports bits per second for 'download' and 'upload'
            download_mbps = float(data.get("download", 0)) / 1_000_000
            upload_mbps = float(data.get("upload", 0)) / 1_000_000

        print(f"Speedtest took {time.time() - t:.2f} seconds")
        return {"download_mbps": download_mbps, "upload_mbps": upload_mbps}
    except Exception as e:
        print(f"Speedtest failed: {e}")
        return None


cache_path = "/tmp/network_speedtest.json"


def get_cached_network_speedtest(expiry_time=1800):
    """Returns cached network speedtest data."""
    test_data = read_cached_network_speedtest()
    if (
        test_data
        and isinstance(test_data, dict)
        and test_data.get("timestamp", 0) > time.time() - expiry_time
    ):
        return test_data
    new_data = get_network_speedtest()
    if new_data:
        new_data["timestamp"] = time.time()
        cache_network_speedtest(new_data)
        return new_data
    return None


def read_cached_network_speedtest():
    """Reads cached network speedtest data."""
    try:
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Failed to read cached speedtest: {e}")
    return None


def cache_network_speedtest(data):
    """Caches network speedtest data."""
    try:
        with open(cache_path, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Failed to write cached speedtest: {e}")


if __name__ == "__main__":
    upload_bitrate = get_upload_bitrate(2)
    print(f"Actual upload bitrate: {upload_bitrate:.2f} Mbps")

    speeds = get_network_speedtest()
    if speeds:
        print(
            f"Network capacity: {speeds['download_mbps']:.2f} Mbps down / {speeds['upload_mbps']:.2f} Mbps up"
        )
    else:
        print("Speedtest tool not found — skipping max network speed check.")
