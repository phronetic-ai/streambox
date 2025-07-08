import asyncio
import signal
import threading
import time

from app.gateway import GatewayService
from app.logs import logger
from app.utils import check_network_availability

RETRY_DELAY = 5

stop_event = threading.Event()

def signal_handler(sig, frame):
    logger.info("Received signal to terminate")
    stop_event.set()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

async def main():
    while not stop_event.is_set():
        while not check_network_availability():
            logger.warning("Network unavailable. Retrying...")
            time.sleep(RETRY_DELAY)

        gateway_service = GatewayService(stop_event)
        await gateway_service.start()

    logger.info("Terminating...")

if __name__ == "__main__":
    asyncio.run(main())