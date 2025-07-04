def get_stream_details(device_id):
    return {
        "streams": [
            {
                "stream_url": "rtsp://172.17.0.1:8554/stream5",
                "stream_id": "stream123",
                "status": "active",
                "source_urls": [
                    "rtsp://172.17.0.1:8554/stream1",
                    "rtsp://172.17.0.1:8554/stream2",
                    "rtsp://172.17.0.1:8554/stream3",
                    "rtsp://172.17.0.1:8554/stream4"
                ]
            },
            {
                "stream_url": "rtsp://172.17.0.1:8554/stream6",
                "stream_id": "stream124",
                "status": "active",
                "source_urls": [
                    "rtsp://172.17.0.1:8554/stream1",
                    "rtsp://172.17.0.1:8554/stream2",
                    "rtsp://172.17.0.1:8554/stream3",
                    "rtsp://172.17.0.1:8554/stream4"
                ]
            }
        ]
    }
