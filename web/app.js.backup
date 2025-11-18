/**
 * Realtime Avatar - Voice Conversation Web App
 * Phase 4: Interactive voice input with avatar responses
 */

// API Configuration
const API_BASE_URL = 'http://localhost:8000';

// State Management
let mediaRecorder = null;
let audioChunks = [];
let conversationHistory = [];
let isRecording = false;
let isProcessing = false;

// DOM Elements
const recordBtn = document.getElementById('recordBtn');
const statusIndicator = document.getElementById('statusIndicator');
const recordingHint = document.getElementById('recordingHint');
const transcript = document.getElementById('transcript');
const avatarVideo = document.getElementById('avatarVideo');
const videoSource = document.getElementById('videoSource');
const videoPlaceholder = document.getElementById('videoPlaceholder');
const clearBtn = document.getElementById('clearBtn');
const languageSelect = document.getElementById('languageSelect');
const autoPlayCheckbox = document.getElementById('autoPlayCheckbox');
const saveHistoryCheckbox = document.getElementById('saveHistoryCheckbox');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Initializing Realtime Avatar web app...');
    await checkServerHealth();
    setupEventListeners();
    loadConversationHistory();
});

// Setup Event Listeners
function setupEventListeners() {
    // Push-to-talk: mousedown/mouseup for desktop
    recordBtn.addEventListener('mousedown', startRecording);
    recordBtn.addEventListener('mouseup', stopRecording);
    
    // Push-to-talk: touchstart/touchend for mobile
    recordBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startRecording();
    });
    recordBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopRecording();
    });
    
    // Clear conversation
    clearBtn.addEventListener('click', clearConversation);
    
    // Settings
    saveHistoryCheckbox.addEventListener('change', (e) => {
        if (e.target.checked) {
            saveConversationHistory();
        } else {
            localStorage.removeItem('conversationHistory');
        }
    });
}

// Check Server Health
async function checkServerHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        
        if (data.status === 'healthy' && data.models_loaded) {
            updateStatus('Ready', 'ready');
            console.log('Server ready:', data);
        } else {
            updateStatus('Initializing...', 'loading');
            console.log('Server initializing:', data);
        }
    } catch (error) {
        updateStatus('Server offline', 'error');
        console.error('Health check failed:', error);
    }
}

// Start Recording
async function startRecording() {
    if (isRecording || isProcessing) return;
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });
        
        audioChunks = [];
        
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };
        
        mediaRecorder.onstop = async () => {
            // Stop all tracks
            stream.getTracks().forEach(track => track.stop());
            
            // Process the recorded audio
            await processRecording();
        };
        
        mediaRecorder.start();
        isRecording = true;
        
        // Update UI
        recordBtn.classList.add('recording');
        recordingHint.textContent = 'Recording... Release to send';
        updateStatus('🎙️ Listening', 'recording');
        
    } catch (error) {
        console.error('Failed to start recording:', error);
        updateStatus('Microphone error', 'error');
        alert('Failed to access microphone. Please grant permission and try again.');
    }
}

// Stop Recording
function stopRecording() {
    if (!isRecording) return;
    
    mediaRecorder.stop();
    isRecording = false;
    
    // Update UI
    recordBtn.classList.remove('recording');
    recordingHint.textContent = 'Hold to speak';
}

// Process Recording
async function processRecording() {
    if (audioChunks.length === 0) {
        updateStatus('No audio recorded', 'error');
        return;
    }
    
    isProcessing = true;
    updateStatus('Processing...', 'loading');
    
    try {
        // Create audio blob
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        
        // Convert to WAV if needed (webm works for most cases)
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        formData.append('language', languageSelect.value);
        
        // Send to conversation endpoint
        const response = await fetch(`${API_BASE_URL}/api/v1/conversation`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Conversation processing failed');
        }
        
        const data = await response.json();
        
        // Update transcript
        addToTranscript('user', data.user_text);
        addToTranscript('assistant', data.response_text);
        
        // Update conversation history
        if (saveHistoryCheckbox.checked) {
            conversationHistory.push(
                { role: 'user', content: data.user_text },
                { role: 'assistant', content: data.response_text }
            );
            saveConversationHistory();
        }
        
        // Play avatar video
        const videoUrl = `${API_BASE_URL}${data.video_url}`;
        playAvatarVideo(videoUrl);
        
        // Show timing info
        console.log('Conversation processed:', {
            userText: data.user_text,
            responseText: data.response_text,
            totalTime: data.total_time,
            metadata: data.metadata
        });
        
        updateStatus(`Generated in ${data.total_time.toFixed(1)}s`, 'ready');
        
    } catch (error) {
        console.error('Processing failed:', error);
        updateStatus('Processing failed', 'error');
        addToTranscript('system', `Error: ${error.message}`);
    } finally {
        isProcessing = false;
        setTimeout(() => {
            if (!isRecording && !isProcessing) {
                updateStatus('Ready', 'ready');
            }
        }, 2000);
    }
}

// Play Avatar Video
function playAvatarVideo(videoUrl) {
    videoSource.src = videoUrl;
    avatarVideo.load();
    
    // Hide placeholder, show video
    videoPlaceholder.style.display = 'none';
    avatarVideo.style.display = 'block';
    
    // Auto-play if enabled
    if (autoPlayCheckbox.checked) {
        avatarVideo.play().catch(err => {
            console.log('Autoplay prevented:', err);
            // Show play button or prompt
        });
    }
}

// Add to Transcript
function addToTranscript(role, text) {
    // Remove empty state
    const emptyState = transcript.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
    
    // Create message element
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${role}`;
    
    const label = document.createElement('span');
    label.className = 'message-label';
    label.textContent = role === 'user' ? 'You:' : role === 'assistant' ? 'Bruce:' : 'System:';
    
    const content = document.createElement('p');
    content.className = 'message-content';
    content.textContent = text;
    
    messageDiv.appendChild(label);
    messageDiv.appendChild(content);
    
    transcript.appendChild(messageDiv);
    
    // Scroll to bottom
    transcript.scrollTop = transcript.scrollHeight;
}

// Clear Conversation
function clearConversation() {
    transcript.innerHTML = '<p class="empty-state">Your conversation will appear here...</p>';
    conversationHistory = [];
    localStorage.removeItem('conversationHistory');
    
    // Reset video
    avatarVideo.pause();
    avatarVideo.style.display = 'none';
    videoPlaceholder.style.display = 'flex';
    videoSource.src = '';
}

// Update Status
function updateStatus(text, state) {
    const statusText = statusIndicator.querySelector('.status-text');
    const statusDot = statusIndicator.querySelector('.status-dot');
    
    statusText.textContent = text;
    statusIndicator.className = `status-indicator status-${state}`;
}

// Save/Load Conversation History
function saveConversationHistory() {
    if (saveHistoryCheckbox.checked) {
        localStorage.setItem('conversationHistory', JSON.stringify(conversationHistory));
    }
}

function loadConversationHistory() {
    const saved = localStorage.getItem('conversationHistory');
    if (saved) {
        conversationHistory = JSON.parse(saved);
        saveHistoryCheckbox.checked = true;
        
        // Restore transcript (optional)
        // conversationHistory.forEach(msg => {
        //     addToTranscript(msg.role, msg.content);
        // });
    }
}

// Keyboard shortcut: Space bar to record
document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && !e.repeat && e.target === document.body) {
        e.preventDefault();
        startRecording();
    }
});

document.addEventListener('keyup', (e) => {
    if (e.code === 'Space' && e.target === document.body) {
        e.preventDefault();
        stopRecording();
    }
});

// Warn before leaving during processing
window.addEventListener('beforeunload', (e) => {
    if (isProcessing) {
        e.preventDefault();
        e.returnValue = 'Processing in progress. Are you sure you want to leave?';
    }
});
