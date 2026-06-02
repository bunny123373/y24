// Dynamic Navigation & Tab Switching
function switchTab(tabId) {
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
    
    document.getElementById(`nav-btn-${tabId}`).classList.add('active');
    document.getElementById(`panel-${tabId}`).classList.add('active');

    if (tabId === 'history') {
        loadHistory();
    } else if (tabId === 'settings') {
        loadSettings();
    }
}

// Toggle quality options in selectors
function toggleQualityOptions() {
    const type = document.getElementById('media-type').value;
    const videoGroup = document.getElementById('video-quality-group');
    const audioGroup = document.getElementById('audio-quality-group');
    
    if (type === 'audio') {
        videoGroup.classList.add('hidden');
        audioGroup.classList.remove('hidden');
    } else {
        videoGroup.classList.remove('hidden');
        audioGroup.classList.add('hidden');
    }
}

// Show Toast Alert Notification
function showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    const icon = document.getElementById('toast-icon');
    const msgSpan = document.getElementById('toast-message');
    
    msgSpan.innerText = message;
    
    if (isError) {
        toast.classList.add('error');
        icon.className = 'fa-solid fa-circle-xmark';
    } else {
        toast.classList.remove('error');
        icon.className = 'fa-solid fa-circle-check';
    }
    
    toast.classList.remove('hidden');
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3500);
}

// Control styles and iframe loading for browser fallback downloader
function activateFallbackWidget(url) {
    const fallbackContainer = document.getElementById('fallback-downloader-container');
    const fallbackIframe = document.getElementById('fallback-iframe');
    const downloadForm = document.getElementById('download-form');
    
    // Load iframe target
    fallbackIframe.src = `https://clickapi.net/api/widgetplus?url=${encodeURIComponent(url)}`;
    
    // Display fallback panel
    fallbackContainer.classList.remove('hidden');
    
    // Hide standard quality controls and download trigger button
    downloadForm.querySelector('.form-row').classList.add('hidden');
    document.getElementById('btn-download').classList.add('hidden');
    
    // Update toggle button text/state
    const manualBtn = document.getElementById('btn-manual-fallback');
    if (manualBtn) {
        manualBtn.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Close Browser Downloader`;
        manualBtn.classList.add('active');
    }
}

function deactivateFallbackWidget() {
    const fallbackContainer = document.getElementById('fallback-downloader-container');
    const fallbackIframe = document.getElementById('fallback-iframe');
    const downloadForm = document.getElementById('download-form');
    
    fallbackContainer.classList.add('hidden');
    fallbackIframe.src = '';
    
    downloadForm.querySelector('.form-row').classList.remove('hidden');
    document.getElementById('btn-download').classList.remove('hidden');
    
    const manualBtn = document.getElementById('btn-manual-fallback');
    if (manualBtn) {
        manualBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Use Alternative Browser Downloader`;
        manualBtn.classList.remove('active');
    }
}

function handleManualFallbackToggle() {
    const urlInput = document.getElementById('media-url');
    const url = urlInput.value.trim();
    const manualBtn = document.getElementById('btn-manual-fallback');
    
    if (!url) {
        showToast("Please paste a URL link first.", true);
        return;
    }
    
    if (manualBtn && manualBtn.classList.contains('active')) {
        deactivateFallbackWidget();
    } else {
        activateFallbackWidget(url);
    }
}

// Triggers background download API call
function handleDownload(event) {
    event.preventDefault();
    
    const urlInput = document.getElementById('media-url');
    const url = urlInput.value.trim();
    const type = document.getElementById('media-type').value;
    
    let quality = 'best';
    if (type === 'audio') {
        quality = document.getElementById('audio-quality').value;
    } else {
        quality = document.getElementById('video-quality').value;
    }
    
    if (!url) return;
    
    fetch('/api/download', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url, type, quality })
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(errData => {
                throw new Error(errData.detail || "Failed to start download");
            });
        }
        return res.json();
    })
    .then(data => {
        if (data.success) {
            showToast("Download job added to queue!");
            urlInput.value = ''; // Reset input
            document.getElementById('video-preview-card').classList.add('hidden');
            lastFetchedUrl = "";
        }
    })
    .catch(err => {
        console.error("Error starting download:", err);
        showToast(err.message || "Server communication error.", true);
    });
}

// Keep track of finished downloads that were auto-triggered for browser saving
const autoDownloadedIds = new Set();

// Triggers browser download prompt programmatically
function triggerBrowserDownload(filename) {
    const link = document.createElement('a');
    link.href = `/api/downloads/${encodeURIComponent(filename)}`;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast(`Saved "${filename}" to your local downloads folder!`);
    
    // Auto-reload history listing if history tab is currently open
    const historyBtn = document.getElementById('nav-btn-history');
    if (historyBtn && historyBtn.classList.contains('active')) {
        loadHistory();
    }
}

// Setup EventSource listening for progress events
function setupProgressEventSource() {
    const eventSource = new EventSource('/api/progress');
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            const downloads = data.downloads || [];
            
            // Scan downloads for completed ones to auto-download to browser
            downloads.forEach(dl => {
                if (dl.status === 'finished' && dl.filename && !autoDownloadedIds.has(dl.id)) {
                    autoDownloadedIds.add(dl.id);
                    triggerBrowserDownload(dl.filename);
                }
            });
            
            const container = document.getElementById('downloads-container');
            const activeCount = document.getElementById('active-count');
            const emptyState = document.getElementById('empty-active-state');
            
            const activeJobs = downloads.filter(dl => 
                dl.status === 'downloading' || dl.status === 'pending' || dl.status === 'processing'
            );
            
            activeCount.innerText = activeJobs.length;
            
            if (downloads.length === 0) {
                container.innerHTML = '';
                emptyState.classList.remove('hidden');
                return;
            }
            
            emptyState.classList.add('hidden');
            let htmlContent = '';
            
            downloads.forEach(dl => {
                const isFailed = dl.status === 'failed';
                const dlIcon = dl.type === 'audio' ? 'fa-music' : 'fa-film';
                
                htmlContent += `
                    <div class="download-item glass">
                        <div class="dl-details">
                            <span class="dl-title" title="${dl.title}">
                                <i class="fa-solid ${dlIcon}" style="margin-right: 8px;"></i> ${dl.title}
                            </span>
                            <span class="dl-status-tag ${dl.status}">${dl.status}</span>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-fill" style="width: ${dl.progress}%"></div>
                        </div>
                        <div class="dl-status-row">
                            <div class="dl-meta">
                                <span><i class="fa-solid fa-gauge-high"></i> ${dl.speed}</span>
                                <span><i class="fa-solid fa-hourglass-half"></i> ${dl.eta}</span>
                            </div>
                            <div class="dl-percentage">${dl.progress}%</div>
                        </div>
                        ${isFailed ? `<div class="dl-error-msg" style="color: #ef476f; font-size: 11px; margin-top: 6px;">Error: ${dl.error}</div>` : ''}
                    </div>
                `;
            });
            
            container.innerHTML = htmlContent;
        } catch (e) {
            console.error("Error parsing SSE:", e);
        }
    };
    
    eventSource.onerror = function(err) {
        console.error("EventSource connectivity error:", err);
    };
}

// Fetch Completed files listing
function loadHistory() {
    const container = document.getElementById('history-container');
    const emptyState = document.getElementById('empty-history-state');
    
    fetch('/api/history')
    .then(res => res.json())
    .then(data => {
        const history = data.history || [];
        container.innerHTML = '';
        
        if (history.length === 0) {
            emptyState.classList.remove('hidden');
            return;
        }
        
        emptyState.classList.add('hidden');
        
        history.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.className = 'history-item';
            const fileIcon = item.type === 'audio' ? 'fa-file-audio audio-icon' : 'fa-file-video video-icon';
            
            itemElement.innerHTML = `
                <div class="history-name" title="${item.name}">
                    <i class="fa-solid ${fileIcon}"></i>
                    <a href="/api/downloads/${encodeURIComponent(item.name)}" download="${item.name}" class="history-link">${item.name}</a>
                </div>
                <div class="history-size">${item.size}</div>
                <div class="history-date">${item.time}</div>
            `;
            container.appendChild(itemElement);
        });
    })
    .catch(err => {
        console.error("Error loading files history:", err);
    });
}

// Load configurations settings panel values
function loadSettings() {
    fetch('/api/config')
    .then(res => res.json())
    .then(data => {
        const cfg = data.config || {};
        
        document.getElementById('settings-download-dir').value = cfg.download_dir || 'downloads';
        document.getElementById('settings-video-quality').value = cfg.video_quality || 'best';
        document.getElementById('settings-audio-format').value = cfg.audio_format || 'mp3';
        
        document.getElementById('settings-embed-metadata').checked = !!cfg.embed_metadata;
        document.getElementById('settings-embed-thumbnail').checked = !!cfg.embed_thumbnail;
        document.getElementById('settings-download-archive').checked = !!cfg.download_archive;
    })
    .catch(err => {
        console.error("Error loading configs:", err);
        showToast("Error loading config fields.", true);
    });
}

// Updates configurations panel values
function saveSettings(event) {
    event.preventDefault();
    
    const download_dir = document.getElementById('settings-download-dir').value.trim();
    const video_quality = document.getElementById('settings-video-quality').value;
    const audio_format = document.getElementById('settings-audio-format').value;
    
    const embed_metadata = document.getElementById('settings-embed-metadata').checked;
    const embed_thumbnail = document.getElementById('settings-embed-thumbnail').checked;
    const download_archive = document.getElementById('settings-download-archive').checked;
    
    fetch('/api/config', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            download_dir,
            video_quality,
            audio_format,
            embed_metadata,
            embed_thumbnail,
            download_archive
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast("Settings saved successfully!");
        } else {
            showToast("Failed to save settings.", true);
        }
    })
    .catch(err => {
        console.error("Error saving config:", err);
        showToast("Failed to communicate settings.", true);
    });
}

// Helper to format video duration (seconds to MM:SS or HH:MM:SS)
function formatDuration(seconds) {
    if (!seconds) return "00:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) {
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// Helper to format view counts
function formatViews(views) {
    if (views === undefined || views === null) return "N/A views";
    if (views >= 1000000) {
        return `${(views / 1000000).toFixed(1)}M views`;
    }
    if (views >= 1000) {
        return `${(views / 1000).toFixed(1)}K views`;
    }
    return `${views} views`;
}

// Debounce timer for URL input fetching
let urlInputTimer = null;
let lastFetchedUrl = "";

function handleUrlInput() {
    const urlInput = document.getElementById('media-url');
    const url = urlInput.value.trim();
    const previewCard = document.getElementById('video-preview-card');
    const loadingSpinner = document.getElementById('preview-loading-spinner');
    const contentArea = document.getElementById('preview-content-area');
    
    if (urlInputTimer) clearTimeout(urlInputTimer);
    
    if (!url) {
        previewCard.classList.add('hidden');
        deactivateFallbackWidget();
        lastFetchedUrl = "";
        return;
    }
    
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        previewCard.classList.add('hidden');
        return;
    }
    
    if (url === lastFetchedUrl) {
        return;
    }
    
    urlInputTimer = setTimeout(() => {
        lastFetchedUrl = url;
        
        deactivateFallbackWidget();
        
        previewCard.classList.remove('hidden');
        loadingSpinner.classList.remove('hidden');
        contentArea.classList.add('hidden');
        
        fetch(`/api/info?url=${encodeURIComponent(url)}`)
        .then(res => {
            if (!res.ok) throw new Error("Metadata request failed");
            return res.json();
        })
        .then(data => {
            document.getElementById('preview-title').innerText = data.title || "Unknown Title";
            document.getElementById('preview-channel').innerHTML = `<i class="fa-solid fa-user"></i> ${data.uploader || "Unknown Channel"}`;
            
            const thumbUrl = data.thumbnail ? `/api/thumbnail?url=${encodeURIComponent(data.thumbnail)}` : "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?auto=format&fit=crop&w=300&q=80";
            document.getElementById('preview-thumbnail').src = thumbUrl;
            
            if (data.is_playlist) {
                document.getElementById('preview-duration').innerHTML = `<i class="fa-solid fa-list-ul"></i> Playlist`;
                document.getElementById('preview-views').innerHTML = `<i class="fa-solid fa-video"></i> ${data.entries_count} items`;
            } else {
                document.getElementById('preview-duration').innerHTML = `<i class="fa-solid fa-clock"></i> ${formatDuration(data.duration)}`;
                document.getElementById('preview-views').innerHTML = `<i class="fa-solid fa-eye"></i> ${formatViews(data.view_count)}`;
            }
            
            loadingSpinner.classList.add('hidden');
            contentArea.classList.remove('hidden');
            
            if (data.is_fallback) {
                activateFallbackWidget(url);
            }
        })
        .catch(err => {
            console.error("Error loading preview:", err);
            previewCard.classList.add('hidden');
            lastFetchedUrl = "";
        });
    }, 800);
}

// Attach Event Listeners on DOM load
window.addEventListener('DOMContentLoaded', () => {
    setupProgressEventSource();
    
    // Bind Tab Switching Buttons
    document.getElementById('nav-btn-download').addEventListener('click', () => switchTab('download'));
    document.getElementById('nav-btn-history').addEventListener('click', () => switchTab('history'));
    document.getElementById('nav-btn-settings').addEventListener('click', () => switchTab('settings'));
    
    // Bind Media Type Selector Change
    document.getElementById('media-type').addEventListener('change', toggleQualityOptions);
    
    // Bind Form Submissions
    document.getElementById('download-form').addEventListener('submit', handleDownload);
    document.getElementById('settings-form').addEventListener('submit', saveSettings);
    
    // Bind Manual Fallback Button
    const manualBtn = document.getElementById('btn-manual-fallback');
    if (manualBtn) {
        manualBtn.addEventListener('click', handleManualFallbackToggle);
    }
    
    // Bind URL input preview listeners
    const urlInput = document.getElementById('media-url');
    if (urlInput) {
        urlInput.addEventListener('input', handleUrlInput);
        urlInput.addEventListener('paste', () => setTimeout(handleUrlInput, 100));
    }
});
