import os
import uuid
import psutil
import socket
from functools import cache
from .network_utils import get_upload_bitrate, get_cached_network_speedtest

@cache
def get_device_id():
    serial_path = "/sys/firmware/devicetree/base/serial-number"
    if os.path.exists(serial_path):
        file_path = serial_path
    else:
        file_path = os.path.expanduser("~/device-id")
        if not os.path.exists(file_path):
            new_id = str(uuid.uuid4())
            with open(file_path, "w") as f:
                f.write(new_id)
            return new_id
    with open(file_path, "r") as f:
        return f.read().strip().strip('\x00')

def check_network_availability():
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(('8.8.8.8', 53))
        return True
    except OSError:
        return False

def get_cpu_usage():
    return psutil.cpu_percent()

def get_memory_usage():
    return psutil.virtual_memory().percent

def get_disk_usage():
    return psutil.disk_usage('/').percent

def get_system_info():
    return {
        "cpu_usage": get_cpu_usage(),
        "memory_usage": get_memory_usage(),
        "disk_usage": get_disk_usage(),
        "network_info": get_network_info(),
    }

def get_network_info():
    upload_bitrate = get_upload_bitrate(2)
    network_speed = get_cached_network_speedtest()
    upload_speed = network_speed["upload_mbps"] if network_speed else 0
    download_speed = network_speed["download_mbps"] if network_speed else 0
    return {
        "upload_speed": upload_speed,
        "download_speed": download_speed,
        "upload_bitrate": upload_bitrate,
    }

if __name__ == "__main__":
    print(f"Network info: {get_network_info()}")
    print(f"System info: {get_system_info()}")
