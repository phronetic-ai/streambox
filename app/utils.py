import platform
import socket
import psutil

def get_mac_address():
    return platform.node()

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
    }
