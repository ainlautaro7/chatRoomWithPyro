const server = 'http://192.168.124.224:5000';

const registerClient = async () => {
    const name = document.getElementById('username').value;
    const response = await fetch(`${server}/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name }),
    });

    if (response.ok) {
        const data = await response.json();
        if (data.client_uri) {
            localStorage.setItem('client_name', name);
            console.info(`Client registered with URI: ${data.client_uri}`);
            setupMessageStream(name);
        } else {
            console.error('Failed to register client.');
        }
    } else {
        console.error('Error registering client.');
    }
};

const validateUser = async (username) => {
    const response = await fetch(`${server}/validate?username=${username}`);
    return response.ok;
};

const sendMessage = async () => {
    const from = localStorage.getItem('client_name');
    const to = document.getElementById('receiver').value;
    const message = document.getElementById('message').value;

    // Validar si el emisor está registrado
    const fromExists = await validateUser(from);
    if (!fromExists) {
        console.error('El usuario emisor no está registrado.');
        return;
    }

    // Validar si el receptor está registrado
    const toExists = await validateUser(to);
    if (!toExists) {
        console.error('El receptor no está registrado.');
        return;
    }

    // Si ambos están registrados, enviamos el mensaje
    const response = await fetch(`${server}/send`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ from, to, message }),
    });

    if (response.ok) {
        const data = await response.json();
        if (data.message) {
            addMessage(from, message, 'sent');
            console.info(data.message);
        } else {
            console.error(`Failed to send message: ${data.error}`);
        }
    } else {
        console.error('Error sending message.');
    }
};

// Function to handle incoming messages
const setupMessageStream = (clientName) => {
    const eventSource = new EventSource(`${server}/messages?client=${clientName}`);
    eventSource.onmessage = (event) => {
        const message = JSON.parse(event.data);
        addMessage(message.from_user, message.message, 'received');
    };
};

// Function to add messages to the chat
const addMessage = (from, message, type) => {
    const messageDiv = document.getElementById('messages');
    const messageElement = document.createElement('div');
    messageElement.className = `message ${type}`;
    messageElement.textContent = `${message}`;
    messageDiv.appendChild(messageElement);
    messageDiv.scrollTop = messageDiv.scrollHeight; // Desplazar hacia abajo al nuevo mensaje
};

window.onload = () => {
    const clientName = localStorage.getItem('client_name');
    validateUser(clientName).then((validate) => {
        if (validate) {
            setupMessageStream(clientName);
        }
    });
};
