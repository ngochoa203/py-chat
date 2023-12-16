import cv2
import sys
import pickle
import struct
import threading
import socket
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.uic import loadUi
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class VideoDisplaySignal(QObject):
    signal = pyqtSignal(QPixmap, object)

class CallVideo(QMainWindow):
    def __init__(self, username, friend_name, camera_index, is_server):
        super().__init__()
        loadUi("ui/CallVideo.ui", self)
        self.username = username
        self.friend_name = friend_name
        self.is_server = is_server
        self.camera_index = camera_index

        if self.is_server:
            self.setWindowTitle(f"Video Call - {self.friend_name} gọi cho bạn")
            self.start_server()
        else:
            self.setWindowTitle(f"Video Call - {self.friend_name} gọi cho bạn")
            self.connect_to_server()

        self.btnStopCall.clicked.connect(self.stop_call)
        self.btnCamera.clicked.connect(self.toggle_camera)
        self.btnMicro.clicked.connect(self.toggle_micro)

        self.lbFriendCam = self.findChild(QLabel, 'lbFriendCam')
        self.lbMyCam = self.findChild(QLabel, 'lbMyCam')

        self.camera = cv2.VideoCapture(self.camera_index)
        self.is_camera_on = True
        self.is_micro_on = True

        self.display_video_signal = VideoDisplaySignal()
        self.display_video_signal.signal.connect(self.display_video)
        
        self.receive_thread = threading.Thread(target=self.receive_video)
        self.send_thread = threading.Thread(target=self.send_video)

        self.receive_thread.start()
        self.send_thread.start()

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.server_socket.bind(("::1", 1234))
        self.server_socket.listen(1)
        self.client_socket, _ = self.server_socket.accept()

    def connect_to_server(self):
        self.client_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.client_socket.connect(("::1", 1234))

    def stop_call(self):
        self.client_socket.send(f"call_video_response|{self.username}|{self.friend_name}|reject".encode())
        self.client_socket.close()
        if hasattr(self, 'server_socket'):
            self.server_socket.close()
        self.receive_thread.join()
        self.send_thread.join()
        self.camera.release()
        self.close()

    def toggle_camera(self):
        self.is_camera_on = not self.is_camera_on

    def toggle_micro(self):
        self.is_micro_on = not self.is_micro_on

    def receive_video(self):
        while True:
            try:
                data = b""
                while True:
                    packet = self.client_socket.recv(4096)
                    if not packet:
                        break
                    data += packet
                    if len(data) >= struct.calcsize(">L"):
                        msg_size = struct.unpack(">L", data[:struct.calcsize(">L")])[0]
                        if len(data) >= msg_size + struct.calcsize(">L"):
                            frame_data = data[struct.calcsize(">L"):msg_size + struct.calcsize(">L")]
                            data = data[msg_size + struct.calcsize(">L"):]
                            frame = pickle.loads(frame_data)
                            pixmap = self.convert_frame_to_pixmap(frame)
                            self.display_video_signal.signal.emit(pixmap, self.lbFriendCam)
            except Exception as e:
                print(f"Error in receive_video: {e}")
                break

    def send_video(self):
        while True:
            try:
                if self.is_camera_on:
                    ret, frame = self.camera.read()
                    if not ret:
                        break
                    frame_data = pickle.dumps(frame)
                    msg = struct.pack(">L", len(frame_data)) + frame_data
                    self.client_socket.send(msg)
                    pixmap = self.convert_frame_to_pixmap(frame)
                    self.display_video_signal.signal.emit(pixmap, self.lbMyCam)
            except Exception as e:
                print(f"Error in send_video: {e}")
                break

    def display_video(self, pixmap, frame_label):
        if frame_label is self.lbFriendCam:
            self.lbFriendCam.setPixmap(pixmap)
            self.lbFriendCam.setAlignment(Qt.AlignCenter)
        elif frame_label is self.lbMyCam:
            self.lbMyCam.setPixmap(pixmap)
            self.lbMyCam.setAlignment(Qt.AlignCenter)
        else:
            print(f"Unknown frame label: {frame_label}")

    def convert_frame_to_pixmap(self, frame):
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)
        return pixmap

def main(username, friend_name, camera_index, is_server):
    app = QApplication(sys.argv)
    video_call_app = CallVideo(username, friend_name, camera_index, is_server)
    video_call_app.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main('hoa1', 'han1', 0, False)
