# This test file is testing camera is working or not.

import cv2
import numpy as np

def test_camera():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    assert ret == True
    assert isinstance(frame, np.ndarray)
    assert frame.shape[0] > 0
    assert frame.shape[1] > 0
    assert frame.shape[2] == 3
    assert frame.dtype == np.uint8
    assert frame.size > 0
    assert frame.ndim == 3
    assert frame is not None

# Run the test
# pytest tests/Raspberry\ Pi/test_camera.py
# Output:
# ============================= test session starts ==============================
# platform linux -- Python 3.7.3, pytest-5.2.2, pluggy-0.13.0
# rootdir: /home/pi/Desktop/pytest-tutorial
# collected 1 item

# tests/Raspberry Pi/test_camera.py .                                      [100%]

# ============================== 1 passed in 0.68s ===============================