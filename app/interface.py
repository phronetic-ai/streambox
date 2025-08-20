from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from .gateway import GatewayService
from .utils import get_device_id, get_system_info


async def get_stream_details(gateway: "GatewayService") -> dict[str, Any]:
    url = "https://abm.phronetic.ai/api/v1/devices/stream_info"
    system_info = get_system_info()
    device_id = get_device_id()
    stream_status = get_stream_status(gateway)
    logs = gateway.fetch_logs()
    payload = {
        "device_id": device_id,
        "system_info": system_info,
        "stream_status": stream_status,
        "logs": logs,
    }
    async with httpx.AsyncClient() as client:
        headers = {"Content-Type": "application/json"}
        response = await client.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return {}


def get_stream_status(gateway: "GatewayService") -> dict:
    return {
        "num_streams": len(gateway.stream_handlers),
        "stream_ids": [stream.id for stream in gateway.stream_handlers],
        "alive_streams": [
            stream.id for stream in gateway.stream_handlers if stream.is_alive()
        ],
        "dead_streams": [
            stream.id for stream in gateway.stream_handlers if not stream.is_alive()
        ],
        "rtsp_status": [
            handler.rtsp_status for handler in gateway.stream_handlers
        ]
    }
