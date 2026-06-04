// For production: replace '' with your backend URL (e.g. 'https://rio-backend.onrender.com')
// In development: keep '' (backend serves frontend at localhost:8000)
const API_BASE = 'https://rio-ai.onrender.com';

// DOM Elements
const themeToggle = document.getElementById('theme-toggle');
const body = document.body;
const pdfUpload = document.getElementById('pdf-upload');
const uploadBtn = document.getElementById('upload-btn');
const uploadStatus = document.getElementById('upload-status');
const chatMessages = document.getElementById('chat-messages');
const emptyState = document.getElementById('empty-state');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const micBtn = document.getElementById('mic-btn');
const voiceStatus = document.getElementById('voice-status');
const voiceWave = document.getElementById('voice-wave');
const toast = document.getElementById('toast');
const attachBtn = document.getElementById('attach-btn');
const imageUpload = document.getElementById('image-upload');

// State
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let audioStream = null;
let speechRecognition = null;

// Theme Toggle
const themeIconSun = document.getElementById('theme-icon-sun');
const themeIconMoon = document.getElementById('theme-icon-moon');
themeToggle.addEventListener('click', () => {
    body.classList.toggle('light-mode');
    const isLight = body.classList.contains('light-mode');
    themeIconSun.style.display = isLight ? 'none' : 'block';
    themeIconMoon.style.display = isLight ? 'block' : 'none';
});

// Clear Chat
const clearBtn = document.getElementById('clear-btn');
if (clearBtn) {
    clearBtn.addEventListener('click', async () => {
        try {
            await fetch(`${API_BASE}/history`, { method: 'DELETE' });
            // Remove all messages and typing indicators
            const messages = chatMessages.querySelectorAll('.message, .typing-indicator');
            messages.forEach(msg => msg.remove());
            
            // Show empty state if it exists
            if (emptyState) emptyState.style.display = 'block';
            
            showToast();
            toast.textContent = 'Chat cleared';
            setTimeout(() => { toast.textContent = 'Copied!'; }, 2000); // Reset toast text
        } catch (err) {
            console.error('Failed to clear chat', err);
        }
    });
}

// PDF Upload
uploadBtn.addEventListener('click', () => pdfUpload.click());

pdfUpload.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
        uploadStatus.textContent = 'Please select a PDF file.';
        uploadStatus.style.color = 'var(--accent-red)';
        return;
    }

    uploadStatus.textContent = 'Indexing...';
    uploadStatus.style.color = 'var(--text-color)';
    
    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API_BASE}/upload-pdf`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        
        if (res.ok) {
            uploadStatus.textContent = `Ready: ${file.name}`;
            uploadStatus.style.color = 'var(--accent-emerald)';
            if (emptyState) emptyState.style.display = 'none';
            
            if (data.analysis) {
                appendMessage(data.analysis, 'agent');
            }
        } else {
            throw new Error(data.detail || data.error || 'Upload failed');
        }
    } catch (err) {
        uploadStatus.textContent = `Error: ${err.message}`;
        uploadStatus.style.color = 'var(--accent-red)';
    }
});

// Chat UI functions
function appendMessage(text, sender, isError = false, correction = null) {
    if (emptyState) emptyState.style.display = 'none';
    
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const idx = text.indexOf('Answer - ');
    const isSplit = sender === 'agent' && idx !== -1 && text.startsWith('Based on');

    if (isSplit) {
        // --- First message: restatement ---
        const msg1 = document.createElement('div');
        msg1.className = 'message agent';
        const label1 = document.createElement('div');
        label1.className = 'sender-label';
        label1.textContent = 'Rio';
        msg1.appendChild(label1);
        const b1 = document.createElement('div');
        b1.className = 'message-bubble message-bubble-hint';
        b1.textContent = text.substring(0, idx).trim();
        b1.addEventListener('click', () => { navigator.clipboard.writeText(text); showToast(); });
        msg1.appendChild(b1);
        const t1 = document.createElement('div');
        t1.className = 'timestamp';
        t1.textContent = timeStr;
        msg1.appendChild(t1);
        chatMessages.appendChild(msg1);

        // --- Second message: answer ---
        const msg2 = document.createElement('div');
        msg2.className = 'message agent';
        const label2 = document.createElement('div');
        label2.className = 'answer-label';
        label2.textContent = 'Answer';
        msg2.appendChild(label2);
        const b2 = document.createElement('div');
        b2.className = 'message-bubble';
        b2.textContent = text.substring(idx);
        b2.addEventListener('click', () => { navigator.clipboard.writeText(text); showToast(); });
        msg2.appendChild(b2);
        const t2 = document.createElement('div');
        t2.className = 'timestamp';
        t2.textContent = timeStr;
        msg2.appendChild(t2);
        chatMessages.appendChild(msg2);
    } else {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender} ${isError ? 'error' : ''}`;
        
        if (sender === 'agent') {
            const label = document.createElement('div');
            label.className = 'sender-label';
            label.textContent = 'Rio';
            msgDiv.appendChild(label);
        
            if (correction && correction.original && correction.corrected) {
                const hint = document.createElement('div');
                hint.className = 'correction-hint';
                hint.textContent = `Heard "${correction.original}" → answering based on related topic`;
                msgDiv.appendChild(hint);
            }
        }
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.textContent = text;
        bubble.addEventListener('click', () => { navigator.clipboard.writeText(text); showToast(); });
        msgDiv.appendChild(bubble);
        
        const time = document.createElement('div');
        time.className = 'timestamp';
        time.textContent = timeStr;
        msgDiv.appendChild(time);
        chatMessages.appendChild(msgDiv);
    }
    
    setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 0);
}

function showTypingIndicator() {
    if (emptyState) emptyState.style.display = 'none';
    
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.id = 'typing-indicator';
    
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.className = 'dot';
        indicator.appendChild(dot);
    }
    
    chatMessages.appendChild(indicator);
    
    // Scroll to bottom with a small delay
    setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 0);
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

function showToast() {
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 2000);
}

// Send Message
async function sendMessage(text = null) {
    const query = text || messageInput.value.trim();
    if (!query) return;

    messageInput.value = '';
    appendMessage(query, 'user');
    showTypingIndicator();

    try {
        const res = await fetch(`${API_BASE}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: query })
        });
        const data = await res.json();
        
        removeTypingIndicator();
        
        if (res.ok) {
            appendMessage(data.answer, 'agent', false, data.corrected ? data : null);
        } else {
            appendMessage(data.detail || data.error || 'Something went wrong.', 'agent', true);
        }
    } catch (err) {
        removeTypingIndicator();
        appendMessage('Network error. Please make sure the backend is running.', 'agent', true);
    }
}

// Event Listeners for Text Input
sendBtn.addEventListener('click', () => sendMessage());
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

// Speech Recognition (live transcription in input bar)
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    speechRecognition = new SR();
    speechRecognition.continuous = true;
    speechRecognition.interimResults = true;
    speechRecognition.lang = 'en-US';

    speechRecognition.onresult = (event) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            transcript += event.results[i][0].transcript;
        }
        messageInput.value = transcript;
    };

    speechRecognition.onerror = (event) => {
        if (event.error === 'no-speech' || event.error === 'aborted') return;
        console.error('Speech recognition error', event.error);
        stopRecording();
    };

    speechRecognition.onend = () => {
        stopListeningAnimation();
        micBtn.classList.remove('recording');
        if (isRecording) {
            isRecording = false;
            messageInput.placeholder = 'Type your question...';
            voiceStatus.textContent = 'Tap the mic and speak naturally.';
        }
    };
}

// Voice Input
function startListeningAnimation() {
    if (voiceWave) voiceWave.classList.add('active');
}

function stopListeningAnimation() {
    if (voiceWave) voiceWave.classList.remove('active');
}

function startRecording() {
    if (isInsecureContext()) {
        const httpsWarning = document.getElementById('https-warning');
        if (httpsWarning) httpsWarning.style.display = 'block';
        appendMessage('Microphone blocked — mobile browsers require HTTPS. Use ngrok to get a secure tunnel URL.', 'agent', true);
        return;
    }

    if (speechRecognition) {
        isRecording = true;
        micBtn.classList.add('recording');
        messageInput.value = '';
        messageInput.placeholder = 'Listening...';
        voiceStatus.textContent = 'Listening... speak now.';
        startListeningAnimation();

        try {
            speechRecognition.start();
        } catch (err) {
            console.warn('Speech recognition failed', err);
            fallbackAudioRecording();
        }
    } else {
        fallbackAudioRecording();
    }
}

function stopRecording() {
    if (!isRecording) return;

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        return;
    }

    if (speechRecognition) {
        try { speechRecognition.stop(); } catch (e) {}
    }

    isRecording = false;
    micBtn.classList.remove('recording');
    stopListeningAnimation();
    messageInput.placeholder = 'Type your question...';
    voiceStatus.textContent = 'Tap the mic and speak naturally.';
}

// Fallback: MediaRecorder for browsers without Web Speech API
async function fallbackAudioRecording() {
    try {
        if (!audioStream) {
            audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        }
        audioChunks = [];
        mediaRecorder = new MediaRecorder(audioStream);
        isRecording = true;
        micBtn.classList.add('recording');
        messageInput.placeholder = 'Recording...';
        voiceStatus.textContent = 'Recording...';
        startListeningAnimation();

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            isRecording = false;
            micBtn.classList.remove('recording');
            stopListeningAnimation();
            messageInput.placeholder = 'Transcribing...';
            voiceStatus.textContent = 'Transcribing...';
            showTypingIndicator();

            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.webm');

            try {
                const res = await fetch(`${API_BASE}/ask-voice`, {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                removeTypingIndicator();

                if (res.ok) {
                    messageInput.value = data.transcript;
                } else {
                    appendMessage(data.detail || data.error || 'Failed to process audio.', 'agent', true);
                }
            } catch (err) {
                removeTypingIndicator();
                appendMessage('Network error processing audio.', 'agent', true);
            }

            messageInput.placeholder = 'Type your question...';
            voiceStatus.textContent = 'Tap the mic and speak naturally.';
        };

        mediaRecorder.start();
    } catch (err) {
        console.error('Microphone error', err);
        const msg = isInsecureContext()
            ? 'Microphone blocked by browser. Mobile devices need HTTPS to access the mic. Use ngrok or localhost.'
            : 'Could not access microphone. Check permissions.';
        appendMessage(msg, 'agent', true);
        voiceStatus.textContent = 'Microphone access denied.';
        micBtn.classList.remove('recording');
        isRecording = false;
        audioStream = null;
    }
}

micBtn.addEventListener('click', () => {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
});

micBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    if (!isRecording) startRecording();
});

micBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    if (isRecording) stopRecording();
});

window.addEventListener('beforeunload', () => {
    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
        audioStream = null;
    }
});

// Check for secure context (HTTPS required for mic on mobile)
function isInsecureContext() {
    return !window.isSecureContext && location.protocol !== 'file:';
}

// Fix mobile viewport height (address bar issue)
function setViewportHeight() {
    const vh = window.innerHeight * 0.01;
    document.documentElement.style.setProperty('--vh', vh + 'px');
}
setViewportHeight();
window.addEventListener('resize', setViewportHeight);

// Sidebar toggle for mobile
const sidebarToggle = document.getElementById('sidebar-toggle');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebar-overlay');

function updateSidebarForViewport() {
    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
        sidebar.classList.add('mobile-hidden');
        sidebar.classList.remove('mobile-visible');
        sidebarOverlay.classList.remove('active');
    } else {
        sidebar.classList.remove('mobile-hidden', 'mobile-visible');
        sidebarOverlay.classList.remove('active');
    }
}

function toggleSidebar(show) {
    if (window.innerWidth > 768) return;

    if (show) {
        sidebar.classList.remove('mobile-hidden');
        sidebar.classList.add('mobile-visible');
        sidebarOverlay.classList.add('active');
    } else {
        sidebar.classList.add('mobile-hidden');
        sidebar.classList.remove('mobile-visible');
        sidebarOverlay.classList.remove('active');
    }
}

if (sidebarToggle && sidebar && sidebarOverlay) {
    updateSidebarForViewport();
    sidebarToggle.addEventListener('click', () => toggleSidebar(true));
    sidebarOverlay.addEventListener('click', () => toggleSidebar(false));
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768) {
            sidebar.classList.remove('mobile-hidden', 'mobile-visible');
            sidebarOverlay.classList.remove('active');
        } else {
            sidebar.classList.add('mobile-hidden');
            sidebar.classList.remove('mobile-visible');
        }
    });
}

// Image Upload
attachBtn.addEventListener('click', () => imageUpload.click());

imageUpload.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (evt) => {
        const dataUrl = evt.target.result;
        appendImageMessage(dataUrl, 'user');
        showTypingIndicator();

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch(`${API_BASE}/upload-image`, {
                method: 'POST',
                body: formData,
            });
            const data = await res.json();
            removeTypingIndicator();

            if (res.ok) {
                appendMessage(data.answer, 'agent');
            } else {
                appendMessage(data.detail?.error || data.detail || 'Failed to process image.', 'agent', true);
            }
        } catch (err) {
            removeTypingIndicator();
            appendMessage('Network error processing image.', 'agent', true);
        }
    };
    reader.readAsDataURL(file);
    imageUpload.value = '';
});

function appendImageMessage(dataUrl, sender) {
    if (emptyState) emptyState.style.display = 'none';

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    const img = document.createElement('img');
    img.src = dataUrl;
    img.alt = 'Uploaded image';
    bubble.appendChild(img);

    const time = document.createElement('div');
    time.className = 'timestamp';
    const now = new Date();
    time.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    msgDiv.appendChild(bubble);
    msgDiv.appendChild(time);
    chatMessages.appendChild(msgDiv);

    setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 0);
}

// Protocol checks
if (window.location.protocol === 'file:') {
    const warningBanner = document.getElementById('protocol-warning');
    if (warningBanner) {
        warningBanner.style.display = 'block';
    }
} else if (isInsecureContext()) {
    const httpsWarning = document.getElementById('https-warning');
    if (httpsWarning) {
        httpsWarning.style.display = 'block';
    }
}

