import socket
import threading
import sys
import os
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QInputDialog, QFileDialog
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.uic import loadUi
from FirestoreOperations import FirestoreOperations

SERVER_DATA_DIR = "ServerData"

if not os.path.exists(SERVER_DATA_DIR):
    os.makedirs(SERVER_DATA_DIR)

class ServerApp(QMainWindow):

    def __init__(self):
        super().__init__()
        loadUi("ui/Server.ui", self)
        self.show()
        self.server_socket = None
        self.client_sockets = {}
        self.server_listening = False
        self.user_model = QStandardItemModel(self.listUser)
        self.listUser.setModel(self.user_model)
        self.btnStartServer.clicked.connect(self.start_server)
        self.btnStopServer.clicked.connect(self.stop_server)
        self.load_user_list()
        self.lock = threading.Lock()
        self.current_username = None
        
    def get_messages(self, sender, receiver):
        messages = FirestoreOperations.get_messages(sender, receiver)
        messages_data = ";".join([f"{msg['sender']}|{msg['message']}|{msg['message_type']}|{msg['timestamp']}" for msg in messages])
        return messages_data

    def send_message(self, sender, receiver, message, message_type, timestamp, sender_socket):
        try:
            FirestoreOperations.save_message(sender, receiver, message, message_type, timestamp)
            if receiver in self.client_sockets:
                with self.lock:
                    receiving_socket = self.client_sockets[receiver]
                    receiving_socket.send(f"received_message|{sender}|{message}|{message_type}|{timestamp}".encode())
                    receiving_socket.send(f"get_messages|{sender}|{receiver}".encode())
                sender_socket.send(f"send_message|{sender}|{message}|{message_type}|{timestamp}".encode())
        except Exception as e:
            self.txtDisplayMsg.append(f"Error sending message: {str(e)}")
            
    def handle_video_call_request(self, sender, receiver, client_socket):
        print(f"Video request: {self.client_sockets}")
        if receiver in self.client_sockets:
            receiving_socket = self.client_sockets[receiver]
            print(f"Sending video call request from {sender} to {receiver}")
            try:
                receiving_socket.send(f"video_call_request|{sender}|{receiver}".encode())
            except Exception as e:
                print(f"Error sending video call request: {str(e)}")
        else:
            print(f"Receiver {receiver} not found in client_sockets")

    def handle_video_call_response(self, sender, receiver, response, client_socket):
        if receiver in self.client_sockets:
            receiving_socket = self.client_sockets[receiver]
            print(f"Sending video call response from {sender} to {receiver}: {response}")
            try:
                receiving_socket.send(f"video_call_response|{receiver}|{sender}|{response}".encode())
                print("Video call response oke")
            except Exception as e:
                print(f"Error sending video call response: {str(e)}")
        else:
            print(f"Receiver {receiver} not found in client_sockets")

    def handle_file_transfer(self, sender, receiver, file_name, file_size, client_socket):
        try:
            # Gửi phản hồi cho client
            response_message = "ready_to_receive"
            client_socket.send(response_message.encode())

            file_data = client_socket.recv(file_size)
            file_path = os.path.join(SERVER_DATA_DIR, file_name)

            with open(file_path, 'wb') as file:
                file.write(file_data)

            print(f"File '{file_name}' received from {sender} and saved to {file_path}")
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            message = f"{file_name}"
            message_type = "file"
            FirestoreOperations.save_message(sender, receiver, message, message_type, timestamp)
            if receiver in self.client_sockets:
                receiving_socket = self.client_sockets[receiver]
                receiving_socket.send(f"file_received|{sender}|{file_name}".encode())

        except Exception as e:
            print(f"Error handling file transfer: {str(e)}")

    def start_server(self):
        port = int(self.txtPort.text())
        try:
            self.server_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            self.server_socket.bind(("fe80::76ae:f254:ba11:2395%21", port))
            self.server_socket.listen(5)
            self.server_listening = True
            self.txtDisplayMsg.append(f"Server started on port: {port}")
        except Exception as e:
            self.txtDisplayMsg.append(f"Error starting server: {str(e)}")
            return
        threading.Thread(target=self.accept_connections).start()

    def accept_connections(self):
        while self.server_listening:
            try:
                client_socket, client_address = self.server_socket.accept()
                username = client_socket.recv(1024).decode()
                if username: 
                    self.client_sockets[username] = client_socket
                    self.txtDisplayMsg.append(f"Accepted connection from {client_address} with username {username}")
                    threading.Thread(target=self.handle_client, args=(client_socket,)).start()
            except Exception as e:
                if self.server_listening:
                    self.txtDisplayMsg.append(f"Error accepting connection: {str(e)}")

    def load_user_list(self):
        self.user_model.clear()
        user_list = FirestoreOperations.get_user_list()
        for user in user_list:
            item = QStandardItem(user)
            self.user_model.appendRow(item)

    def handle_client(self, client_socket):
        try:
            while True:
                try:
                    client_message = client_socket.recv(1024).decode('utf-8', errors='replace')
                    if not client_message:
                        break
                    parts = client_message.split("|")
                    if parts[0] == "login":
                        username, password = parts[1], parts[2]
                        response = FirestoreOperations.login_user(username, password, client_socket)
                        if response == "login_success":
                            self.txtDisplayMsg.append(f"User {username} logged in.")
                            client_socket.send("login_success".encode('utf-8'))
                            return username
                        else:
                            client_socket.send("login_failed".encode('utf-8'))

                    elif parts[0] == "register":
                        name, username, password, phone = parts[1], parts[2], parts[3], parts[4]
                        response = FirestoreOperations.register_user(name, username, password, phone, client_socket)
                        if response == "register_success":
                            self.txtDisplayMsg.append(f"User {username} registered.")
                            client_socket.send("register_success".encode('utf-8'))
                        else:
                            client_socket.send(response.encode('utf-8'))
                            client_socket.close()
                            break

                    elif parts[0] == "add_friend":
                        username = parts[1]
                        friend_username = parts[2]
                        response = self.add_friend(username, friend_username, client_socket)
                        if response:
                            client_socket.send(response.encode('utf-8'))

                    elif parts[0] == "list_friends":
                        username = parts[1]
                        response = self.get_friends_list(username, client_socket)
                        client_socket.send(response.encode('utf-8'))

                    elif parts[0] == "send_message":
                        sender, receiver, message, message_type, timestamp = parts[1], parts[2], parts[3], parts[4], parts[5]
                        self.send_message(sender, receiver, message, message_type, timestamp, client_socket)

                    elif parts[0] == "get_messages":
                        sender, receiver = parts[1], parts[2]
                        messages_str = self.get_messages(sender, receiver)
                        client_socket.send(messages_str.encode('utf-8'))

                    elif parts[0] == "call_video_request":
                        sender, receiver = parts[1], parts[2]
                        self.handle_video_call_request(sender, receiver, client_socket)

                    elif parts[0] == "call_video_response":
                        sender, receiver, response = parts[1], parts[2], parts[3]
                        self.handle_video_call_response(sender, receiver, response, client_socket)

                    elif parts[0] == "send_file":
                        sender, receiver, file_name, file_size = parts[1], parts[2], parts[3], int(parts[4])
                        self.handle_file_transfer(sender, receiver, file_name, file_size, client_socket)

                except UnicodeDecodeError as decode_error:
                    print(f"UnicodeDecodeError: {str(decode_error)}")
                    break
        except Exception as e:
            self.txtDisplayMsg.append(f"Error handling client: {str(e)}")
        finally:
            client_socket.close()

    def add_friend(self, username, friend_username, client_socket):
        response = FirestoreOperations.add_friend(username, friend_username)
        client_socket.send(response.encode('utf-8'))

    def get_friends_list(self, username, client_socket):
        response = FirestoreOperations.get_friends_list(username)
        client_socket.send(response.encode('utf-8'))
        return response

    def stop_server(self):
        try:
            for client_socket in self.client_sockets.values():
                try:
                    client_socket.shutdown(socket.SHUT_RDWR)
                    client_socket.close()
                except:
                    pass
            if self.server_socket:
                self.server_listening = False
                self.server_socket.close()
                self.txtDisplayMsg.append(f"Server on port {self.txtPort.text()} stopped")
        except Exception as e:
            self.txtDisplayMsg.append(f"Error stopping server: {str(e)}")

def main():
    app = QApplication(sys.argv)
    server_app = ServerApp()
    server_app.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
