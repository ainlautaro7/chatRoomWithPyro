import Pyro5.api
import socket
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from collections import defaultdict
import time
import json

app = Flask(__name__)
CORS(app)

clients = {}
message_queues = defaultdict(list)  # Queue messages for each client

#region chats
@Pyro5.api.expose
class ChatClient:
    def __init__(self, name):
        self.name = name

    def receive_message(self, from_user, message):
        # Enviar el mensaje a la cola para este cliente
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
        # Crear una instancia de ChatClient para el cliente
        client = ChatClient(name)
        # Registrar el cliente en el daemon y obtener su URI
        client_uri = daemon.register(client)
        clients[name] = client_uri

        # Asegurarse de que la cola de mensajes para el cliente esté inicializada
        if name not in message_queues:
            message_queues[name] = []

        print(f"Client registered: {name} with URI {client_uri}")
        return {'client_uri': str(client_uri)}

    def send_message(self, from_user, to_user, message):
        if to_user in clients:
            uri = clients[to_user]  # Usar la URI correcta del cliente
            print(f"Sending message to URI: {uri}")
            try:
                with Pyro5.api.Proxy(uri) as recipient:
                    recipient.receive_message(from_user, message)
                return {'message': 'Message sent'}
            except Pyro5.errors.PyroError as e:
                print(f"PyroError: {e}")
                return {'error': f'Failed to send message: {str(e)}'}
        else:
            return {'error': 'Recipient not found'}
#endregion

# detect public id server
def get_public_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception as e:
        print(f"Error getting public IP: {e}")
        ip = 'localhost'
    finally:
        s.close()
    return ip

daemon = Pyro5.server.Daemon(host=get_public_ip())
ns = Pyro5.api.locate_ns()
chat_server = ChatServer()
chat_server_uri = daemon.register(chat_server)
ns.register("example.chatserver", chat_server_uri)

# print server id & others utils dir
print(f"Server is ready. URI: {chat_server_uri}")

#region endpoints
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    if name:
        result = chat_server.register_client(name)
        print(f"Registered client: {name} with URI: {result['client_uri']}")
        return jsonify(result)
    return jsonify({'error': 'Invalid data'}), 400

@app.route('/send', methods=['POST'])
def send():
    data = request.json
    from_user = data.get('from')
    to_user = data.get('to')
    message = data.get('message')
    if from_user and to_user and message:
        print(f"Sending message from {from_user} to {to_user}")
        result = chat_server.send_message(from_user, to_user, message)
        print(f"Send result: {result}")
        return jsonify(result)
    return jsonify({'error': 'Invalid data'}), 400

@app.route('/messages', methods=['GET'])
def messages():
    client_name = request.args.get('client')
    print(f"Request for messages for client: {client_name}")
    
    if client_name in clients:
        def generate():
            while True:
                if message_queues[client_name]:
                    message = message_queues[client_name].pop(0)
                    yield f"data: {json.dumps(message)}\n\n"
                else:
                    time.sleep(1)

        return Response(generate(), mimetype='text/event-stream')
    else:
        print(f"Client '{client_name}' not found.")
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
#endregion

def run_flask_app():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    from threading import Thread
    flask_thread = Thread(target=run_flask_app)
    flask_thread.start()
    daemon.requestLoop()
