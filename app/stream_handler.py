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
        self.valid_source_urls: list[str] = []
        self.rtsp_status = {}
        self.ffmpeg_error = "init"

    def update(self, stream_details: dict):
        logger.info(f"Updating stream details for stream: {stream_details['stream_id']}")
        changed = True
        if (
            self.stream_url == stream_details["stream_url"]
            and self.status == stream_details["status"]
            and self.source_urls == stream_details["source_urls"]
        ):
            changed = False

        self.stream_url = stream_details["stream_url"]
        self.status = stream_details["status"]
        self.source_urls = stream_details["source_urls"]
        self.last_frame_timestamp = stream_details["last_frame_timestamp"]
        existing_valid_source_urls = self.valid_source_urls
        self.validate_source_urls()
        if changed or self.valid_source_urls != existing_valid_source_urls:
            self.restart()

    def get_error(self):
        error = ""
        for _index, status in self.rtsp_status.items():
            if not status["valid"]:
                error += f"RTSP URL {status['url']} is invalid: {status['output']}\n"
        if self.ffmpeg_error:
            error += f"FFmpeg error: {self.ffmpeg_error}\n"
            self.ffmpeg_error = "init"
        if len(self.valid_source_urls) == 0:
            error += "No valid source URLs"
        return error.strip() if error else None

    def start(self):
        if self.gateway.stop_event.is_set():
            return

        self.validate_source_urls()

        if len(self.valid_source_urls) == 0:
            logger.info(f"No valid source urls - Returning...")
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
        logger.info(f"Stream handler started at: {self.start_timestamp}")

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
                self.ffmpeg_error = stderr_output if stderr_output else "ffmpeg command failed"

                stdout_output = self.ffmpeg_process.stdout.read() if self.ffmpeg_process.stdout else ""
                self.ffmpeg_error += f" | FFmpeg Output: {stdout_output}"
                process_return_code = self.ffmpeg_process.returncode
                self.ffmpeg_error += f" | Return Code: {process_return_code}"
                return False
        if self.start_timestamp and time.time() - self.start_timestamp > 150:
            if (
                not self.last_frame_timestamp
                or time.time() - self.last_frame_timestamp > 10
            ):
                return False
        return True

    def validate_source_urls(self):
        rtsp_status = {}
        for index, url in enumerate(self.source_urls):
            valid, output = self.check_rtsp(url)
            rtsp_status[index] = {"url": url, "valid": valid, "output": output}
            logger.info(f"Checking rtsp url: {url} - Results: valid -> {valid} | output -> {output}")
        self.rtsp_status = rtsp_status
        self.valid_source_urls = [url["url"] for url in self.rtsp_status.values() if url["valid"]]

    def check_rtsp(self, url):
        try:
            output = subprocess.check_output(
                [
                    "ffprobe",
                    "-rtsp_transport", "tcp",
                    "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=index,codec_name,codec_long_name,profile,pix_fmt,width,height,avg_frame_rate,r_frame_rate,bit_rate,level,color_range,color_space,color_transfer,color_primaries,nb_frames",
                    "-of", "default=nokey=1:noprint_wrappers=1",
                    url
                ],
                stderr=subprocess.STDOUT
            )
            return True, output.decode().strip()
        except subprocess.CalledProcessError as e:
            return False, e.output.decode().strip()

    def build_ffmpeg_cmd(self):
        logger.info(f"Building ffmpeg command for stream: {self.id} and urls: {self.valid_source_urls}")
        source_urls = self.valid_source_urls
        url_count = len(source_urls)

        if url_count == 1:
            # For single URL, just relay the stream as is
            ffmpeg_cmd = [
                "ffmpeg",
                "-rtsp_transport", "tcp",
                "-fflags", "+genpts",
                "-flags", "low_delay",
                "-thread_queue_size", "4096",
                "-i", source_urls[0],
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,format=yuv420p",
                "-c:v", "libx264",
                "-r", "2",
                "-preset", "veryfast",
                "-tune", "zerolatency",
                "-b:v", "500k",
                "-maxrate", "600k",
                "-bufsize", "1000k",
                "-an",  # disable audio explicitly
                "-f", "flv",
                self.stream_url,
            ]
        else:
            # For 2-4 URLs, create a 2x2 grid
            ffmpeg_cmd = ["ffmpeg", "-re", "-rtsp_transport", "tcp"]

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
                    "500k",
                    "-maxrate",
                    "600k",
                    "-bufsize",
                    "1000k",
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
