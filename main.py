import time
import threading
import signal
from app.utils import get_mac_address, check_network_availability
from app.logs import logger
from app.gateway import GatewayService

DEVICE_ID = get_mac_address()
RETRY_DELAY = 5

stop_event = threading.Event()

def signal_handler(sig, frame):
    logger.info("Received signal to terminate")
    stop_event.set()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def main():
    while not stop_event.is_set():
        while not check_network_availability():
            logger.warning("Network unavailable. Retrying...")
            time.sleep(RETRY_DELAY)

        gateway_service = GatewayService(DEVICE_ID, stop_event)
        gateway_service.start()

    logger.info("Terminating...")

if __name__ == "__main__":
    main()