// For production: replace '' with your backend URL (e.g. 'https://rio-backend.onrender.com')
// In development: keep '' (backend serves frontend at localhost:8000)
const API_BASE = '';

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
let audioContext = null;
let pcmChunks = [];

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
            throw new Error(data.detail?.error || data.detail || data.error || 'Upload failed');
        }
    } catch (err) {
        uploadStatus.textContent = `Error: ${err.message}`;
        uploadStatus.style.color = 'var(--accent-red)';
    }
});

// Chat UI functions
function appendMessage(text, sender, isError = false, correction = null) {
    if (emptyState) emptyState.style.display = 'none';
    
    // Ensure text is a string (not an object that would show "[object Object]")
    if (typeof text !== 'string') {
        text = text?.error || text?.message || JSON.stringify(text) || 'Unknown error';
    }
    
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

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
            appendMessage(data.detail?.error || data.detail || data.error || 'Something went wrong.', 'agent', true);
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
    speechRecognition.continuous = false;
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
        isRecording = false;
        messageInput.placeholder = 'Type your question...';
        voiceStatus.textContent = 'Tap the mic and speak naturally.';

        // Auto-send after speech ends naturally or was stopped by user
        const transcript = messageInput.value.trim();
        if (transcript) {
            sendMessage(transcript);
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

    // Web Audio API / WAV path
    if (audioContext) {
        stopWavRecording();
        return;
    }

    // Legacy MediaRecorder path (if somehow active)
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        return;
    }

    // Web Speech API path
    if (speechRecognition) {
        try { speechRecognition.stop(); } catch (e) {}
        // onend handles UI cleanup and auto-send
        return;
    }

    isRecording = false;
    micBtn.classList.remove('recording');
    stopListeningAnimation();
    messageInput.placeholder = 'Type your question...';
    voiceStatus.textContent = 'Tap the mic and speak naturally.';
}

// --- WAV encoding helpers (no ffmpeg needed) ---
function encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    const writeStr = (offset, str) => {
        for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
    };
    writeStr(0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeStr(8, 'WAVE');
    writeStr(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeStr(36, 'data');
    view.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) {
        let s = Math.max(-1, Math.min(1, samples[i]));
        s = s < 0 ? s * 0x8000 : s * 0x7FFF;
        view.setInt16(44 + i * 2, s, true);
    }
    return buffer;
}

function sendWavToBackend(wavBlob) {
    const formData = new FormData();
    formData.append('file', wavBlob, 'recording.wav');

    showTypingIndicator();
    messageInput.placeholder = 'Transcribing...';
    voiceStatus.textContent = 'Transcribing...';

    fetch(`${API_BASE}/ask-voice`, { method: 'POST', body: formData })
        .then(async res => {
            if (!res.ok) {
                const text = await res.text();
                let errMsg = text;
                try {
                    const json = JSON.parse(text);
                    errMsg = json.detail?.error || json.detail || json.error || text;
                } catch (e) {}
                throw new Error(`HTTP ${res.status}: ${typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg)}`);
            }
            return res.json();
        })
        .then(data => {
            removeTypingIndicator();
            if (data.answer) {
                messageInput.value = data.transcript || '';
                sendMessage(data.transcript || '');
            } else {
                appendMessage(data.detail?.error || data.detail || data.error || 'Failed to process audio.', 'agent', true);
            }
        })
        .catch(err => {
            removeTypingIndicator();
            appendMessage(`Error: ${err.message}`, 'agent', true);
        })
        .finally(() => {
            messageInput.placeholder = 'Type your question...';
            voiceStatus.textContent = 'Tap the mic and speak naturally.';
        });
}

// Web Audio API recording — captures raw PCM and encodes as WAV (no ffmpeg needed)
async function fallbackAudioRecording() {
    try {
        audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(audioStream);
        const sampleRate = audioContext.sampleRate;
        pcmChunks = [];

        const processor = audioContext.createScriptProcessor(4096, 1, 1);
        processor.onaudioprocess = (event) => {
            const input = event.inputBuffer.getChannelData(0);
            pcmChunks.push(new Float32Array(input));
        };

        const dummyGain = audioContext.createGain();
        dummyGain.gain.value = 0; // Mute to prevent feedback loop

        source.connect(processor);
        processor.connect(dummyGain);
        dummyGain.connect(audioContext.destination);


        isRecording = true;
        micBtn.classList.add('recording');
        messageInput.placeholder = 'Recording...';
        voiceStatus.textContent = 'Recording...';
        startListeningAnimation();
    } catch (err) {
        console.error('Microphone error', err);
        const msg = isInsecureContext()
            ? 'Microphone blocked by browser. Mobile devices need HTTPS to access the mic. Use ngrok or localhost.'
            : 'Could not access microphone. Check permissions.';
        appendMessage(msg, 'agent', true);
        voiceStatus.textContent = 'Microphone access denied.';
        micBtn.classList.remove('recording');
        isRecording = false;
        if (audioStream) {
            audioStream.getTracks().forEach(t => t.stop());
            audioStream = null;
        }
        audioContext = null;
    }
}

function stopWavRecording() {
    if (!audioContext || !pcmChunks.length) return;

    // Compute total length
    let totalLen = 0;
    for (const chunk of pcmChunks) totalLen += chunk.length;
    const allSamples = new Float32Array(totalLen);
    let offset = 0;
    for (const chunk of pcmChunks) {
        allSamples.set(chunk, offset);
        offset += chunk.length;
    }

    const sampleRate = audioContext.sampleRate;
    const wavBuffer = encodeWAV(allSamples, sampleRate);
    const wavBlob = new Blob([wavBuffer], { type: 'audio/wav' });

    // Cleanup
    audioContext.close();
    audioContext = null;
    pcmChunks = [];
    if (audioStream) {
        audioStream.getTracks().forEach(t => t.stop());
        audioStream = null;
    }

    isRecording = false;
    micBtn.classList.remove('recording');
    stopListeningAnimation();

    sendWavToBackend(wavBlob);
}

micBtn.addEventListener('click', () => {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
});

window.addEventListener('beforeunload', () => {
    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
        audioStream = null;
    }
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
});

// Check for secure context (HTTPS required for mic on mobile)
function isInsecureContext() {
    // localhost and 127.0.0.1 are always treated as secure for mic access
    const host = location.hostname;
    if (host === 'localhost' || host === '127.0.0.1' || host === '[::1]') {
        return false;
    }
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

