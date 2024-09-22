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

    def receive_message(self, from_user, message):
        # Recibe un mensaje de otro usuario y lo agrega a la cola de mensajes del cliente.
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
        # Registra un nuevo cliente en el servidor y devuelve su URI.
        client = ChatClient(name)
        client_uri = daemon.register(client)
        clients[name] = client_uri

        if name not in message_queues:
            message_queues[name] = []

        print(f"Client registered: {name} with URI {client_uri}")
        return {'client_uri': str(client_uri)}

    def send_message(self, from_user, to_user, message):
        # Envía un mensaje de un usuario a otro utilizando la URI del receptor.
        if to_user in clients:
            uri = clients[to_user]
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

def get_public_ip():
    # Obtiene la dirección IP pública del servidor.
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

# Función para iniciar el Name Server de Pyro5 en un hilo separado
def start_nameserver():
    # El Name Server es necesario para registrar y buscar URIs de objetos Pyro.
    # Se inicia dentro de un bucle para funcionar continuamente.
    Pyro5.nameserver.start_ns_loop()

# Crear y lanzar el hilo que ejecutará el Name Server de Pyro5
ns_thread = Thread(target=start_nameserver)
ns_thread.start()

# Pequeña pausa para asegurarnos de que el Name Server está en funcionamiento antes de intentar localizarlo
time.sleep(2)

# Se crea una instancia del daemon de Pyro5 para escuchar las solicitudes de los clientes
daemon = Pyro5.server.Daemon(host=get_public_ip())

# Se localiza el Name Server de Pyro5 para registrar el servidor de chat
ns = Pyro5.api.locate_ns()

# Se crea una instancia del servidor de chat
chat_server = ChatServer()

# Se registra el servidor de chat en el daemon para obtener su URI
chat_server_uri = daemon.register(chat_server)

# Se registra el URI del servidor de chat en el Name Server bajo el nombre "server.chat"
ns.register("server.chat", chat_server_uri)

print(f"Server is ready. URI: {chat_server_uri}")

#region endpoints para el cliente Flask
@app.route('/register', methods=['POST'])
def register():
    # Endpoint para registrar un cliente en el servidor de chat.
    data = request.json
    name = data.get('name')
    if name:
        result = chat_server.register_client(name)
        print(f"Registered client: {name} with URI: {result['client_uri']}")
        return jsonify(result)
    return jsonify({'error': 'Invalid data'}), 400

@app.route('/send', methods=['POST'])
def send():
    # Endpoint para enviar un mensaje de un usuario a otro.
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
    # Endpoint para recibir mensajes en tiempo real para un cliente específico.
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
    # Endpoint para listar todos los clientes registrados.
    return jsonify({'clients': list(clients.keys())})

@app.route('/validate', methods=['GET'])
def validate_user():
    # Endpoint para validar si un usuario está registrado.
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username not provided'}), 400

    if username in clients:
        return jsonify({'message': f'User {username} is registered'}), 200
    else:
        return jsonify({'error': f'User {username} not found'}), 404
#endregion

def run_flask_app():
    # Ejecuta la aplicación Flask en un hilo separado para que funcione en paralelo con Pyro5.
    app.run(host='0.0.0.0', port=5000)

# Se ejecuta cuando el script es lanzado como programa principal
if __name__ == '__main__':
    # Crear y lanzar el hilo que ejecutará la aplicación Flask
    flask_thread = Thread(target=run_flask_app)
    flask_thread.start()
    
    # Mantiene el daemon de Pyro5 en ejecución, escuchando solicitudes
    daemon.requestLoop()
