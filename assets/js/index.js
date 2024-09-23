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
            window.location = "client.html";
        } else {
            console.error('Failed to register client.');
        }
    } else {
        console.error('Error registering client.');
    }
};

const setReceiver = (receiver) => {
    localStorage.receiver = receiver;
};

const validateUser = async (username) => {
    const response = await fetch(`${server}/validate?username=${username}`);
    return response.ok;
};

const sendMessage = async () => {
    const from = localStorage.getItem('client_name');
    const to = localStorage.receiver;
    const message = document.getElementById('message').value;
    document.getElementById('message').value = "";

    const fromExists = await validateUser(from);
    const toExists = await validateUser(to);

    if (!fromExists || !toExists) {
        console.error('Invalid sender or receiver.');
        return;
    }

    let attempts = 0;
    const maxAttempts = 3;
    let success = false;

    while (attempts < maxAttempts && !success) {
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
                success = true; // Mensaje enviado con éxito
            }
        } else {
            attempts++;
            console.error('Error sending message, retrying...');
            await new Promise(res => setTimeout(res, 1000)); // Esperar un segundo antes de reintentar
        }
    }

    if (!success) {
        console.error('Failed to send message after multiple attempts.');
    }
};

const searchUsers = async () => {
    const query = document.getElementById('search').value.trim();
    const userList = document.getElementById('user-list');
    userList.innerHTML = '';

    if (query === '') {
        userList.style.display = 'none';
        return;
    }

    const response = await fetch(`${server}/search?query=${query}`);
    
    if (response.ok) {
        const result = await response.json();
        result.users.forEach(user => {
            const userElement = document.createElement('div');
            userElement.classList.add('nav-item');  // Agregas la clase 'nav-item'
            userElement.innerHTML = `<div class="receiver-container p-2 bg-light text-dark my-2" onclick="selectUser('${user}')">${user}</div>`;
            userList.appendChild(userElement);
        });
        userList.style.display = result.users.length > 0 ? 'block' : 'none';
    } else {
        console.log("No users found or error occurred.");
        userList.style.display = 'none';
    }
};

const selectUser = (username) => {
    setReceiver(username);
    
    const sidebar = document.getElementById('sidebar-users');

    if (!Array.from(sidebar.children).some(child => child.textContent.trim() === username)) {
        const userElement = document.createElement('li');
        userElement.classList.add('nav-item');
        userElement.innerHTML = `<div class="receiver-container p-2 bg-light text-dark my-2" onclick="setReceiver('${username}')">${username}</div>`;
        sidebar.appendChild(userElement);
    }
    
    document.getElementById('user-list').style.display = 'none';
    document.getElementById('search').value = '';
};

const setupMessageStream = (clientName) => {
    const eventSource = new EventSource(`${server}/messages?client=${clientName}`);
    
    eventSource.onmessage = (event) => {
        const message = JSON.parse(event.data);
        addMessage(message.from_user, message.message, 'received');
    };

    eventSource.onerror = (error) => {
        console.error('Error in EventSource:', error);
        eventSource.close();
    };

    // Manejar el cierre de la conexión
    window.addEventListener('beforeunload', () => {
        eventSource.close();
    });
};

const addMessage = (from, message, type) => {
    const messageDiv = document.getElementById('messages');
    const messageElement = document.createElement('div');
    messageElement.className = `message ${type}`;
    messageElement.textContent = `${from}: ${message}`;
    messageDiv.appendChild(messageElement);
    messageDiv.scrollTop = messageDiv.scrollHeight;
};

window.onload = () => {
    const clientName = localStorage.getItem('client_name');
    if (clientName) {
        validateUser(clientName).then((validate) => {
            if (validate) {
                setupMessageStream(clientName);
            }
        });
    }
};
