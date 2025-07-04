import subprocess
from app.gateway import GatewayService
from app.logs import logger

class StreamHandler:
    def __init__(self, gateway: GatewayService, stream_details: dict):
        self.id = stream_details["stream_id"]
        self.stream_url = stream_details["stream_url"]
        self.status = stream_details["status"]
        self.source_urls = stream_details["source_urls"]
        self.gateway = gateway
        self.ffmpeg_process = None
        self.exit_code = 0

    def start(self):
        if self.gateway.stop_event.is_set():
            return

        logger.info(f"Starting stream: {self.id}")
        # ffmpeg_process = subprocess.Popen(ffmpeg_cmd)
        self.ffmpeg_process = subprocess.Popen(
            self.build_ffmpeg_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    def stop(self):
        if self.ffmpeg_process:
            try:
                self.ffmpeg_process.terminate()
                self.ffmpeg_process = None
            except Exception as e:
                logger.error(f"Error stopping stream {self.id}: {e}")
            logger.info(f"Stream {self.id} stopped")

    def restart(self):
        self.stop()
        self.start()

    def is_alive(self):
        if self.ffmpeg_process:
            return self.ffmpeg_process.poll() is None
        return False

    def build_ffmpeg_cmd(self):
        logger.info(f"Building ffmpeg command for stream: {self.id}")
        source_urls = self.source_urls
        url_count = len(source_urls)

        if url_count == 1:
            # For single URL, just relay the stream as is
            ffmpeg_cmd = [
                "ffmpeg", "-re",
                "-thread_queue_size", "512", "-i", source_urls[0],
                "-c:v", "copy", "-f", "rtsp", self.stream_url
            ]
        else:
            # For 2-4 URLs, create a 2x2 grid
            ffmpeg_cmd = ["ffmpeg", "-re"]

            # Add inputs for available URLs
            for i in range(min(url_count, 4)):
                ffmpeg_cmd.extend(["-thread_queue_size", "512", "-i", source_urls[i]])

            # Add black inputs for missing URLs
            for i in range(url_count, 4):
                ffmpeg_cmd.extend(["-f", "lavfi", "-i", "color=c=black:s=960x540"])

            # Build filter complex
            filter_complex = (
                "[0:v]scale=960:540[v1];"
                "[1:v]scale=960:540[v2];"
                "[2:v]scale=960:540[v3];"
                "[3:v]scale=960:540[v4];"
                "[v1][v2][v3][v4]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0[out]"
            )

            ffmpeg_cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[out]", "-r", "15", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-vsync", "2",
                "-b:v", "2M", "-maxrate", "2M", "-bufsize", "4M",
                "-vcodec", "libx264", "-tune", "zerolatency", "-f", "rtsp", self.stream_url
            ])

        return ffmpeg_cmd
