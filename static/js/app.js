document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const mediaList = document.getElementById('media-list');
    const videoPlayer = document.getElementById('video-player');
    const audioPlayer = document.getElementById('audio-player');
    const playerPlaceholder = document.getElementById('player-placeholder');
    const currentMediaTitle = document.getElementById('current-media-title');
    const playPauseBtn = document.getElementById('play-pause-btn');
    const previousBtn = document.getElementById('previous-btn');
    const nextBtn = document.getElementById('next-btn');
    const volumeSlider = document.getElementById('volume-slider');
    const searchInput = document.getElementById('search-input');
    const searchButton = document.getElementById('search-button');
    const filterButtons = document.querySelectorAll('.filter-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const settingsModal = document.getElementById('settings-modal');
    const closeModalBtn = document.querySelector('.close');
    const saveSettingsBtn = document.getElementById('save-settings');
    const mediaFolderInput = document.getElementById('media-folder');
    const logoutLink = document.getElementById('logout-link');

    // State variables
    let mediaFiles = [];
    let filteredMediaFiles = [];
    let currentMediaIndex = -1;
    let currentPlayer = null;
    let playbackState = {};
    let currentFilter = 'all';
    let searchQuery = '';
    let csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    // Security check - ensure we're not in an iframe to prevent clickjacking
    if (window.self !== window.top) {
        document.body.innerHTML = '<h1>For security reasons, this application cannot be displayed in a frame.</h1>';
        return;
    }

    // Initialize
    init();

    async function init() {
        await fetchMediaFiles();
        await fetchPlaybackState();
        setupEventListeners();
    }

    async function fetchMediaFiles() {
        try {
            const response = await fetch('/api/media', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRF-Token': csrfToken
                }
            });
            if (response.status === 401) {
                // Unauthorized, redirect to login
                window.location.href = '/login';
                return;
            }
            if (!response.ok) {
                throw new Error('Failed to fetch media files');
            }
            const data = await response.json();
            mediaFiles = data.files || [];
            filteredMediaFiles = [...mediaFiles];
            renderMediaList();
        } catch (error) {
            console.error('Error fetching media files:', error);
            showErrorNotification('Failed to load media files. Please try refreshing the page.');
        }
    }

    async function fetchPlaybackState() {
        try {
            const response = await fetch('/api/playback-state', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRF-Token': csrfToken
                }
            });
            if (!response.ok) {
                throw new Error('Failed to fetch playback state');
            }
            playbackState = await response.json();
        } catch (error) {
            console.error('Error fetching playback state:', error);
            // Non-critical error, don't show to user
            playbackState = {};
        }
    }

    function setupEventListeners() {
        // Media list click event
        mediaList.addEventListener('click', (e) => {
            const item = e.target.closest('.media-item');
            if (item) {
                const index = parseInt(item.dataset.index);
                if (!isNaN(index)) {
                    playMedia(index);
                }
            }
        });

        // Play/Pause button
        playPauseBtn.addEventListener('click', togglePlayPause);

        // Previous button
        previousBtn.addEventListener('click', playPrevious);

        // Next button
        nextBtn.addEventListener('click', playNext);

        // Volume slider
        volumeSlider.addEventListener('input', () => {
            const volume = volumeSlider.value / 100;
            if (videoPlayer) videoPlayer.volume = volume;
            if (audioPlayer) audioPlayer.volume = volume;
        });

        // Search functionality
        searchButton.addEventListener('click', performSearch);
        searchInput.addEventListener('keyup', (e) => {
            if (e.key === 'Enter') {
                performSearch();
            }
        });

        // Filter buttons
        filterButtons.forEach(button => {
            button.addEventListener('click', () => {
                filterButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                currentFilter = button.dataset.filter;
                applyFilters();
            });
        });

        // Settings modal
        settingsBtn.addEventListener('click', () => {
            mediaFolderInput.value = localStorage.getItem('mediaFolder') || '';
            settingsModal.style.display = 'block';
        });

        closeModalBtn.addEventListener('click', () => {
            settingsModal.style.display = 'none';
        });

        window.addEventListener('click', (e) => {
            if (e.target === settingsModal) {
                settingsModal.style.display = 'none';
            }
        });

        saveSettingsBtn.addEventListener('click', async () => {
            const mediaFolder = mediaFolderInput.value.trim();
            
            try {
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify({ mediaFolder })
                });
                
                if (!response.ok) {
                    throw new Error('Failed to save settings');
                }
                
                localStorage.setItem('mediaFolder', mediaFolder);
                settingsModal.style.display = 'none';
                
                // Refresh media files
                await fetchMediaFiles();
                
                showNotification('Settings saved successfully');
            } catch (error) {
                console.error('Error saving settings:', error);
                showErrorNotification('Failed to save settings. Please try again.');
            }
        });

        // Logout link
        logoutLink.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Create a form to submit the logout request with CSRF token
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/logout';
            
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token';
            csrfInput.value = csrfToken;
            
            form.appendChild(csrfInput);
            document.body.appendChild(form);
            form.submit();
        });

        // Video and audio player events
        videoPlayer.addEventListener('timeupdate', saveCurrentPlaybackPosition);
        audioPlayer.addEventListener('timeupdate', saveCurrentPlaybackPosition);
        
        // Prevent video player from being controlled by keyboard to avoid focus issues
        videoPlayer.addEventListener('keydown', (e) => {
            e.stopPropagation();
        });
        
        // Add event listeners for media ended
        videoPlayer.addEventListener('ended', playNext);
        audioPlayer.addEventListener('ended', playNext);
    }

    function renderMediaList() {
        if (filteredMediaFiles.length === 0) {
            mediaList.innerHTML = '<div class="no-media">No media files found</div>';
            return;
        }

        // Group files by folder
        const folderStructure = {};
        filteredMediaFiles.forEach((file, index) => {
            const pathParts = file.path.split('/');
            const fileName = pathParts.pop();
            const folderPath = pathParts.join('/');
            
            if (!folderStructure[folderPath]) {
                folderStructure[folderPath] = [];
            }
            folderStructure[folderPath].push({ ...file, index });
        });

        // Generate HTML for folders and files
        const html = Object.entries(folderStructure).map(([folderPath, files]) => {
            const folderName = folderPath || 'Root';
            const folderId = `folder-${btoa(folderPath).replace(/[^a-zA-Z0-9]/g, '')}`;
            
            const filesHtml = files.map(file => {
                const isActive = file.index === currentMediaIndex;
                return `
                    <div class="media-item ${isActive ? 'active' : ''}" data-index="${file.index}">
                        <div class="media-icon">${file.type === 'video' ? '<i class="fas fa-film"></i>' : '<i class="fas fa-music"></i>'}</div>
                        <div class="media-title">${escapeHtml(file.name)}</div>
                    </div>
                `;
            }).join('');

            return `
                <div class="folder" id="${folderId}">
                    <div class="folder-header" onclick="document.getElementById('${folderId}').classList.toggle('open')">
                        <i class="fas fa-folder"></i>
                        <i class="fas fa-folder-open"></i>
                        <div class="folder-name">${escapeHtml(folderName)}</div>
                    </div>
                    <div class="folder-content">
                        ${filesHtml}
                    </div>
                </div>
            `;
        }).join('');

        mediaList.innerHTML = html;

        // Open the folder containing the currently playing media
        if (currentMediaIndex !== -1) {
            const currentFile = filteredMediaFiles[currentMediaIndex];
            if (currentFile) {
                const pathParts = currentFile.path.split('/');
                pathParts.pop();
                const folderPath = pathParts.join('/');
                const folderId = `folder-${btoa(folderPath).replace(/[^a-zA-Z0-9]/g, '')}`;
                const folderElement = document.getElementById(folderId);
                if (folderElement) {
                    folderElement.classList.add('open');
                }
            }
        }
    }

    // Helper function to escape HTML to prevent XSS
    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function playMedia(index) {
        if (index < 0 || index >= filteredMediaFiles.length) return;
        
        // Save current position before switching
        if (currentMediaIndex !== -1 && currentPlayer) {
            saveCurrentPlaybackPosition(true);
        }
        
        currentMediaIndex = index;
        const file = filteredMediaFiles[index];
        
        // Hide both players and show placeholder initially
        videoPlayer.style.display = 'none';
        audioPlayer.style.display = 'none';
        playerPlaceholder.style.display = 'flex';
        
        // Set the media title
        currentMediaTitle.textContent = file.name;
        
        // Determine which player to use based on file type
        if (file.type === 'video') {
            currentPlayer = videoPlayer;
            videoPlayer.style.display = 'block';
            playerPlaceholder.style.display = 'none';
            
            // Set video source with cache-busting parameter for security
            const timestamp = new Date().getTime();
            videoPlayer.src = `/media/${encodeURIComponent(file.path)}?t=${timestamp}`;
            audioPlayer.src = '';
        } else {
            currentPlayer = audioPlayer;
            audioPlayer.style.display = 'block';
            
            // Set audio source with cache-busting parameter for security
            const timestamp = new Date().getTime();
            audioPlayer.src = `/media/${encodeURIComponent(file.path)}?t=${timestamp}`;
            videoPlayer.src = '';
        }
        
        // Set volume
        currentPlayer.volume = volumeSlider.value / 100;
        
        // Check if we have a saved position for this file
        if (playbackState[file.path]) {
            currentPlayer.currentTime = playbackState[file.path];
        }
        
        // Play the media
        const playPromise = currentPlayer.play();
        
        if (playPromise !== undefined) {
            playPromise.catch(error => {
                console.error('Error playing media:', error);
                // Auto-play was prevented, show play button
                playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
            });
        }
        
        // Update play/pause button
        playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
        
        // Update the active item in the list
        renderMediaList();
    }

    function togglePlayPause() {
        if (!currentPlayer) return;
        
        if (currentPlayer.paused) {
            currentPlayer.play();
            playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
        } else {
            currentPlayer.pause();
            playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
        }
    }

    function playPrevious() {
        if (currentMediaIndex > 0) {
            playMedia(currentMediaIndex - 1);
        }
    }

    function playNext() {
        if (currentMediaIndex < filteredMediaFiles.length - 1) {
            playMedia(currentMediaIndex + 1);
        }
    }

    function performSearch() {
        searchQuery = searchInput.value.trim().toLowerCase();
        applyFilters();
    }

    function applyFilters() {
        // Start with all media files
        let filtered = [...mediaFiles];
        
        // Apply search filter if there's a search query
        if (searchQuery) {
            filtered = filtered.filter(file => 
                file.name.toLowerCase().includes(searchQuery)
            );
        }
        
        // Apply type filter
        if (currentFilter !== 'all') {
            filtered = filtered.filter(file => file.type === currentFilter);
        }
        
        // Update filtered media files
        filteredMediaFiles = filtered;
        
        // Render the updated list
        renderMediaList();
        
        // If the current media is no longer in the filtered list, clear the player
        if (currentMediaIndex !== -1) {
            const currentPath = filteredMediaFiles[currentMediaIndex]?.path;
            const stillExists = filteredMediaFiles.some(file => file.path === currentPath);
            
            if (!stillExists) {
                // Clear the player
                currentMediaIndex = -1;
                currentPlayer = null;
                videoPlayer.style.display = 'none';
                audioPlayer.style.display = 'none';
                playerPlaceholder.style.display = 'flex';
                currentMediaTitle.textContent = 'No media selected';
                videoPlayer.src = '';
                audioPlayer.src = '';
            }
        }
    }

    function saveCurrentPlaybackPosition(forceSave = false) {
        if (!currentPlayer || currentMediaIndex === -1) return;
        
        const file = filteredMediaFiles[currentMediaIndex];
        if (!file) return;
        
        // Only save if we've watched more than 5 seconds or if forceSave is true
        if (forceSave || currentPlayer.currentTime > 5) {
            playbackState[file.path] = currentPlayer.currentTime;
            
            // Debounce the API call to prevent too many requests
            clearTimeout(window.savePlaybackTimeout);
            window.savePlaybackTimeout = setTimeout(() => {
                fetch('/api/playback-state', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify({
                        path: file.path,
                        position: currentPlayer.currentTime
                    })
                }).catch(error => {
                    console.error('Error saving playback position:', error);
                });
            }, 1000);
        }
    }
    
    // Helper functions for notifications
    function showNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'notification';
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.classList.add('show');
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => {
                    document.body.removeChild(notification);
                }, 300);
            }, 3000);
        }, 10);
    }
    
    function showErrorNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'notification error';
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.classList.add('show');
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => {
                    document.body.removeChild(notification);
                }, 300);
            }, 3000);
        }, 10);
    }
});
