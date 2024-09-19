const registerClient = async () => {
    const name = document.getElementById('username').value;
    const response = await fetch('http://192.168.124.224:5000/register', {
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
            alert(`Client registered with URI: ${data.client_uri}`);
            setupMessageStream(name);
        } else {
            alert('Failed to register client.');
        }
    } else {
        alert('Error registering client.');
    }
};

const sendMessage = async () => {
    const from = localStorage.getItem('client_name');
    const to = document.getElementById('receiver').value;
    const message = document.getElementById('message').value;

    const response = await fetch('http://192.168.124.224:5000/send', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ from, to, message }),
    });

    if (response.ok) {
        const data = await response.json();
        if (data.message) {
            alert(data.message);
        } else {
            alert(`Failed to send message: ${data.error}`);
        }
    } else {
        alert('Error sending message.');
    }
};

// Function to handle incoming messages
const setupMessageStream = (clientName) => {
    const eventSource = new EventSource(`http://192.168.124.224:5000/messages?client=${clientName}`);
    eventSource.onmessage = (event) => {
        const messageDiv = document.getElementById('messages');
        const message = JSON.parse(event.data);
        const messageElement = document.createElement('div');
        messageElement.textContent = `From ${message.from_user}: ${message.message}`;
        messageDiv.appendChild(messageElement);
    };
};

window.onload = () => {
    // Check if client name is already stored
    const clientName = localStorage.getItem('client_name');
    if (clientName) {
        setupMessageStream(clientName);
    }
};