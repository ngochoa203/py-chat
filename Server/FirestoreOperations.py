from firebase_admin import credentials, firestore, initialize_app
import uuid, logging

cred = credentials.Certificate("Firestore/py-chat-ipv6.json")
firebase_app = initialize_app(cred)
db = firestore.client()

class FirestoreOperations:
    @staticmethod
    def get_user_list():
        try:
            user_docs = db.collection("Users").stream()
            user_list = [user.id for user in user_docs] 
            return user_list
        except Exception as e:
            logging.error(f"Error getting user list from Firestore: {str(e)}")
            return []
    
    @staticmethod
    def add_friend(username, friend_identifier):
        user_ref = db.collection("Users").document(username)
        friend_query = None
        if friend_identifier.isdigit():
            friend_query = db.collection("Users").where("phone", "==", friend_identifier)
        elif friend_identifier.isalpha():
            friend_query = db.collection("Users").where("name", "==", friend_identifier)
        else:
            friend_query = db.collection("Users").where("username", "==", friend_identifier)
        friend_docs = friend_query.limit(1).get()
        if friend_docs:
            friend_data = friend_docs[0].to_dict()
            user_data = user_ref.get().to_dict()
            friend_username = friend_data["username"]
            if friend_username not in user_data["friends"]:
                user_ref.update({"friends": firestore.ArrayUnion([friend_username])})
                friend_ref = db.collection("Users").document(friend_username)
                friend_ref.update({"friends": firestore.ArrayUnion([username])})
                return "add_friend_success"
            else:
                return "Friend already added"
        else:
            return "User or friend not found"

    @staticmethod
    def get_friends_list(username):
        user_ref = db.collection("Users").document(username)
        user_data = user_ref.get().to_dict()
        if user_data and "friends" in user_data:
            friends_list = user_data["friends"]
            if friends_list:
                return ";".join(friends_list)
            else:
                return "No friends found."
        else:
            return "No friends found."

    @staticmethod
    def save_message(sender, receiver, message, message_type, timestamp):
        try:
            conversation_id = '-'.join(sorted([sender, receiver]))
            messages_ref = db.collection("Messages").document(conversation_id)
            if messages_ref.get().exists:
                current_order = messages_ref.get().to_dict().get("order", 1)
                message_id = str(current_order + 1)

                messages_ref.update({
                    message_id: {
                        "order": current_order + 1,
                        "sender": sender,
                        "receiver": receiver,
                        "message": message,
                        "message_type": message_type,
                        "timestamp": timestamp
                    },
                    "order": current_order + 1
                })
            else:
                message_id = "1"
                messages_ref.set({
                    message_id: {
                        "order": 1,
                        "sender": sender,
                        "receiver": receiver,
                        "message": message,
                        "message_type": message_type,
                        "timestamp": timestamp
                    },
                    "order": 1
                })

            return "save_message_success"
        except Exception as e:
            print(f"Error saving message to Firestore: {str(e)}")
            return "save_message_failed"

    @staticmethod
    def get_messages(sender, receiver):
        try:
            conversation_id = '-'.join(sorted([sender, receiver]))
            messages_ref = db.collection("Messages").document(conversation_id)
            if messages_ref.get().exists:
                messages_data = messages_ref.get().to_dict()
                if messages_data:
                    valid_messages = {k: v for k, v in messages_data.items() if isinstance(v, dict)}
                    messages = [v for _, v in sorted(valid_messages.items(), key=lambda item: item[1].get('order', 1))]
                    return messages
        except Exception as e:
            print(f"Error getting messages from Firestore: {str(e)}")
        return []

    @staticmethod
    def register_user(name, username, password, phone, client_socket):
        user_ref = db.collection("Users").document(username)
        existing_user_data = user_ref.get().to_dict()

        if existing_user_data:
            client_socket.send("Username already exists. Please choose another one.".encode('utf-8'))
            return "register_failed"
        else:
            user_ref.set({
                "name": name,
                "username": username,
                "password": password,
                "phone": phone,
                "friends": []
            })
            client_socket.send("register_success".encode('utf-8'))
            return "register_success"

    @staticmethod
    def login_user(username, password, client_socket):
        user_ref = db.collection("Users").document(username)
        user_data = user_ref.get().to_dict()

        if user_data and user_data["password"] == password:
            client_socket.send("login_success".encode('utf-8'))
            return "login_success"
        else:
            client_socket.send("Login failed. Please check your credentials.".encode('utf-8'))
            return "login_failed"
