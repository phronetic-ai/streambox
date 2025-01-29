import sys
from pathlib import Path
import argparse
import subprocess
import requests
import platform
import time
import logging
import os
import traceback
import threading
import queue

logging.basicConfig(
    filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rtmp.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - "%(message)s" - %(name)s:%(lineno)s'
)

logger = logging.getLogger(__name__)

FRAME_RATE = 24
RETRY_DELAY = 5
global SERVER_ALIVE_INTERVAL
SERVER_ALIVE_INTERVAL = 10

def check_network_availability():
    try:
        requests.get('https://www.google.com', timeout=5)
        return True
    except (requests.ConnectionError, requests.Timeout):
        logger.warning("Network connection unavailable.")
        return False

def send_api_request(webroomId):
    api_url = 'https://devapi.phronetic.ai/api/theiavision/manager/join/rtmp'
    payload = {"webroom_id": webroomId}

    while True:
        try:
            response = requests.post(api_url, json=payload)
            
            if response.status_code in [200, 409]:
                logger.info("Service started/maintained successfully.")
                return True
            else:
                logger.error(f"API request failed. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending API request: {e}")
        
        time.sleep(RETRY_DELAY)

def periodic_server_alive_check(webroomId, id):
    logger.info(f"periodic_server_alive_check start {SERVER_ALIVE_PROCESS_ID} - {id}")
    while SERVER_ALIVE_PROCESS_ID == id:
        try:
            send_api_request(webroomId)
            time.sleep(SERVER_ALIVE_INTERVAL)
            logger.info(f"periodic_server_alive_check loop end {SERVER_ALIVE_PROCESS_ID} - {id}")
        except Exception as e:
            logger.error(f"Server alive check error: {e}")
            stop_event.set()
            break

def start_ffmpeg_stream(rtmp_url, webroomId):
    logger.info("start_ffmpeg_stream")
    system = platform.system()
    
    if system == 'Windows':
        video_device = 'C3-1 USB3 Video'
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'dshow',
            '-framerate', str(FRAME_RATE),
            '-rtbufsize', '100M',
            '-i', f'video={video_device}',
            '-vcodec', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-r', str(FRAME_RATE),
            '-f', 'flv',
            rtmp_url
        ]
    elif system == 'Linux':
        video_device = '/dev/video0'
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'v4l2',
            '-framerate', str(FRAME_RATE),
            '-i', video_device,
            '-vf', 'format=yuv420p',
            '-vcodec', 'libx264',
            '-preset', 'veryfast',
            '-tune', 'zerolatency',
            '-f', 'flv',
            rtmp_url
        ]
    elif system == 'Darwin':
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'avfoundation',
            '-framerate', str(FRAME_RATE),
            '-video_size', '1280x720',    # Reduce resolution
            '-i', video_device,
            '-vcodec', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-b:v', '1000k',              # Set bitrate
            '-maxrate', '1500k',          # Limit max bitrate
            '-bufsize', '2000k',          # Set buffer size

            '-vcodec', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-r', str(FRAME_RATE),
            '-f', 'flv',
            rtmp_url
        ]
    else:
        logger.error(f"Unsupported operating system: {system}")
        return False

    while True:
        logger.info("Starting FFmpeg stream...")
        # Create stop event for thread management
        stop_event = threading.Event()

        try:
            # Start server alive thread
            global SERVER_ALIVE_PROCESS_ID
            SERVER_ALIVE_PROCESS_ID = time.time()
            server_alive_thread = threading.Thread(
                target=periodic_server_alive_check, 
                args=(webroomId, SERVER_ALIVE_PROCESS_ID), 
                daemon=True
            )
            server_alive_thread.start()

            # Start FFmpeg process
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd)
            
            while ffmpeg_process.poll() is None:
                time.sleep(5)  # Check every 5 seconds
                
                if not check_network_availability():
                    logger.warning("Network unavailable. Restarting stream.")
                    ffmpeg_process.terminate()
                    stop_event.set()  # Stop the server alive thread
                    break
            
            # Wait for threads to terminate
            server_alive_thread.join(timeout=5)
            
            logger.warning("Stream stopped. Restarting...")
            logger.warning(f"process status - {ffmpeg_process}")
            time.sleep(RETRY_DELAY)

        except Exception as e:
            logger.error(f"FFmpeg streaming error: {e}")
            logger.error(traceback.format_exc())
            stop_event.set()  # Ensure thread stops
            time.sleep(RETRY_DELAY)

def main():
    parser = argparse.ArgumentParser(description='Robust Webcam streaming script.')
    # parser.add_argument('webroomId', nargs='?', help='Webroom ID in the format webroomId=<webroomId>')
    parser.add_argument('--server', choices=['local', 'remote'], default='remote', help='Server to connect to: local or remote (default: remote)')
    args = parser.parse_args()

    if args.server == 'remote':
        home_dir = Path.home()
        webroom_id_file = home_dir / '.webroom_id'
        if os.path.exists(webroom_id_file):
            with open(webroom_id_file, 'r') as f:
                webroomId = f.read().strip()
        if not webroomId:
            print("Error: webroomId cannot be empty.")
            sys.exit(1)
    else:
        webroomId = "test"

    rtmp_url = f'rtmp://localhost:1936/stream/{webroomId}' if args.server == 'local' else f'rtmp://3.109.181.62:1936/stream/{webroomId}'

    while True:
        while not check_network_availability():
            logger.warning("Network unavailable. Retrying...")
            time.sleep(RETRY_DELAY)

        system = platform.system()

        if args.server == 'remote':
            send_api_request(webroomId)

        start_ffmpeg_stream(rtmp_url, webroomId)

if __name__ == "__main__":
    main()