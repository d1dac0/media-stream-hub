document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const mediaList = document.getElementById('media-list');
    const videoPlayerEl = document.getElementById('video-player');
    const audioPlayerEl = document.getElementById('audio-player');
    const playerPlaceholder = document.getElementById('player-placeholder');
    const currentMediaTitle = document.getElementById('current-media-title');
    const playPauseBtn = document.getElementById('play-pause-btn');
    const previousBtn = document.getElementById('previous-btn');
    const nextBtn = document.getElementById('next-btn');
    const searchInput = document.getElementById('search-input');
    const searchButton = document.getElementById('search-button');
    const filterButtons = document.querySelectorAll('.filter-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const settingsModal = document.getElementById('settings-modal');
    const closeModalBtn = document.querySelector('.close');
    const saveSettingsBtn = document.getElementById('save-settings');
    const mediaFolderInput = document.getElementById('media-folder');
    const logoutLink = document.getElementById('logout-link');

    // Player instance
    let player;

    // State variables
    let mediaFiles = [];
    let filteredMediaFiles = [];
    let currentMediaIndex = -1;
    let currentPlayer = null;
    let playbackState = {};
    let currentFilter = 'all';
    let searchQuery = '';
    let csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    // Centralized API calls
    const api = {
        async get(url) {
            const response = await fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRF-Token': csrfToken
                }
            });
            if (response.status === 401) {
                showLoginModal();
                throw new Error('User not authenticated');
            }
            return response;
        },
        async post(url, data) {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify(data)
            });
            if (response.status === 401) {
                showLoginModal();
                throw new Error('User not authenticated');
            }
            return response;
        }
    };

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
        
        // Initialize Plyr player
        player = new Plyr('#video-player', {
            // Options can be added here
        });

        // Expose player for debugging
        window.player = player;

        // Periodically check session
        setInterval(checkSession, 5 * 60 * 1000); // Check every 5 minutes
    }

    async function fetchMediaFiles() {
        try {
            const response = await api.get('/api/media');
            if (!response.ok) {
                throw new Error('Failed to fetch media files');
            }
            const data = await response.json();
            mediaFiles = data.files || [];
            filteredMediaFiles = [...mediaFiles];
            renderMediaList();
        } catch (error) {
            console.error('Error fetching media files:', error);
            if (error.message !== 'User not authenticated') {
                showErrorNotification('Failed to load media files. Please try refreshing the page.');
            }
        }
    }

    async function fetchPlaybackState() {
        try {
            const response = await api.get('/api/playback-state');
            if (!response.ok) {
                throw new Error('Failed to fetch playback state');
            }
            playbackState = await response.json();
        } catch (error) {
            console.error('Error fetching playback state:', error);
            playbackState = {};
        }
    }

    function setupEventListeners() {
        // Media list click event
        if (mediaList) {
            mediaList.addEventListener('click', (e) => {
                const item = e.target.closest('.media-item');
                if (item) {
                    const index = parseInt(item.dataset.index, 10);
                    if (!isNaN(index)) {
                        playMedia(index);
                    }
                }
            });
        }

        // Play/Pause button
        if(playPauseBtn) {
            playPauseBtn.addEventListener('click', togglePlayPause);
        }

        // Previous button
        if (previousBtn) {
            previousBtn.addEventListener('click', playPrevious);
        }

        // Next button
        if (nextBtn) {
            nextBtn.addEventListener('click', playNext);
        }

        // Search functionality
        if (searchButton) {
            searchButton.addEventListener('click', performSearch);
        }
        if (searchInput) {
            searchInput.addEventListener('keyup', (e) => {
                if (e.key === 'Enter') {
                    performSearch();
                }
            });
        }

        // Filter buttons
        if (filterButtons) {
            filterButtons.forEach(button => {
                button.addEventListener('click', () => {
                    filterButtons.forEach(btn => btn.classList.remove('active'));
                    button.classList.add('active');
                    currentFilter = button.dataset.filter;
                    applyFilters();
                });
            });
        }

        // Settings modal
        if (settingsBtn) {
            settingsBtn.addEventListener('click', () => {
                settingsModal.style.display = 'block';
            });
        }

        if (closeModalBtn) {
            closeModalBtn.addEventListener('click', () => {
                settingsModal.style.display = 'none';
            });
        }

        window.addEventListener('click', (e) => {
            if (e.target === settingsModal) {
                settingsModal.style.display = 'none';
            }
        });

        if (saveSettingsBtn) {
            saveSettingsBtn.addEventListener('click', async () => {
                const mediaFolder = mediaFolderInput.value.trim();
                
                try {
                    const response = await api.post('/api/settings', { media_folder: mediaFolder });
                    
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.error || 'Failed to save settings');
                    }
                    
                    settingsModal.style.display = 'none';
                    await fetchMediaFiles();
                    showNotification('Settings saved successfully');
                } catch (error) {
                    console.error('Error saving settings:', error);
                    showErrorNotification(error.message || 'Failed to save settings. Please try again.');
                }
            });
        }

        // Logout link
        if (logoutLink) {
            logoutLink.addEventListener('click', (e) => {
                e.preventDefault();
                logout();
            });
        }

        // Player events
        if (player) {
            player.on('timeupdate', saveCurrentPlaybackPosition);
            player.on('ended', playNext);
        }
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
                    <div class="folder-header">
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

        // Add event listeners to folder headers
        document.querySelectorAll('.folder-header').forEach(header => {
            header.addEventListener('click', () => {
                header.parentElement.classList.toggle('open');
            });
        });

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
        if (index < 0 || index >= filteredMediaFiles.length) {
            console.error("Invalid media index requested:", index);
            return;
        }

        // Save current position before switching
        if (currentMediaIndex !== -1 && player) {
            saveCurrentPlaybackPosition(true);
        }
        
        currentMediaIndex = index;
        const file = filteredMediaFiles[index];
        
        // Hide placeholder and show player
        playerPlaceholder.style.display = 'none';
        
        // Set the media title
        currentMediaTitle.textContent = file.name;
        
        // Update player source
        player.source = {
            type: file.type,
            title: file.name,
            sources: [{
                src: `/media/${encodeURIComponent(file.path)}`,
                type: file.type === 'video' ? 'video/mp4' : 'audio/mp3',
            }],
        };
        
        // Check if we have a saved position for this file
        if (playbackState[file.path]) {
            player.once('canplay', () => {
                player.currentTime = playbackState[file.path].position || 0;
            });
        }
        
        // Play the media
        player.play();
        
        // Update the active item in the list
        renderMediaList();

        // Update control buttons state
        updateControlButtons();
    }

    function togglePlayPause() {
        if (player) {
            player.togglePlay();
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
                if (player) player.stop();
                playerPlaceholder.style.display = 'flex';
                currentMediaTitle.textContent = 'No media selected';
            }
        }
    }

    function saveCurrentPlaybackPosition(forceSave = false) {
        if (!player || currentMediaIndex === -1) return;
        
        const file = filteredMediaFiles[currentMediaIndex];
        if (!file) return;
        
        // Only save if we've watched more than 5 seconds or if forceSave is true
        if (forceSave || player.currentTime > 5) {
            const currentPosition = player.currentTime;
            
            // Update local state immediately
            if (!playbackState[file.path]) playbackState[file.path] = {};
            playbackState[file.path].position = currentPosition;

            // Debounce the API call to prevent too many requests
            clearTimeout(window.savePlaybackTimeout);
            window.savePlaybackTimeout = setTimeout(async () => {
                try {
                    await api.post('/api/playback-state', {
                        path: file.path,
                        position: currentPosition,
                        volume: player.volume
                    });
                } catch (error) {
                    console.error('Error saving playback position:', error);
                }
            }, 1000);
        }
    }
    
    // Session management functions
    async function checkSession() {
        try {
            const response = await api.get('/api/media'); // A simple authenticated endpoint
            if (!response.ok) {
                showLoginModal();
            }
        } catch (error) {
            // Error will be thrown if not authenticated, modal already shown
        }
    }

    function showLoginModal() {
        // Simple alert for now, can be replaced with a proper modal
        alert("Your session has expired. Please log in again to continue.");
        window.location.href = '/login';
    }

    function updateControlButtons() {
        if (playPauseBtn) {
            playPauseBtn.disabled = currentMediaIndex === -1;
        }
        if (previousBtn) {
            previousBtn.disabled = currentMediaIndex <= 0;
        }
        if (nextBtn) {
            nextBtn.disabled = currentMediaIndex >= filteredMediaFiles.length - 1;
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
