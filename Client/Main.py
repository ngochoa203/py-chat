import os
import sys
import socket
from PyQt5.QtWidgets import QApplication, QMainWindow, QInputDialog, QLabel, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.uic import loadUi
from CallVideo import CallVideo

server_address = ("fe80::76ae:f254:ba11:2395%21", 1234)

class MessageThread(QThread):
    messages_received = pyqtSignal(str)

    def __init__(self, client_socket, sender, receiver):
        super().__init__()
        self.client_socket = client_socket
        self.sender = sender
        self.receiver = receiver
        self.running = True

    def run(self):
        while self.running:
            self.client_socket.send(f"get_messages|{self.sender}|{self.receiver}".encode())
            messages_data = self.client_socket.recv(1024).decode()
            self.messages_received.emit(messages_data)
            self.msleep(100)

    def stop(self):
        self.running = False

class VideoCallThread(QThread):
    video_call_request_signal = pyqtSignal(str)

    def __init__(self, client_socket):
        super().__init__()
        self.client_socket = client_socket
        self.running = True

    def run(self):
        timer = QTimer(self)
        timer.timeout.connect(self.check_video_call_request)
        timer.start(1000)
        self.exec_()

    def check_video_call_request(self):
        try:
            data = self.client_socket.recv(1024)
            if not data:
                self.stop()
                return

            message = data.decode('utf-8')
            if message.startswith("video_call_request"):
                self.video_call_request_signal.emit(message)
        except Exception as e:
            print(f"Error in VideoCallThread: {str(e)}")

    def stop(self):
        self.running = False

class MainChat(QMainWindow):
    update_messages_signal = pyqtSignal(str)
    def __init__(self, username):
        super().__init__()
        loadUi("ui/MainChat.ui", self)
        self.username = username
        self.client_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self.client_socket.connect(server_address)
        self.client_socket.send(username.encode())
        self.setWindowTitle(f"Py-Chat - {self.username}")
        self.avtUser.setText(self.username)
        self.txtNameUser.setText(self.username)
        self.btnSend.clicked.connect(self.send_message)
        self.btnAddFriend.clicked.connect(self.add_friend)
        self.btnCallVideo.clicked.connect(self.start_call_video)
        self.btnSendFile.clicked.connect(self.send_file_dialog)
        self.listFriends.itemClicked.connect(self.handle_friend_click)
        self.load_friends_list()
        self.friend_name = None
        self.txtMsg.setEnabled(False)
        self.message_thread = MessageThread(self.client_socket, self.username, "")
        self.message_thread.messages_received.connect(self.handle_messages_received)
        self.update_messages_signal.connect(self.display_messages)
        self.message_thread.start()
        
    def send_file_dialog(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select File to Send")
        if file_path:
            self.send_file(file_path)
            
    def send_file(self, file_path):
        try:
            with open(file_path, 'rb') as file:
                file_data = file.read()
                file_name = os.path.basename(file_path)
                message = f"send_file|{self.username}|{self.friend_name}|{file_name}|{len(file_data)}"
                self.client_socket.send(message.encode())
                response = self.client_socket.recv(1024).decode()
                print(f"Response from server: {response}")
                if response == "ready_to_receive":
                    self.client_socket.send(file_data)
                    QMessageBox.information(self, "File Sent", f"File '{file_name}' sent successfully!")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to send file: {response}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error sending file: {str(e)}")
    def download_file(self, sender, file_name):
        save_path, _ = QFileDialog.getSaveFileName(self, "Save File", file_name)
        if save_path:
            try:
                # Gửi yêu cầu tải file đến server
                self.client_socket.send(f"download_file|{self.username}|{sender}|{file_name}".encode())

                # Nhận dữ liệu file từ server
                file_data = self.client_socket.recv(1024)

                # Lưu dữ liệu file vào đường dẫn đã chọn
                with open(save_path, 'wb') as file:
                    file.write(file_data)

                QMessageBox.information(self, "File Downloaded", f"File '{file_name}' downloaded successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error downloading file: {str(e)}")
    def start_call_video(self):
        friend_name = self.txtNameFriend.text()
        print(f"Trying to start a video call with {friend_name}")
        self.client_socket.send(f"call_video_request|{self.username}|{friend_name}".encode())

    def handle_messages_received(self, messages_data):
        parts = messages_data.split("|")
        if parts[0] == "video_call_request":
            caller, friend_name = parts[1], parts[2]
            self.handle_video_call_request(caller, friend_name)
        elif parts[0] == "video_call_response":
            caller, friend_name, response = parts[1], parts[2], parts[3]
            self.handle_video_call_response(caller, friend_name, response)
        else:
            self.update_messages_signal.emit(messages_data)

    def handle_video_call_request(self, sender, receiver):
        if receiver == self.username:
            response = QMessageBox.question(
                self, "Video Call Request", f"Do you want to accept a video call from {sender}?", 
                QMessageBox.Yes | QMessageBox.No
            )
            if response == QMessageBox.Yes:
                self.client_socket.send(f"call_video_response|{self.username}|{sender}|accept".encode())
                print(f"{self.username} accepts the call from {sender}")
                video_call_window_receiver = CallVideo(sender, self.username, 1, True)  # Camera index for receiver
                video_call_window_receiver.show()
            else:
                self.client_socket.send(f"call_video_response|{sender}|{self.username}|reject".encode())
                print(f"{self.username} rejects the call from {sender}")

    def handle_video_call_response(self, sender, receiver, response):
        print(f"Got video call response: sender={sender}, receiver={receiver}, response={response}")
        if sender == self.username:
            if response == "accept":
                print(f"{self.username} accepts the call from {receiver}")
                video_call_window_caller = CallVideo(self.username, receiver, 0, False)  # Camera index for caller
                video_call_window_caller.show()
            elif sender == "reject":
                print(f"{self.username} rejects the call from {receiver}")
                # Handle rejection if needed

    def send_message(self):
        friend_name = self.txtNameFriend.text()
        message = self.txtMsg.text()
        message_type = 'text'
        timestamp = QtCore.QDateTime.currentDateTime().toString(Qt.DefaultLocaleLongDate)
        self.client_socket.send(f"send_message|{self.username}|{friend_name}|{message}|{message_type}|{timestamp}".encode())
        self.add_message("You", message, timestamp)
        self.txtMsg.clear()
        self.listMsg.scrollToBottom()

    def add_friend(self):
        friend_username, ok_pressed = QInputDialog.getText(self, "Add Friend", "Enter friend's username:")
        if ok_pressed and friend_username:
            self.client_socket.send(f"add_friend|{self.username}|{friend_username}".encode())
            response = self.client_socket.recv(1024).decode()
            if response == "add_friend_success":
                QMessageBox.information(self, "Success", f"Friend {friend_username} added successfully!")
                self.load_friends_list()
            else:
                QMessageBox.warning(self, "Error", f"Failed to add friend: {response}")

    def load_friends_list(self):
        self.client_socket.send(f"list_friends|{self.username}".encode())
        friends_data = self.client_socket.recv(1024).decode()

        if friends_data.startswith("No friends found."):
            QMessageBox.information(self, "Friends List", "No friends found.")
            return
        self.listFriends.clear()
        friends_list = friends_data.split(";")
        for friend in friends_list:
            if friend:
                self.load_friend_widget(friend)

    def handle_friend_click(self, item):
        friend_name_widget = self.listFriends.itemWidget(item).findChild(QLabel)
        if friend_name_widget:
            new_friend_name = friend_name_widget.text()
            self.friend_name = new_friend_name
            self.txtNameFriend.setText(new_friend_name)
            self.avtFriend.setText(new_friend_name)
            self.txtMsg.setEnabled(True)
            self.listMsg.clear()
            if (self.message_thread and self.message_thread.isRunning()):
                print("Thread has been deleted.")
                self.clearLoadMsgsThread()
            self.message_thread = MessageThread(self.client_socket, self.username, new_friend_name)
            self.message_thread.messages_received.connect(self.handle_messages_received)
            self.message_thread.start()

    def clearLoadMsgsThread(self):
        self.message_thread.terminate()
        self.message_thread.wait()
        self.message_thread = None

    def display_messages(self, messages_data):
        messages_list = messages_data.split(";")
        current_items_amount = self.listMsg.count()
        if len(messages_list) != current_items_amount:
            self.listMsg.clear()
            for message in messages_list:
                if message:
                    message_parts = message.split("|")
                    if len(message_parts) >= 3:
                        sender, message_text, timestamp = message_parts[:3]
                        message_type = message_parts[3] if len(message_parts) >= 4 else "text"
                        received_message = sender != self.username
                        self.add_message(sender, message_text, message_type, timestamp, received_message)
                        self.listMsg.scrollToBottom()
                        print(f"Added message: {sender}, {message_text}, {message_type}, {timestamp}, {received_message}")

    def add_message(self, sender, message, timestamp, message_type, received_message=False):
        item = QtWidgets.QListWidgetItem(self.listMsg)
        item.setSizeHint(QtCore.QSize(150, 150))
        widget = QtWidgets.QWidget(self.listMsg)
        layout = QtWidgets.QVBoxLayout(widget)
        chat_bubble = QtWidgets.QFrame()
        chat_layout = QtWidgets.QHBoxLayout(chat_bubble)
        chat_bubble.setStyleSheet(
            "background-color: #E1FFC7; border: 1px solid #E1FFC7; border-radius: 15px; padding: 10px;"
        )

        if received_message:
            avatar_label = self.create_avatar_label(sender)
            chat_layout.addWidget(avatar_label)
            QtWidgets.QApplication.processEvents()

        message_container = QtWidgets.QWidget()
        message_container_layout = QtWidgets.QVBoxLayout(message_container)
        print(message_type)
        try:
            if message_type == "text":
                message_label = self.create_message_label(message)
                timestamp_label = self.create_timestamp_label(timestamp)
                message_container_layout.addWidget(message_label)
                message_container_layout.addWidget(timestamp_label)
            elif message_type == "file":
                message_label = self.create_message_label(message)
                timestamp_label = self.create_timestamp_label(timestamp)
                download_icon = self.create_download_icon_label(message)
                message_container_layout.addWidget(message_label)
                message_container_layout.addWidget(download_icon)
                message_container_layout.addWidget(timestamp_label)
                download_icon.mousePressEvent = lambda event: self.download_file(sender, message)
            chat_layout.addWidget(message_container)

            if not received_message:
                layout.addStretch(1)

            layout.addWidget(chat_bubble)
            self.listMsg.addItem(item)
            self.listMsg.setItemWidget(item, widget)
        except Exception as e:
            print(f"Error adding message: {str(e)}")

    def create_download_icon_label(self, file_name):
        try:
            download_icon = QtWidgets.QLabel()
            download_icon.setPixmap(QtGui.QPixmap(".\\Icon\iconDownload.png"))
            download_icon.setToolTip(f"Download {file_name}")
            download_icon.setAlignment(QtCore.Qt.AlignCenter)
            return download_icon
        except Exception as e:
            print(f"Error creating download icon label: {str(e)}")
            return QtWidgets.QLabel("Error creating label")

    def load_friend_widget(self, friend_name):
        item = QtWidgets.QListWidgetItem()
        widget_friend = QtWidgets.QWidget()
        label_avt = QtWidgets.QLabel(friend_name, parent=widget_friend)
        label_avt.setGeometry(QtCore.QRect(10, 0, 41, 21))
        label_name = QtWidgets.QLabel(friend_name, parent=widget_friend)
        label_name.setGeometry(QtCore.QRect(60, 0, 151, 21))
        item.setSizeHint(widget_friend.sizeHint())
        self.listFriends.addItem(item)
        self.listFriends.setItemWidget(item, widget_friend)

    def create_avatar_label(self, sender):
        avatar_label = QtWidgets.QLabel()
        avatar_label.setFixedSize(31, 31)
        avatar_label.setStyleSheet(
            "border: 1px solid #E1FFC7; background-color: white; border-radius: 15px;"
        )
        avatar_label.setAlignment(QtCore.Qt.AlignCenter)
        avatar_label.setObjectName("avatar_label")
        avatar_label.setText(sender[:3])
        return avatar_label

    def create_message_label(self, message):
        message_label = QtWidgets.QLabel(message)
        message_label.setStyleSheet(
            "background-color: #E1FFC7; border: none; padding: 5px; color: black; font-family: Arial; font-size: 12px;"
        )
        return message_label

    def create_timestamp_label(self, timestamp):
        timestamp_label = QtWidgets.QLabel(timestamp)
        timestamp_label.setStyleSheet(
            "background-color: #E1FFC7; border: none; padding: 5px; color: gray; font-family: Arial; font-size: 10px;"
        )
        return timestamp_label

def main(username):
    app = QApplication(sys.argv)
    main_chat = MainChat(username)
    main_chat.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main('han1')