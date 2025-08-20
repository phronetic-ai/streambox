import subprocess
import time

from app.gateway import GatewayService
from app.logs import logger


class StreamHandler:
    def __init__(self, gateway: GatewayService, stream_details: dict):
        self.id: str = stream_details["stream_id"]
        self.stream_url: str = stream_details["stream_url"]
        self.status: str = stream_details["status"]
        self.source_urls: list[str] = stream_details["source_urls"]
        self.gateway: GatewayService = gateway
        self.ffmpeg_process: subprocess.Popen | None = None
        self.exit_code: int = 0
        self.last_frame_timestamp: float | None = stream_details["last_frame_timestamp"]
        self.start_timestamp: float | None = None
        self.error = None

    def update(self, stream_details: dict):
        if (
            self.stream_url == stream_details["stream_url"]
            and self.status == stream_details["status"]
            and self.source_urls == stream_details["source_urls"]
        ):
            return

        self.stream_url = stream_details["stream_url"]
        self.status = stream_details["status"]
        self.source_urls = stream_details["source_urls"]
        self.last_frame_timestamp = stream_details["last_frame_timestamp"]
        self.restart()

    def start(self):
        if self.gateway.stop_event.is_set():
            return

        logger.info(f"Starting stream: {self.id}")
        # ffmpeg_process = subprocess.Popen(ffmpeg_cmd)
        self.ffmpeg_process = subprocess.Popen(
            self.build_ffmpeg_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.start_timestamp = time.time()

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
            if self.ffmpeg_process.poll() is not None:
                # Process has terminated, capture error output
                stderr_output = self.ffmpeg_process.stderr.read() if self.ffmpeg_process.stderr else None
                self.error = stderr_output if stderr_output else "ffmpeg command failed"
                return False
        if self.start_timestamp and time.time() - self.start_timestamp > 60:
            if (
                not self.last_frame_timestamp
                or time.time() - self.last_frame_timestamp > 10
            ):
                return False
        return True

    def build_ffmpeg_cmd(self):
        logger.info(f"Building ffmpeg command for stream: {self.id}")
        source_urls = self.source_urls
        url_count = len(source_urls)

        if url_count == 1:
            # For single URL, just relay the stream as is
            ffmpeg_cmd = [
                "ffmpeg",
                "-rtsp_transport", "tcp",
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-thread_queue_size", "4096",
                "-i", source_urls[0],
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-tune", "zerolatency",
                "-b:v", "2M",
                "-maxrate", "2M",
                "-bufsize", "4M",
                "-an",  # disable audio explicitly
                "-f", "rtsp",
                self.stream_url,
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

            ffmpeg_cmd.extend(
                [
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[out]",
                    "-r",
                    "15",
                    "-pix_fmt",
                    "yuv420p",
                    "-preset",
                    "ultrafast",
                    "-vsync",
                    "2",
                    "-b:v",
                    "2M",
                    "-maxrate",
                    "2M",
                    "-bufsize",
                    "4M",
                    "-vcodec",
                    "libx264",
                    "-tune",
                    "zerolatency",
                    "-f",
                    "rtsp",
                    self.stream_url,
                ]
            )

        return ffmpeg_cmd
