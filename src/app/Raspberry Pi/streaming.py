#!/usr/bin/python3

from flask import Flask, Response, request, stream_with_context

import cv2


app = Flask(__name__)
timestamp = None

PORT = 5000
CACHE_TIME = 2
PROC_CACHE = 30
DEFAULT_RESOLUTION = (1920, 1080)


def generate_video_stream(camera_id=0, resolution=DEFAULT_RESOLUTION):
    camera = cv2.VideoCapture(camera_id)  # Open default camera
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    try:
        while True:
            success, frame = camera.read()
            if not success:
                break
            # Resize the frame if it doesn't match the desired resolution
            if frame.shape[1] != resolution[0] or frame.shape[0] != resolution[1]:
                frame = cv2.resize(frame, resolution)
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    finally:
        camera.release()

@app.route('/api/video_feed/')
def video_feed():
    resolution = request.args.get('resolution', f'{DEFAULT_RESOLUTION[0]}x{DEFAULT_RESOLUTION[1]}')
    width, height = map(int, resolution.split('x'))
    return Response(stream_with_context(generate_video_stream(camera_id=0, resolution=(width, height))),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/video_feed/<int:camera_id>')
def video_feed_camera(camera_id):
    resolution = request.args.get('resolution', f'{DEFAULT_RESOLUTION[0]}x{DEFAULT_RESOLUTION[1]}')
    width, height = map(int, resolution.split('x'))
    return Response(stream_with_context(generate_video_stream(camera_id=camera_id, resolution=(width, height))),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run('0.0.0.0', PORT)
