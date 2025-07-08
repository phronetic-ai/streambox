from typing import Any

import httpx

from .utils import get_device_id, get_system_info


async def get_stream_details() -> dict[str, Any]:
    url = "https://abm.phronetic.ai/api/v1/devices/stream_info"
    system_info = get_system_info()
    device_id = get_device_id()
    payload = {"device_id": device_id, "system_info": system_info}
    async with httpx.AsyncClient() as client:
        headers = {"Content-Type": "application/json"}
        response = await client.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return {}
