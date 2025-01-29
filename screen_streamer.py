"""
This script captures video from the default webcam and sends the frames as JPEG data over a WebSocket connection to a server.
The script can connect to either a local server for testing or a remote server for live data, based on command-line arguments.
It uses OpenCV to capture video frames and Socket.IO to establish a WebSocket connection and send the frame data to the server.

Usage:
    python script_name.py webroomId=<webroomId> [--server local|remote]

- webroomId: Required when connecting to the remote server. Format: webroomId=<webroomId>
- --server: Optional. Specify 'local' or 'remote' to choose the server. Defaults to 'remote'.

The script runs in an infinite loop, capturing frames and sending them to the server, until the user presses the 'q' key to exit.
It includes reconnection logic with exponential backoff on disconnections or socket errors.
"""

import cv2
import socketio
import time
import sys
import random
import argparse

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Webcam streaming script.')
    parser.add_argument('webroomId', nargs='?', help='Webroom ID in the format webroomId=<webroomId>')
    parser.add_argument('--server', choices=['local', 'remote'], default='remote', help='Server to connect to: local or remote (default: remote)')
    args = parser.parse_args()

    # Extract webroomId
    if args.server == 'remote':
        if not args.webroomId or not args.webroomId.startswith('webroomId='):
            print("Usage: python script_name.py webroomId=<webroomId> [--server local|remote]")
            sys.exit(1)
        webroomId = args.webroomId.split('=', 1)[1]
        if not webroomId:
            print("Error: webroomId cannot be empty.")
            sys.exit(1)
    else:
        webroomId = None

    # Determine server URL and Socket.IO path
    if args.server == 'local':
        url = 'http://localhost:5000'
        socketio_path = '/socket.io'
    else:
        url = f"https://devapi.phronetic.ai?webroom_id={webroomId}"
        socketio_path = "/streams/socket/socket.io"

    # Initialize a Socket.IO client
    sio = socketio.Client(ssl_verify=False, logger=True, engineio_logger=True)

    # Define variables for exponential backoff
    max_retries = 5       # Maximum number of reconnection attempts
    base_delay = 1        # Initial delay in seconds
    max_delay = 32        # Maximum delay in seconds

    # Flag to control the main loop
    connected = False

    # Event handler for successful connection
    @sio.event
    def connect():
        print("Connected to server")
        nonlocal connected
        connected = True

    # Event handler for disconnection
    @sio.event
    def disconnect():
        print("Disconnected from server")
        nonlocal connected
        connected = False

    # Event handler for connection errors
    @sio.event
    def connect_error(data):
        print(f"Connection failed: {data}")
        nonlocal connected
        connected = False

    # Function to attempt reconnection with exponential backoff
    def attempt_reconnect():
        retries = 0
        delay = base_delay
        while retries < max_retries:
            try:
                print(f"Attempting to reconnect... (Attempt {retries + 1} of {max_retries})")
                sio.connect(
                    url,
                    socketio_path=socketio_path,
                    transports=["websocket"]
                )
                if connected:
                    print("Reconnected successfully")
                    return True
            except Exception as e:
                print(f"Reconnect attempt failed: {e}")
            # Exponential backoff with jitter
            sleep_time = delay + random.uniform(0, 1)  # Add jitter
            print(f"Waiting {sleep_time:.2f} seconds before next attempt")
            time.sleep(sleep_time)
            delay = min(delay * 2, max_delay)  # Exponential increase
            retries += 1
        print("Max retries reached. Could not reconnect.")
        return False

    # Initial connection
    try:
        sio.connect(
            url,
            socketio_path=socketio_path,
            transports=["websocket"]
        )
    except Exception as e:
        print(f"Initial connection failed: {e}")
        if not attempt_reconnect():
            sys.exit(1)

    # Capture video from the default webcam (device index 0)
    cap = cv2.VideoCapture(0)

    while True:
        # Read a frame from the webcam
        ret, frame = cap.read()

        # If a frame is successfully captured and connected to the server
        if ret and connected:
            # Encode the frame as a JPEG image
            ret, jpeg = cv2.imencode('.jpg', frame)

            # Emit the JPEG image bytes via the 'screen_data' event
            sio.emit('screen_data', jpeg.tobytes())

        # Sleep before capturing the next frame
        # sio.sleep(0.1)  # Adjust the sleep time to change frame rate (e.g., sleep(0.1) for ~10 fps)
        sio.sleep(2)

        # Check if the 'q' key is pressed to exit the loop
        if cv2.waitKey(1) == ord('q'):
            print("Exit command received. Exiting...")
            break

        # If not connected, attempt to reconnect
        if not connected:
            print("Lost connection. Attempting to reconnect...")
            if not attempt_reconnect():
                print("Could not reconnect. Exiting.")
                break

    # Disconnect the Socket.IO client
    sio.disconnect()

    # Release the webcam resource
    cap.release()

    # Close any OpenCV windows (if any were opened)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

