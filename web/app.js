/**
 * Realtime Avatar - Voice Conversation Web App
 * Phase 4: Interactive voice input with avatar responses
 */

// API Configuration
const API_BASE_URL = 'http://35.243.218.244:8000';
const USE_STREAMING = true; // Toggle streaming mode

// State Management
let mediaRecorder = null;
let audioChunks = [];
let conversationHistory = [];
let isRecording = false;
let isProcessing = false;
let currentEventSource = null;
let videoQueue = [];
let isPlayingQueue = false;

// DOM Elements
const recordBtn = document.getElementById('recordBtn');
const statusIndicator = document.getElementById('statusIndicator');
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
    // Click to toggle recording: click to start, click to stop
    recordBtn.addEventListener('click', toggleRecording);
    
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

// Toggle Recording (Click to Start/Stop)
function toggleRecording() {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

// Start Recording
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
        
        if (USE_STREAMING) {
            await processStreamingConversation(audioBlob);
        } else {
            await processBlockingConversation(audioBlob);
        }
        
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

// Process with Streaming (SSE)
async function processStreamingConversation(audioBlob) {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');
    formData.append('language', languageSelect.value);
    
    let userText = '';
    let responseText = '';
    let chunkCount = 0;
    const startTime = Date.now();
    
    // Upload audio and get streaming response
    const response = await fetch(`${API_BASE_URL}/api/v1/conversation/stream`, {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    let buffer = '';
    
    // Process stream in real-time
    while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
            console.log('Stream completed');
            break;
        }
        
        // Decode chunk immediately
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        
        // Process all complete events in buffer
        let eventEndIndex;
        while ((eventEndIndex = buffer.indexOf('\n\n')) !== -1) {
            const eventText = buffer.substring(0, eventEndIndex);
            buffer = buffer.substring(eventEndIndex + 2);
            
            if (!eventText.trim()) continue;
            
            const event = parseSSE(eventText);
            if (!event) continue;
            
            console.log(`[${(Date.now() - startTime) / 1000}s] SSE Event:`, event.type);
            
            // Process event immediately
            switch (event.type) {
                case 'transcription':
                    userText = event.data.text;
                    addToTranscript('user', userText);
                    updateStatus(`Transcribed (${event.data.time.toFixed(1)}s)`, 'loading');
                    console.log('Transcription:', userText.substring(0, 80));
                    break;
                
                case 'llm_response':
                    responseText = event.data.text;
                    addToTranscript('assistant', responseText);
                    updateStatus('Generating video...', 'loading');
                    console.log('LLM Response:', responseText.substring(0, 80));
                    break;
                
                case 'video_chunk':
                    chunkCount++;
                    // Add cache buster to prevent stale video loading
                    const baseUrl = `${API_BASE_URL}${event.data.video_url}`;
                    const videoUrl = baseUrl.includes('?') ? `${baseUrl}&t=${Date.now()}` : `${baseUrl}?t=${Date.now()}`;
                    const chunkTime = event.data.chunk_time;
                    const elapsedTime = (Date.now() - startTime) / 1000;
                    
                    console.log(`🎬 Chunk ${chunkCount} received at ${elapsedTime.toFixed(1)}s (generated in ${chunkTime.toFixed(1)}s)`);
                    
                    // Add to queue immediately
                    videoQueue.push({
                        url: videoUrl,
                        index: event.data.chunk_index,
                        text: event.data.text_chunk
                    });
                    
                    console.log(`📥 Added chunk ${event.data.chunk_index} to queue. Queue length: ${videoQueue.length}`);
                    
                    if (chunkCount === 1) {
                        const ttff = elapsedTime;
                        updateStatus(`⚡ First chunk (${ttff.toFixed(1)}s TTFF)`, 'loading');
                        console.log(`⚡ TTFF: ${ttff.toFixed(1)}s - Starting playback NOW`);
                    } else {
                        updateStatus(`Chunk ${chunkCount} (${chunkTime.toFixed(1)}s)`, 'loading');
                    }
                    
                    // Start playback immediately (won't interfere if already playing)
                    playVideoQueue();
                    break;
                
                case 'complete':
                    const totalTime = event.data.total_time;
                    updateStatus(`✅ Complete (${totalTime.toFixed(1)}s, ${chunkCount} chunks)`, 'ready');
                    console.log(`Stream complete: ${totalTime.toFixed(1)}s total, ${chunkCount} chunks`);
                    
                    // Update conversation history
                    if (saveHistoryCheckbox.checked) {
                        conversationHistory.push(
                            { role: 'user', content: userText },
                            { role: 'assistant', content: responseText }
                        );
                        saveConversationHistory();
                    }
                    break;
                
                case 'error':
                    throw new Error(event.data.error);
            }
        }
    }
}

// Process with Blocking API (original)
async function processBlockingConversation(audioBlob) {
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
}

// Parse SSE Event
function parseSSE(eventText) {
    const lines = eventText.split('\n');
    let eventType = 'message';
    let eventData = '';
    
    for (const line of lines) {
        if (line.startsWith('event:')) {
            eventType = line.substring(6).trim();
        } else if (line.startsWith('data:')) {
            eventData = line.substring(5).trim();
        }
    }
    
    if (!eventData) return null;
    
    try {
        return {
            type: eventType,
            data: JSON.parse(eventData)
        };
    } catch (e) {
        console.error('Failed to parse SSE data:', eventData);
        return null;
    }
}

// Video Queue Management
async function playVideoQueue() {
    // If already playing, just return - the running loop will pick up new chunks
    if (isPlayingQueue) {
        console.log('✋ Already playing queue, new chunk will be picked up by running loop');
        return;
    }
    
    if (videoQueue.length === 0) {
        console.log('📭 Queue is empty, nothing to play');
        return;
    }
    
    isPlayingQueue = true;
    console.log('▶️ Starting video queue playback...');
    
    while (videoQueue.length > 0) {
        const chunk = videoQueue.shift();
        
        console.log(`\n🎬 Playing chunk ${chunk.index}:`);
        console.log(`   Text: "${chunk.text.substring(0, 60)}..."`);
        console.log(`   URL: ${chunk.url}`);
        console.log(`   Queue remaining: ${videoQueue.length}`);
        
        // CRITICAL: Reset video element completely before loading new source
        console.log('🔄 Resetting video element...');
        avatarVideo.pause();
        avatarVideo.removeAttribute('src');
        videoSource.removeAttribute('src');
        avatarVideo.load(); // Clear any pending loads
        
        // Small delay to ensure reset completes
        await new Promise(resolve => setTimeout(resolve, 50));
        
        // Now set new video source
        videoSource.src = chunk.url;
        console.log(`📺 Video source set to: ${chunk.url}`);
        
        // Show video, hide placeholder
        videoPlaceholder.style.display = 'none';
        avatarVideo.style.display = 'block';
        console.log('👁️ Video element shown');
        
        // Load the new video
        avatarVideo.load();
        console.log('🔄 Video load() called');
        
        // Wait for video to be ready
        try {
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    console.error(`⏱️ Timeout waiting for video to load after 30s`);
                    console.error(`   Current state: readyState=${avatarVideo.readyState}, networkState=${avatarVideo.networkState}`);
                    console.error(`   Video dimensions: ${avatarVideo.videoWidth}x${avatarVideo.videoHeight}`);
                    console.error(`   Buffered ranges: ${avatarVideo.buffered.length}`);
                    console.error(`   Current src: ${avatarVideo.currentSrc}`);
                    console.error(`   Error: ${avatarVideo.error ? avatarVideo.error.message : 'none'}`);
                    reject(new Error('Video load timeout after 30s'));
                }, 30000); // Increased to 30 seconds
                
                // Log progress more frequently
                const onProgress = () => {
                    const buffered = avatarVideo.buffered.length > 0 
                        ? avatarVideo.buffered.end(0) 
                        : 0;
                    console.log(`📊 Loading... readyState=${avatarVideo.readyState}, networkState=${avatarVideo.networkState}, buffered=${buffered.toFixed(1)}s`);
                };
                
                const onLoadStart = () => {
                    console.log(`🎬 Video load started`);
                };
                
                const onCanPlay = () => {
                    console.log(`✅ Can play (canplay event) - readyState=${avatarVideo.readyState}`);
                };
                
                const onStalled = () => {
                    console.warn(`⚠️ Video download stalled`);
                };
                
                const onSuspend = () => {
                    console.log(`⏸️ Video download suspended by browser`);
                };
                
                avatarVideo.addEventListener('progress', onProgress);
                avatarVideo.addEventListener('loadstart', onLoadStart);
                avatarVideo.addEventListener('canplay', onCanPlay);
                avatarVideo.addEventListener('stalled', onStalled);
                avatarVideo.addEventListener('suspend', onSuspend);
                
                const cleanup = () => {
                    clearTimeout(timeout);
                    avatarVideo.removeEventListener('progress', onProgress);
                    avatarVideo.removeEventListener('loadstart', onLoadStart);
                    avatarVideo.removeEventListener('canplay', onCanPlay);
                    avatarVideo.removeEventListener('stalled', onStalled);
                    avatarVideo.removeEventListener('suspend', onSuspend);
                };
                
                avatarVideo.onloadeddata = () => {
                    cleanup();
                    console.log(`✅ Video loaded successfully`);
                    console.log(`   Duration: ${avatarVideo.duration.toFixed(2)}s`);
                    console.log(`   Ready state: ${avatarVideo.readyState}`);
                    console.log(`   Network state: ${avatarVideo.networkState}`);
                    resolve();
                };
                
                avatarVideo.onerror = () => {
                    cleanup();
                    const error = avatarVideo.error;
                    let errorMsg = 'Unknown error';
                    if (error) {
                        const errorCodes = ['', 'MEDIA_ERR_ABORTED', 'MEDIA_ERR_NETWORK', 'MEDIA_ERR_DECODE', 'MEDIA_ERR_SRC_NOT_SUPPORTED'];
                        errorMsg = errorCodes[error.code] || `Error code ${error.code}`;
                    }
                    reject(new Error(`Video error: ${errorMsg}`));
                };
                
                // If we can play, that's good enough
                avatarVideo.oncanplay = () => {
                    if (avatarVideo.readyState >= 3) { // HAVE_FUTURE_DATA or better
                        cleanup();
                        console.log(`✅ Using canplay event (readyState=${avatarVideo.readyState})`);
                        resolve();
                    }
                };
            });
        } catch (err) {
            console.error(`❌ Video load failed:`, err.message);
            console.error(`   Skipping to next chunk...`);
            continue; // Skip to next chunk
        }
        
        // Play video
        if (autoPlayCheckbox.checked) {
            try {
                console.log('▶️ Calling video.play()...');
                const playPromise = avatarVideo.play();
                
                if (playPromise !== undefined) {
                    await playPromise;
                    console.log(`✅ Chunk ${chunk.index} is now playing`);
                } else {
                    console.log(`⚠️ Play returned undefined (old browser?)`);
                }
                
                // Wait for video to finish
                await new Promise((resolve) => {
                    avatarVideo.onended = () => {
                        console.log(`✅ Chunk ${chunk.index} finished playing`);
                        resolve();
                    };
                });
            } catch (err) {
                console.error('❌ Playback error:', err.name, err.message);
                if (err.name === 'NotAllowedError') {
                    console.error('   User interaction required for autoplay. Please click the video.');
                    updateStatus('Click video to play', 'error');
                }
                break;
            }
        } else {
            console.log('⏸️ Autoplay disabled, showing first chunk only');
            break;
        }
    }
    
    isPlayingQueue = false;
    console.log('🏁 Video queue playback complete\n');
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
