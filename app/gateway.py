import time
from .logs import logger
from .utils import check_network_availability, get_system_info
from .interface import get_stream_details

class GatewayService:
    def __init__(self, device_id, stop_event):
        self.device_id = device_id
        self.stream_handlers = self.load_streams()
        self.exit_code = 0
        self.last_online = time.time()
        self.stop_event = stop_event

    def load_streams(self):
        from .stream_handler import StreamHandler
        streams = get_stream_details(self.device_id)["streams"]
        stream_handlers = [StreamHandler(self, stream) for stream in streams if stream["status"] == "active"]
        return stream_handlers

    def monitor(self):
        if not check_network_availability():
            logger.info(f"Network unavailable for device {self.device_id}")
            self.stop_event.set()
            return

        system_info = get_system_info()
        logger.info(f"System info: {system_info}")
        for stream_handler in self.stream_handlers:
            if not stream_handler.is_alive():
                logger.warning(f"Stream {stream_handler.id} crashed. Restarting...")
                stream_handler.restart()

    def start(self):
        logger.info(f"Starting gateway service for device {self.device_id}")
        for stream_handler in self.stream_handlers:
            stream_handler.start()
        while not self.stop_event.is_set():
            self.monitor()
            time.sleep(5)
        for stream_handler in self.stream_handlers:
            stream_handler.stop()
