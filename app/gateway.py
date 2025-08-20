import asyncio
import time
from typing import TYPE_CHECKING

from .interface import get_stream_details
from .logs import logger
from .utils import check_network_availability, get_device_id

if TYPE_CHECKING:
    from .stream_handler import StreamHandler


class GatewayService:
    """
    Gateway service for the device. This process is responsible for:
    - Fetching stream details from the backend
    - Starting and stopping stream handlers based on the stream details
    - Monitoring the stream handlers and restarting them if they crash
    - Sending metrics to the backend
    """

    def __init__(self, stop_event):
        self.exit_code: int = 0
        self.last_online: float = time.time()
        self.stream_handlers: list["StreamHandler"] = []
        self.stop_event: asyncio.Event = stop_event
        self.last_monitor_timestamp: float = time.time()

    async def load_streams(self):
        stream_details = await get_stream_details(self)
        streams = stream_details.get("streams", [])
        return [stream for stream in streams if stream["status"] == "active"]

    async def update_stream_handlers(self):
        from .stream_handler import StreamHandler

        streams = await self.load_streams()
        for stream in streams:
            existing_handler = next(
                (
                    handler
                    for handler in self.stream_handlers
                    if handler.id == stream["stream_id"]
                ),
                None,
            )
            if existing_handler:
                existing_handler.update(stream)
            else:
                stream_handler = StreamHandler(self, stream)
                self.stream_handlers.append(stream_handler)
                stream_handler.start()

        active_stream_ids = [stream["stream_id"] for stream in streams]
        inactive_stream_ids = [
            handler.id
            for handler in self.stream_handlers
            if handler.id not in active_stream_ids
        ]
        for handler in self.stream_handlers:
            if handler.id in inactive_stream_ids:
                handler.stop()
                self.stream_handlers.remove(handler)
        self.stream_fetch_timestamp = time.time()

    async def monitor(self):
        if not check_network_availability():
            logger.info(f"Network unavailable for device {get_device_id()}")
            self.stop_event.set()
            return

        await self.update_stream_handlers()
        for stream_handler in self.stream_handlers:
            if not stream_handler.is_alive():
                logger.warning(f"Stream {stream_handler.id} crashed. Restarting...")
                stream_handler.restart()

    async def start(self):
        logger.info(f"Starting gateway service for device {get_device_id()}")
        await self.update_stream_handlers()
        while not self.stop_event.is_set():
            if time.time() - self.last_monitor_timestamp > 60:
                await self.monitor()
                self.last_monitor_timestamp = time.time()
            await asyncio.sleep(1)
        for stream_handler in self.stream_handlers:
            stream_handler.stop()
