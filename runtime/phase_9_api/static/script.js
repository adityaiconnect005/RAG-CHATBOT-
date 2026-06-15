let currentThreadId = null;

const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const sessionIdDisplay = document.getElementById('session-id-display');
const newChatBtn = document.getElementById('new-chat-btn');
const recentChatsList = document.getElementById('recent-chats-list');

async function initSession() {
    try {
        const response = await fetch('/api/chat/new');
        const data = await response.json();
        currentThreadId = data.thread_id;
        if (sessionIdDisplay) {
            sessionIdDisplay.textContent = currentThreadId;
        }
        await loadRecentChats();
    } catch (error) {
        console.error('Failed to initialize session', error);
        if (sessionIdDisplay) {
            sessionIdDisplay.textContent = "Error connecting to server";
        }
    }
}

async function loadRecentChats() {
    try {
        const response = await fetch('/api/chat/threads');
        const data = await response.json();
        
        recentChatsList.innerHTML = '';
        data.threads.forEach(thread => {
            const li = document.createElement('li');
            li.classList.add('chat-history-item');
            
            // Truncate title if it's too long
            let displayTitle = thread.title;
            if (displayTitle && displayTitle.length > 30) {
                displayTitle = displayTitle.substring(0, 30) + '...';
            }
            
            li.textContent = displayTitle;
            li.title = thread.title; // Show full on hover
            li.addEventListener('click', () => loadChatHistory(thread.id));
            recentChatsList.appendChild(li);
        });
    } catch (error) {
        console.error('Failed to load recent chats', error);
    }
}

async function loadChatHistory(threadId) {
    try {
        const response = await fetch(`/api/chat/history?thread_id=${threadId}`);
        const data = await response.json();
        
        currentThreadId = threadId;
        
        if (sessionIdDisplay) {
            sessionIdDisplay.textContent = currentThreadId;
        }

        chatMessages.innerHTML = `
            <div class="message assistant">
                <div class="avatar">
                    <img src="https://ui-avatars.com/api/?name=F+E&background=0D8ABC&color=fff" alt="Bot">
                </div>
                <div class="bubble">
                    Loaded history for session.
                </div>
            </div>
        `;
        
        data.history.forEach(msg => {
            appendMessage(msg.role, msg.content);
        });
        
    } catch (error) {
        console.error('Failed to load chat history', error);
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
    
    let mainContent = content;
    let followUpQuestions = [];
    
    // Parse out ```json blocks
    const jsonMatch = content.match(/```json\s*([\s\S]*?)\s*```/);
    if (jsonMatch) {
        try {
            const data = JSON.parse(jsonMatch[1]);
            if (data.follow_up_questions) {
                followUpQuestions = data.follow_up_questions;
            }
        } catch(e) {
            console.error("Failed to parse follow up JSON", e);
        }
        mainContent = content.replace(jsonMatch[0], '').trim();
    }
    
    bubbleDiv.innerHTML = mainContent.replace(/\n/g, '<br>');
    
    if (followUpQuestions.length > 0 && role === 'assistant') {
        const followUpDiv = document.createElement('div');
        followUpDiv.classList.add('follow-ups');
        followUpQuestions.forEach(q => {
            const btn = document.createElement('button');
            btn.classList.add('follow-up-btn');
            btn.textContent = q;
            btn.addEventListener('click', () => {
                userInput.value = q;
                chatForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
            });
            followUpDiv.appendChild(btn);
        });
        bubbleDiv.appendChild(followUpDiv);
    }
    
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
            await loadRecentChats();
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

newChatBtn.addEventListener('click', async () => {
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
    await initSession();
});

// Start
initSession();
