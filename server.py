import Pyro5.api
import socket
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from collections import defaultdict
import time
import json

app = Flask(__name__)
CORS(app)

# Diccionario para almacenar clientes y colas de mensajes
clients = {}
message_queues = defaultdict(list)  # Queue messages for each client

#region chats
@Pyro5.api.expose
class ChatClient:
    def __init__(self, name):
        self.name = name

    def receive_message(self, from_user, message):
        # Recibe un mensaje de otro usuario y lo agrega a la cola de mensajes del cliente.
        # :param from_user: Nombre del usuario que envía el mensaje.
        # :param message: Contenido del mensaje.
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
        # :param name: Nombre del cliente que se va a registrar.
        # :return: URI del cliente registrado.
        client = ChatClient(name)
        client_uri = daemon.register(client)
        clients[name] = client_uri

        if name not in message_queues:
            message_queues[name] = []

        print(f"Client registered: {name} with URI {client_uri}")
        return {'client_uri': str(client_uri)}

    def send_message(self, from_user, to_user, message):
        # Envía un mensaje de un usuario a otro, utilizando la URI del receptor.
        # :param from_user: Nombre del usuario que envía el mensaje.
        # :param to_user: Nombre del usuario que recibe el mensaje.
        # :param message: Contenido del mensaje.
        # :return: Resultado del envío del mensaje.
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
    # :return: IP pública como cadena. Si hay un error, retorna 'localhost'.
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

#Se crea una instancia del daemon de Pyro5. El parámetro host se establece en la 
# dirección IP pública del servidor (obtenida a través de la función get_public_ip()). 
# Esto permite que los clientes se conecten al servidor utilizando la IP correcta.
daemon = Pyro5.server.Daemon(host=get_public_ip())

#Se localiza el Name Server de Pyro5, que es un servicio que permite a los clientes 
# encontrar los objetos remotos registrados en el servidor.
ns = Pyro5.api.locate_ns()

#Se crea una instancia de la clase ChatServer, que contiene la lógica para 
# registrar clientes y enviar mensajes.
chat_server = ChatServer()

#Se registra la instancia del servidor de chat (chat_server) en el daemon, lo que permite 
# que sea accesible a través de un URI (Uniform Resource Identifier). Este URI es una 
# referencia única que los clientes usarán para interactuar con el servidor de chat.
chat_server_uri = daemon.register(chat_server)

# Se registra el URI del servidor de chat en el Name Server bajo el nombre 
# "server.chat". Esto permite que los clientes busquen el servidor 
# de chat utilizando este nombre y obtengan la URI para conectarse.
ns.register("server.chat", chat_server_uri)

print(f"Server is ready. URI: {chat_server_uri}")

#region endpoints utilizados por el cliente
@app.route('/register', methods=['POST'])
def register():
    # Endpoint para registrar un cliente.
    # :return: JSON con el URI del cliente registrado o un error si los datos son inválidos.
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
    # :return: Resultado del envío del mensaje o un error si los datos son inválidos.
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
    # Endpoint para recibir mensajes de un cliente en tiempo real.
    # :return: Stream de eventos con los mensajes para el cliente.
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
    # :return: JSON con la lista de nombres de los clientes.
    return jsonify({'clients': list(clients.keys())})

@app.route('/validate', methods=['GET'])
def validate_user():
    # Endpoint para validar si un usuario está registrado.
    # :return: Mensaje de validación o error si el usuario no está registrado.
    username = request.args.get('username')
    if not username:
        return jsonify({'error': 'Username not provided'}), 400

    if username in clients:
        return jsonify({'message': f'User {username} is registered'}), 200
    else:
        return jsonify({'error': f'User {username} not found'}), 404
#endregion

def run_flask_app():
    # Función para ejecutar la aplicación Flask.
    app.run(host='0.0.0.0', port=5000)

#verifica si el script se esta ejecutando como programa principal
if __name__ == '__main__':
    #importa la clase Thread del módulo threading, que permite crear y manejar hilos de ejecución.
    from threading import Thread
    
    #crea un nuevo hilo (flask_thread) que ejecutará la función run_flask_app, la cual inicia el servidor Flask.
    flask_thread = Thread(target=run_flask_app)
    
    #crea un nuevo hilo (flask_thread) que ejecutará la función run_flask_app, la cual inicia el servidor Flask.
    flask_thread.start()
        
    # Inicia un bucle que permite que el daemon de Pyro5 
    # escuche y procese las solicitudes de los clientes de chat. Esto mantiene 
    # la aplicación en ejecución, gestionando la comunicación de Pyro5 mientras 
    # el servidor Flask opera en segundo plano.
    daemon.requestLoop()
