import cv2
import pickle
import socket
import struct
import sys
import threading
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.uic import loadUi
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class VideoDisplaySignal(QObject):
    signal = pyqtSignal(QPixmap, object)

class VideoCallApp(QMainWindow):
    def __init__(self, username, friend_name):
        super().__init__()
        loadUi("ui/CallVideo.ui", self)
        self.username = username
        self.friend_name = friend_name
        self.setWindowTitle(f"Cuộc gọi video - {self.username} gọi {self.friend_name}")

        self.btnStopCall.clicked.connect(self.stop_call)
        self.btnCamera.clicked.connect(self.toggle_camera)
        self.btnMicro.clicked.connect(self.toggle_micro)

        self.client_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.client_socket.connect(("::1", 1234))

        # Gửi yêu cầu cuộc gọi video đến máy chủ
        self.client_socket.send(f"call_video_request|{self.username}|{self.friend_name}".encode())

        self.lbFriendCam = self.findChild(QLabel, 'lbFriendCam')
        self.lbMyCam = self.findChild(QLabel, 'lbMyCam')

        self.camera = cv2.VideoCapture(0)
        # self.camera = cv2.VideoCapture(1)
        self.is_camera_on = True
        self.is_micro_on = True
        self.call_accepted = False

        self.lock = threading.Lock()

        self.display_video_signal = VideoDisplaySignal()
        self.display_video_signal.signal.connect(self.display_video)

        self.receive_thread = threading.Thread(target=self.receive_video)
        self.send_thread = threading.Thread(target=self.send_video)

        self.receive_thread.start()
        self.send_thread.start()

    def stop_call(self):
        # Send the end video call response to the server
        self.client_socket.send(f"call_video_response|{self.username}|{self.friend_name}|reject".encode())
        self.client_socket.close()  # Close the connection when ending the call
        self.receive_thread.join()  # Wait for threads to finish
        self.send_thread.join()
        self.close()


    def toggle_camera(self):
        self.is_camera_on = not self.is_camera_on

    def toggle_micro(self):
        self.is_micro_on = not self.is_micro_on

    def receive_video(self):
        try:
            while True:
                payload_size = struct.unpack(">L", self.client_socket.recv(4))[0]

                if payload_size == 0:
                    # Received end video call message
                    break

                frame_data = b""
                while len(frame_data) < payload_size:
                    chunk = self.client_socket.recv(4096)
                    if not chunk:
                        print("Connection closed while receiving frame data.")
                        return
                    frame_data += chunk

                frame = pickle.loads(frame_data)

                if frame is not None:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format_RGB888)

                    print(f"Received video frame for {self.lbFriendCam}")
                    print(f"Image size: {img.size()}")

                    pixmap = QPixmap.fromImage(img)
                    print(f"Pixmap size: {pixmap.size()}")

                    self.display_video_signal.signal.emit(pixmap, self.lbFriendCam)

        except Exception as e:
            print(f"Error receiving video: {str(e)}")

    def send_video(self):
        try:
            while True:
                if self.is_camera_on:
                    ret, frame = self.camera.read()
                    if ret:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        img = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format_RGB888)
                        pixmap = QPixmap.fromImage(img)
                        self.display_video_signal.signal.emit(pixmap, self.lbMyCam)

                        frame_data = pickle.dumps(frame)
                        sent_size = struct.pack(">L", len(frame_data))
                        self.client_socket.send(sent_size + frame_data)

                time.sleep(0.1)
        except Exception as e:
            print(f"Lỗi khi gửi video: {str(e)}")

    def display_video(self, pixmap, frame_label):
        # print(f"Received video frame for {frame_label}")
        if frame_label is self.lbFriendCam:
            print("Displaying video on lbFriendCam")
            self.lbFriendCam.setPixmap(pixmap)
            self.lbFriendCam.setAlignment(Qt.AlignCenter)
        elif frame_label is self.lbMyCam:
            # print("Displaying video on lbMyCam")
            self.lbMyCam.setPixmap(pixmap)
            self.lbMyCam.setAlignment(Qt.AlignCenter)
        else:
            print(f"Unknown frame label: {frame_label}")



def main(username, friend_name):
    app = QApplication(sys.argv)
    video_call_app = VideoCallApp(username, friend_name)
    video_call_app.show()
    sys.exit(app.exec_())

# if __name__ == '__main__':
#     main('han1', 'hoa1')
#     # main('hoa1', 'han1')
