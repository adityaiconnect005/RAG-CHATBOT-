let currentThreadId = null;

const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const sessionIdDisplay = document.getElementById('session-id-display');
const newChatBtn = document.getElementById('new-chat-btn');

async function initSession() {
    try {
        const response = await fetch('/api/chat/new');
        const data = await response.json();
        currentThreadId = data.thread_id;
        sessionIdDisplay.textContent = currentThreadId;
    } catch (error) {
        console.error('Failed to initialize session', error);
        sessionIdDisplay.textContent = "Error connecting to server";
    }
}

function appendMessage(role, content) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', role);
    
    const avatarDiv = document.createElement('div');
    avatarDiv.classList.add('avatar');
    
    const img = document.createElement('img');
    if (role === 'user') {
        img.src = "https://ui-avatars.com/api/?name=U+S&background=2563EB&color=fff";
    } else {
        img.src = "https://ui-avatars.com/api/?name=F+E&background=0D8ABC&color=fff";
    }
    avatarDiv.appendChild(img);
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.classList.add('bubble');
    // Basic formatting for line breaks
    bubbleDiv.innerHTML = content.replace(/\n/g, '<br>');
    
    msgDiv.appendChild(avatarDiv);
    msgDiv.appendChild(bubbleDiv);
    
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator() {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message', 'assistant');
    msgDiv.id = 'typing-indicator-msg';
    
    const avatarDiv = document.createElement('div');
    avatarDiv.classList.add('avatar');
    const img = document.createElement('img');
    img.src = "https://ui-avatars.com/api/?name=F+E&background=0D8ABC&color=fff";
    avatarDiv.appendChild(img);
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.classList.add('bubble');
    bubbleDiv.innerHTML = `
        <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    `;
    
    msgDiv.appendChild(avatarDiv);
    msgDiv.appendChild(bubbleDiv);
    
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
    const el = document.getElementById('typing-indicator-msg');
    if (el) el.remove();
}

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = userInput.value.trim();
    if (!text || !currentThreadId) return;
    
    // UI Update
    appendMessage('user', text);
    userInput.value = '';
    sendBtn.disabled = true;
    showTypingIndicator();
    
    // API Call
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                thread_id: currentThreadId,
                message: text
            })
        });
        
        const data = await response.json();
        removeTypingIndicator();
        
        if (response.ok) {
            appendMessage('assistant', data.message);
        } else {
            appendMessage('assistant', `Error: ${data.detail || 'Failed to get response'}`);
        }
    } catch (error) {
        removeTypingIndicator();
        appendMessage('assistant', 'Network error. Please make sure the server is running.');
    } finally {
        sendBtn.disabled = false;
        userInput.focus();
    }
});

newChatBtn.addEventListener('click', () => {
    chatMessages.innerHTML = `
        <div class="message assistant">
            <div class="avatar">
                <img src="https://ui-avatars.com/api/?name=F+E&background=0D8ABC&color=fff" alt="Bot">
            </div>
            <div class="bubble">
                New session started. How can I help you today?
            </div>
        </div>
    `;
    initSession();
});

// Start
initSession();
