import sys
import socket
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox
from PyQt5.uic import loadUi
from Main import MainChat

server_address = ("fe80::76ae:f254:ba11:2395%21", 1234)

class LoginApp(QWidget):
    def __init__(self):
        super().__init__()
        loadUi("ui/Login.ui", self)
        self.show()
        self.btnLogin.clicked.connect(self.login)
        self.btnRegisterWidget.clicked.connect(self.show_register_widget)
        self.btnRegister.clicked.connect(self.register)
        self.btnLoginWidget.clicked.connect(self.show_login_widget)
        self.main_window = None

    def send_message_to_server(self, message):
        try:
            client_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            client_socket.connect(server_address)
            client_socket.send(message.encode('utf-8'))
            response = client_socket.recv(1024).decode('utf-8')
            client_socket.close()
            return response
        except Exception as e:
            return f"Error connecting to server: {str(e)}"

    def login(self):
        username = self.txtUserLogin.text()
        password = self.txtPasswordLogin.text()
        message = f"login|{username}|{password}"
        response = self.send_message_to_server(message)
        if response == "login_success":
            QMessageBox.information(self, "Login", "Login successful!")
            self.open_main_window(username)
        else:
            QMessageBox.warning(self, "Login", f"Login failed. Server response: {response}")

    def register(self):
        name = self.txtName.text()
        username = self.txtUsernameRegister.text()
        password = self.txtPasswordRegister.text()
        re_password = self.txtRePasswordRegister.text()
        phone = self.txtPhone.text()
        if password != re_password:
            QMessageBox.warning(self, "Registration", "Passwords do not match.")
            return
        message = f"register|{name}|{username}|{password}|{phone}"
        response = self.send_message_to_server(message)
        if response == "register_success":
            self.show_login_widget()
        else:
            QMessageBox.warning(self, "Registration", response)

    def open_main_window(self, username):
        if not self.main_window:
            self.main_window = MainChat(username)
        self.main_window.show()
        self.hide()

    def show_register_widget(self):
        self.registerWidget.setEnabled(True)
        self.loginWidget.setVisible(False)
        self.registerWidget.setVisible(True)

    def show_login_widget(self):
        self.loginWidget.setEnabled(True)
        self.registerWidget.setVisible(False)
        self.loginWidget.setVisible(True)

def main():
    app = QApplication(sys.argv)
    login_app = LoginApp()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
