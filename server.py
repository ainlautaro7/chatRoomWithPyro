import Pyro5.api
import Pyro5.nameserver
import socket
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from collections import defaultdict
import time
import json
from threading import Thread

app = Flask(__name__)
CORS(app)

# Diccionario para almacenar clientes y colas de mensajes
clients = {}
message_queues = defaultdict(list)

#region chats
@Pyro5.api.expose
class ChatClient:
    def __init__(self, name):
        self.name = name
        self.active = True  # Cambiar a 'True' en lugar de 'true'

    def receive_message(self, from_user, message):
        if self.active:
            if self.name in message_queues:
                message_queues[self.name].append({
                    'from_user': from_user,
                    'message': message
                })
            else:
                print(f"Error: Client {self.name} not found for receiving message.")

@Pyro5.api.expose
class ChatServer:
    def register_client(self, name):
        client = ChatClient(name)
        client_uri = daemon.register(client)
        clients[name] = client_uri

        if name not in message_queues:
            message_queues[name] = []

        return {'client_uri': str(client_uri)}

    def send_message(self, from_user, to_user, message):
        if to_user in clients:
            uri = clients[to_user]
            try:
                with Pyro5.api.Proxy(uri) as recipient:
                    recipient.receive_message(from_user, message)
                return {'message': 'Message sent'}
            except Pyro5.errors.CommunicationError:
                print(f"Recipient {to_user} not available. Queueing message.")
                message_queues[to_user].append({
                    'from_user': from_user,
                    'message': message
                })
                return {'message': 'Recipient not available, message queued'}
        else:
            return {'error': 'Recipient not found'}

    def search_users(self, query):
        if not query:
            return list(clients.keys())
        matching_users = [user for user in clients.keys() if query.lower() in user.lower()]
        return matching_users

    def set_client_active(self, name, active):
        if name in clients:
            client_uri = clients[name]
            with Pyro5.api.Proxy(client_uri) as client:
                client.active = active
            return {'message': f'Client {name} active status set to {active}'}
        else:
            return {'error': 'Client not found'}
#endregion

def get_public_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception as e:
        ip = 'localhost'
    finally:
        s.close()
    return ip

def start_nameserver():
    Pyro5.nameserver.start_ns_loop()

ns_thread = Thread(target=start_nameserver)
ns_thread.start()

time.sleep(2)

daemon = Pyro5.server.Daemon(host=get_public_ip())
ns = Pyro5.api.locate_ns()

chat_server = ChatServer()
chat_server_uri = daemon.register(chat_server)
ns.register("server.chat", chat_server_uri)

print(f"Server is ready. URI: {chat_server_uri}")

#region endpoints para el cliente Flask
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    if name:
        result = chat_server.register_client(name)
        return jsonify(result)
    return jsonify({'error': 'Invalid data'}), 400

@app.route('/send', methods=['POST'])
def send():
    data = request.json
    from_user = data.get('from')
    to_user = data.get('to')
    message = data.get('message')
    if from_user and to_user and message:
        result = chat_server.send_message(from_user, to_user, message)
        return jsonify(result)
    return jsonify({'error': 'Invalid data'}), 400

@app.route('/messages', methods=['GET'])
def messages():
    client_name = request.args.get('client')
    if client_name in clients:
        def generate():
            while True:
                if message_queues[client_name]:
                    message = message_queues[client_name].pop(0)
                    yield f"data: {json.dumps(message)}\n\n"
                else:
                    time.sleep(0.5)

        return Response(generate(), mimetype='text/event-stream')
    else:
        return jsonify({'error': 'Client not found'}), 404

@app.route('/clients', methods=['GET'])
def list_clients():
    return jsonify({'clients': list(clients.keys())})

@app.route('/validate', methods=['GET'])
def validate_user():
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username not provided'}), 400

    if username in clients:
        return jsonify({'message': f'User {username} is registered'}), 200
    else:
        return jsonify({'error': f'User {username} not found'}), 404

@app.route('/search', methods=['GET'])
def search_users():
    query = request.args.get('query', '')
    result = chat_server.search_users(query)

    if result:
        return jsonify({'users': result}), 200
    else:
        return jsonify({'error': 'No users found'}), 404
#endregion

def run_flask_app():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    flask_thread = Thread(target=run_flask_app)
    flask_thread.start()
    daemon.requestLoop()
