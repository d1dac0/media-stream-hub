document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const mediaGridContainer = document.getElementById('media-grid-container');
    const playerOverlay = document.getElementById('player-overlay');
    const videoPlayerEl = document.getElementById('video-player');
    const closePlayerBtn = document.getElementById('close-player');
    const logoutLink = document.getElementById('logout-link');
    const header = document.querySelector('header');

    // Player instance
    let player;

    // State variables
    let mediaFiles = [];
    let currentMediaIndex = -1;
    let currentFilter = 'all';
    let csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    // Centralized API calls
    const api = {
        async get(url) {
            const response = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-Token': csrfToken }
            });
            if (response.status === 401) {
                window.location.href = '/login';
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
                window.location.href = '/login';
                throw new Error('User not authenticated');
            }
            return response;
        }
    };

    // Initialize
    init();

    async function init() {
        await fetchMediaFiles();
        setupEventListeners();
        
        player = new Plyr(videoPlayerEl);
        window.player = player;
    }

    async function fetchMediaFiles() {
        try {
            const response = await api.get('/api/media');
            if (!response.ok) throw new Error('Failed to fetch media files');
            const data = await response.json();
            mediaFiles = data.files || [];
            renderMediaGrid();
        } catch (error) {
            console.error('Error fetching media files:', error);
            mediaGridContainer.innerHTML = '<p class="error">Could not load media. Please try again later.</p>';
        }
    }

    function setupEventListeners() {
        if (logoutLink) {
            logoutLink.addEventListener('click', (e) => {
                e.preventDefault();
                logout();
            });
        }
        
        if (closePlayerBtn) {
            closePlayerBtn.addEventListener('click', () => {
                player.pause();
                playerOverlay.style.display = 'none';
            });
        }
        
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                header.classList.add('scrolled');
            } else {
                header.classList.remove('scrolled');
            }
        });

        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelector('.filter-btn.active').classList.remove('active');
                btn.classList.add('active');
                currentFilter = btn.dataset.filter;
                applyFilter();
            });
        });
    }

    async function logout() {
        try {
            await api.post('/logout', {});
            window.location.href = '/login';
        } catch (error) {
            console.error('Logout failed:', error);
        }
    }

    function renderMediaGrid() {
        if (mediaFiles.length === 0) {
            mediaGridContainer.innerHTML = '<p>No media files found.</p>';
            return;
        }

        const html = mediaFiles.map((file, index) => {
            const { poster, title, year, type } = file.metadata;
            const isAudio = file.type === 'audio';
            const displayTitle = isAudio ? file.name.replace(/\.[^/.]+$/, "") : title;

            let posterHtml;
            if (poster) {
                posterHtml = `<img src="${poster}" alt="${escapeHtml(displayTitle)}" class="tile-poster">`;
            } else {
                const iconClass = isAudio ? 'fa-music' : 'fa-film';
                posterHtml = `
                    <div class="tile-poster-placeholder">
                        <i class="fas ${iconClass}"></i>
                    </div>
                `;
            }

            return `
                <div class="media-tile" data-index="${index}" data-media-type="${type}">
                    ${posterHtml}
                    <div class="tile-metadata">
                        <div class="tile-title">${escapeHtml(displayTitle)}</div>
                        <div class="tile-details">${year || ''} &bull; ${type}</div>
                    </div>
                </div>
            `;
        }).join('');

        mediaGridContainer.innerHTML = html;
        
        document.querySelectorAll('.media-tile').forEach(tile => {
            tile.addEventListener('click', () => {
                const index = parseInt(tile.dataset.index, 10);
                playMedia(index);
            });
        });
    }

    function applyFilter() {
        document.querySelectorAll('.media-tile').forEach(tile => {
            const mediaType = tile.dataset.mediaType;
            if (currentFilter === 'all' || mediaType === currentFilter) {
                tile.style.display = 'block';
            } else {
                tile.style.display = 'none';
            }
        });
    }

    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    function playMedia(index) {
        if (index < 0 || index >= mediaFiles.length) return;
        
        currentMediaIndex = index;
        const file = mediaFiles[index];
        
        player.source = {
            type: 'video',
            title: file.name,
            sources: [{
                src: `/media/${encodeURIComponent(file.path)}`,
                type: 'video/mp4'
            }],
        };

        playerOverlay.style.display = 'flex';
        player.play();
    }
});
