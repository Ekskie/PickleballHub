/**
 * tutorials.js
 * Universal, responsive tutorials controller for PickleballHub.
 * Features:
 *  - Dual playback: YouTube embeds & direct HTML5 uploaded video files
 *  - Dual publishing: YouTube links & drag-and-drop video file uploads
 *  - Real-time upload progress bar
 *  - Cross-role permissions (superadmin, adminstaff, clubadmin, owner, facilitystaff, player)
 *  - Instant search, multi-faceted filtering (level & source type), and sorting
 *  - Real-time database sync via Supabase channels and resilient REST fallback
 */

function initTutorials() {
    /* ── Container & Config ────────────────────────────────────────────── */
    const container = document.getElementById('tutorialsContainer');
    if (!container) return;

    const canManage      = container.dataset.canManage === 'true';
    const currentUserId  = container.dataset.userId || (typeof window.currentUserId !== 'undefined' ? window.currentUserId : '');
    const currentUserRole= (container.dataset.userRole || '').toLowerCase();
    const isGlobalAdmin  = ['superadmin', 'adminstaff'].includes(currentUserRole);

    /* ── DOM Elements ─────────────────────────────────────────────────── */
    const grid            = document.getElementById('tutorialsGrid');
    const searchInput     = document.getElementById('tutorialsSearch');
    const searchClearBtn  = document.getElementById('searchClearBtn');
    const levelPillsWrap  = document.getElementById('levelFilterPills');
    const sourcePillsWrap = document.getElementById('sourceFilterPills');
    const sortFilter      = document.getElementById('sortFilter');
    const countBadge      = document.getElementById('tutorialsCount');

    // Quick Stats Elements
    const statTotal       = document.getElementById('statTotalCount');
    const statBeginner    = document.getElementById('statBeginnerCount');
    const statInterm      = document.getElementById('statIntermediateCount');
    const statAdvanced    = document.getElementById('statAdvancedCount');
    const statUpload      = document.getElementById('statUploadCount');

    // Watch Modal Elements
    const watchModal      = document.getElementById('watchModal');
    const watchTitle      = document.getElementById('watchTitle');
    const watchBadges     = document.getElementById('watchBadges');
    const watchFrame      = document.getElementById('watchFrame');
    const watchVideoPlayer= document.getElementById('watchVideoPlayer');
    const watchDesc       = document.getElementById('watchDesc');
    const watchUploader   = document.getElementById('watchUploader');
    const watchExternalBtn= document.getElementById('watchExternalBtn');
    const watchShareBtn   = document.getElementById('watchShareBtn');
    const closeWatchBtn   = document.getElementById('closeWatch');

    // Add Modal Elements (managers only)
    const addBtn          = document.getElementById('addTutorialBtn');
    const addModal        = document.getElementById('addTutorialModal');
    const addForm         = document.getElementById('addTutorialForm');
    const closeAddBtn     = document.getElementById('closeTutorialModal');
    const closeAddAltBtn  = document.getElementById('closeTutorialModalAlt');
    const submitAddBtn    = document.getElementById('submitTutorialBtn');

    // Source switchers (Add Modal)
    const tabAddYoutube   = document.getElementById('tabAddYoutube');
    const tabAddUpload    = document.getElementById('tabAddUpload');
    const groupAddYoutube = document.getElementById('groupAddYoutube');
    const groupAddUpload  = document.getElementById('groupAddUpload');

    // YouTube Inputs & Preview
    const tUrlInput       = document.getElementById('tUrl');
    const ytLivePreview   = document.getElementById('ytLivePreview');
    const ytPreviewImg    = document.getElementById('ytPreviewImg');

    // Video File Upload Inputs & Dropzone
    const videoDropZone   = document.getElementById('videoDropZone');
    const tVideoFileInput = document.getElementById('tVideoFile');
    const tThumbFileInput = document.getElementById('tThumbFile');
    const selectedFileCard= document.getElementById('selectedFileCard');
    const selectedFileName= document.getElementById('selectedFileName');
    const selectedFileSize= document.getElementById('selectedFileSize');
    const removeVideoBtn  = document.getElementById('removeVideoFileBtn');
    const videoPreviewWrap= document.getElementById('videoPreviewWrap');
    const videoUploadPreview = document.getElementById('videoUploadPreview');

    // Progress Bar
    const progressWrap    = document.getElementById('uploadProgressWrap');
    const progressBar     = document.getElementById('uploadProgressBar');
    const progressLabel   = document.getElementById('uploadProgressLabel');
    const progressPercent = document.getElementById('uploadProgressPercent');

    // Common Inputs (Add Modal)
    const tTitleInput     = document.getElementById('tTitle');
    const tLevelInput     = document.getElementById('tLevel');
    const tDurationInput  = document.getElementById('tDuration');
    const tDescInput      = document.getElementById('tDesc');

    // Edit Modal Elements
    const editModal       = document.getElementById('editTutorialModal');
    const editForm        = document.getElementById('editTutorialForm');
    const closeEditBtn    = document.getElementById('closeEditTutorialModal');
    const closeEditAltBtn = document.getElementById('closeEditTutorialModalAlt');
    const submitEditBtn   = document.getElementById('submitEditTutorialBtn');

    const editIdInput     = document.getElementById('editTId');
    const editCurTypeInput= document.getElementById('editTCurrentType');
    const editExVidUrl    = document.getElementById('editTExistingVideoUrl');
    const editExThumbUrl  = document.getElementById('editTExistingThumbUrl');
    const tabEditYoutube  = document.getElementById('tabEditYoutube');
    const tabEditUpload   = document.getElementById('tabEditUpload');
    const groupEditYoutube= document.getElementById('groupEditYoutube');
    const groupEditUpload = document.getElementById('groupEditUpload');
    const editUrlInput    = document.getElementById('editTUrl');
    const editYtPreview   = document.getElementById('editYtLivePreview');
    const editYtPreviewImg= document.getElementById('editYtPreviewImg');
    const editVideoDropZone = document.getElementById('editVideoDropZone');
    const editVideoFileInput= document.getElementById('editTVideoFile');
    const editThumbFileInput= document.getElementById('editTThumbFile');
    const editSelectedFileCard = document.getElementById('editSelectedFileCard');
    const editSelectedFileName = document.getElementById('editSelectedFileName');
    const editSelectedFileSize = document.getElementById('editSelectedFileSize');
    const editRemoveVideoBtn   = document.getElementById('editRemoveVideoFileBtn');
    const editExistingNotice   = document.getElementById('editExistingVideoNotice');
    const editProgressWrap     = document.getElementById('editUploadProgressWrap');
    const editProgressBar      = document.getElementById('editUploadProgressBar');
    const editProgressLabel    = document.getElementById('editUploadProgressLabel');
    const editProgressPercent  = document.getElementById('editUploadProgressPercent');
    const editTitleInput  = document.getElementById('editTTitle');
    const editLevelInput  = document.getElementById('editTLevel');
    const editDurationInput= document.getElementById('editTDuration');
    const editDescInput   = document.getElementById('editTDesc');

    // Teleport modals to document.body to break out of .main-wrapper stacking context and render in front of sidebar/topbar
    [watchModal, addModal, editModal].forEach(modalEl => {
        if (modalEl && modalEl.parentElement !== document.body) {
            document.body.appendChild(modalEl);
        }
    });

    /* ── State ─────────────────────────────────────────────────────────── */
    let allTutorials     = [];
    let searchQ          = '';
    let filterLevel      = 'all';
    let filterSourceType = 'all';
    let currentSort      = 'newest';

    let addSourceType    = 'youtube'; // 'youtube' | 'upload'
    let selectedVideoFile= null;
    let selectedThumbFile= null;

    let editSourceType   = 'youtube';
    let editSelectedVideoFile = null;
    let editSelectedThumbFile = null;

    /* ── CSRF Helper ───────────────────────────────────────────────────── */
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content') || '';
        const input = document.querySelector('input[name="csrf_token"]');
        return input ? input.value : '';
    }

    /* ── Toast & Helpers ───────────────────────────────────────────────── */
    function notify(title, message, type = 'info') {
        if (typeof showToast === 'function') {
            showToast(title, message, type);
        } else {
            console.log(`[Toast ${type}] ${title}: ${message}`);
            if (type === 'error') alert(`${title}: ${message}`);
        }
    }

    function esc(str) {
        return (str || '').replace(/[&<>"']/g, t =>
            ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[t]));
    }

    function extractYoutubeId(url) {
        if (!url) return null;
        try {
            const u = new URL(url);
            let vid = u.searchParams.get('v');
            if (!vid && (u.hostname === 'youtu.be' || u.hostname.endsWith('.youtu.be'))) {
                vid = u.pathname.slice(1).split('/')[0];
            } else if (!vid && u.pathname.includes('/embed/')) {
                vid = u.pathname.split('/embed/')[1].split('/')[0];
            } else if (!vid && u.pathname.includes('/shorts/')) {
                vid = u.pathname.split('/shorts/')[1].split('/')[0];
            }
            return vid || null;
        } catch {
            return null;
        }
    }

    function formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function getLevelMeta(lvl) {
        switch ((lvl || '').toLowerCase()) {
            case 'beginner':
                return { label: 'Beginner', cls: 'beginner', icon: 'ph-leaf' };
            case 'advanced':
                return { label: 'Advanced', cls: 'advanced', icon: 'ph-lightning' };
            case 'intermediate':
            default:
                return { label: 'Intermediate', cls: 'intermediate', icon: 'ph-flame' };
        }
    }

    /* ── Update Quick Stats ────────────────────────────────────────────── */
    function updateStats() {
        const total = allTutorials.length;
        const beginner = allTutorials.filter(t => (t.level || '').toLowerCase() === 'beginner').length;
        const interm = allTutorials.filter(t => (t.level || '').toLowerCase() === 'intermediate').length;
        const advanced = allTutorials.filter(t => (t.level || '').toLowerCase() === 'advanced').length;
        const uploads = allTutorials.filter(t => (t.video_type === 'upload') || (!extractYoutubeId(t.youtube_url) && !!t.video_url)).length;

        if (statTotal) statTotal.textContent = total;
        if (statBeginner) statBeginner.textContent = beginner;
        if (statInterm) statInterm.textContent = interm;
        if (statAdvanced) statAdvanced.textContent = advanced;
        if (statUpload) statUpload.textContent = uploads;
    }

    /* ── Load Tutorials (API + Supabase Fallback) ───────────────────────── */
    async function loadTutorials() {
        if (!grid) return;
        grid.innerHTML = `
            <div class="tutorials-loading">
                <div class="tut-spinner"></div>
                <p>Loading clinic tutorials...</p>
            </div>`;

        try {
            // First attempt: Flask REST API endpoint
            const res = await fetch('/api/tutorials/list', {
                headers: { 'Accept': 'application/json' }
            });
            if (res.ok) {
                const json = await res.json();
                if (json.success && Array.isArray(json.tutorials)) {
                    allTutorials = json.tutorials;
                    updateStats();
                    renderGrid();
                    return;
                }
            }
        } catch (apiErr) {
            console.warn('[Tutorials] REST list failed, attempting Supabase direct fallback:', apiErr);
        }

        // Second attempt: Supabase client fallback
        if (typeof supabaseClient !== 'undefined' && supabaseClient) {
            const { data, error } = await supabaseClient
                .from('tutorials')
                .select('*, profiles(first_name, last_name, role, avatar_url)')
                .order('created_at', { ascending: false });

            if (!error && data) {
                allTutorials = data;
                updateStats();
                renderGrid();
                return;
            }
            console.error('[Tutorials] Supabase fallback error:', error);
        }

        grid.innerHTML = `
            <div class="tutorials-empty">
                <i class="ph ph-warning-circle"></i>
                <h3>Unable to load tutorials</h3>
                <p>Please check your internet connection or try refreshing the page.</p>
                <button type="button" class="btn-tut-primary" onclick="initTutorials()" style="margin-top:12px;">
                    <i class="ph ph-arrows-clockwise"></i> Try Again
                </button>
            </div>`;
    }

    /* ── Render Tutorials Grid ─────────────────────────────────────────── */
    function renderGrid() {
        if (!grid) return;

        const q = searchQ.toLowerCase().trim();

        // 1. Filter
        let filtered = allTutorials.filter(t => {
            const matchSearch = !q ||
                (t.title || '').toLowerCase().includes(q) ||
                (t.description || '').toLowerCase().includes(q) ||
                (t.level || '').toLowerCase().includes(q);

            const matchLevel = filterLevel === 'all' || (t.level || '').toLowerCase() === filterLevel.toLowerCase();

            const isUpload = (t.video_type === 'upload') || (!extractYoutubeId(t.youtube_url) && !!t.video_url);
            const matchType = filterSourceType === 'all' ||
                (filterSourceType === 'upload' && isUpload) ||
                (filterSourceType === 'youtube' && !isUpload);

            return matchSearch && matchLevel && matchType;
        });

        // 2. Sort
        if (currentSort === 'newest') {
            filtered.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
        } else if (currentSort === 'oldest') {
            filtered.sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0));
        } else if (currentSort === 'alpha') {
            filtered.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
        }

        // 3. Update count badge
        if (countBadge) {
            countBadge.textContent = `${filtered.length} Tutorial${filtered.length === 1 ? '' : 's'}`;
        }

        // 4. Empty State
        if (filtered.length === 0) {
            grid.innerHTML = `
                <div class="tutorials-empty">
                    <i class="ph ph-video-slash"></i>
                    <h3>No tutorials found</h3>
                    <p>${q ? `No results matching "${esc(q)}". Try a different search term or clear filters.` : 'No tutorials have been published yet.'}</p>
                    ${canManage ? `
                    <button class="btn-tut-primary" type="button" onclick="document.getElementById('addTutorialModal')?.classList.add('open')" style="margin-top:10px;">
                        <i class="ph ph-plus-circle"></i> Add First Tutorial
                    </button>
                    ` : ''}
                </div>`;
            return;
        }

        // 5. Build Cards
        grid.innerHTML = '';
        filtered.forEach(t => {
            const ytId = extractYoutubeId(t.youtube_url || t.video_url);
            const isUpload = (t.video_type === 'upload') || (!ytId && !!t.video_url);

            // Determine thumbnail
            let thumbUrl = t.thumbnail_url;
            if (!thumbUrl) {
                if (ytId) {
                    thumbUrl = `https://img.youtube.com/vi/${ytId}/hqdefault.jpg`;
                } else {
                    thumbUrl = '/static/images/hero-action.png';
                }
            }

            const levelMeta = getLevelMeta(t.level);

            // Uploader info
            const prof = t.profiles || {};
            const uploaderName = (prof.first_name || prof.last_name)
                ? `${prof.first_name || ''} ${prof.last_name || ''}`.trim()
                : 'PickleballHub Coach';
            const uploaderRole = prof.role ? prof.role.toUpperCase() : 'COACH';
            const avatarUrl = prof.avatar_url;

            // Permissions
            const isAuthor = currentUserId && t.uploaded_by === currentUserId;
            const canEdit = isGlobalAdmin || (canManage && isAuthor);

            const card = document.createElement('div');
            card.className = 'tutorial-card';
            card.dataset.id = t.id;

            card.innerHTML = `
                <div class="tutorial-thumb-wrap">
                    <img src="${esc(thumbUrl)}" alt="${esc(t.title)}" class="tutorial-thumb-img" onerror="this.src='/static/images/hero-action.png'">
                    
                    <!-- Source Format Badge -->
                    <span class="tut-badge-type ${isUpload ? 'upload' : 'youtube'}">
                        <i class="ph ${isUpload ? 'ph-film-slate' : 'ph-youtube-logo'}"></i>
                        ${isUpload ? 'Hub Original' : 'YouTube'}
                    </span>

                    <!-- Level Badge -->
                    <span class="tut-badge-level ${levelMeta.cls}">
                        <i class="ph ${levelMeta.icon}"></i>
                        ${esc(levelMeta.label)}
                    </span>

                    ${t.duration ? `
                    <!-- Duration Badge -->
                    <span class="tut-badge-duration">
                        <i class="ph ph-clock"></i> ${esc(t.duration)}
                    </span>
                    ` : ''}

                    <!-- Play Overlay Button -->
                    <button class="tutorial-play-overlay" 
                            data-id="${esc(t.id)}" 
                            data-title="${esc(t.title)}"
                            data-url="${esc(t.video_url || t.youtube_url)}"
                            data-type="${isUpload ? 'upload' : 'youtube'}"
                            title="Play tutorial">
                        <i class="ph-fill ph-play-circle"></i>
                    </button>
                </div>

                <div class="tutorial-card-body">
                    <h3 class="tutorial-card-title" title="${esc(t.title)}">${esc(t.title)}</h3>
                    <p class="tutorial-card-desc">${esc(t.description || 'Step-by-step clinic drills and tactical instructions.')}</p>

                    <!-- Uploader Profile Chip -->
                    <div class="tut-uploader-chip">
                        ${avatarUrl ? `
                            <img src="${esc(avatarUrl)}" alt="${esc(uploaderName)}" class="tut-uploader-avatar">
                        ` : `
                            <div class="tut-uploader-avatar-placeholder">
                                ${esc(uploaderName.charAt(0) || 'P')}
                            </div>
                        `}
                        <div class="tut-uploader-text">
                            <span class="tut-uploader-name">${esc(uploaderName)}</span>
                            <span class="tut-uploader-role">${esc(uploaderRole)}</span>
                        </div>
                    </div>

                    <!-- Card Action Footer -->
                    <div class="tutorial-card-footer">
                        <button class="btn-tut-card-watch" 
                                data-id="${esc(t.id)}"
                                data-title="${esc(t.title)}"
                                data-url="${esc(t.video_url || t.youtube_url)}"
                                data-type="${isUpload ? 'upload' : 'youtube'}">
                            <i class="ph ph-play"></i> Watch Video
                        </button>

                        ${canEdit ? `
                        <div class="tut-card-manage-btns">
                            <button class="btn-tut-icon edit tut-edit-trigger" data-id="${esc(t.id)}" title="Edit tutorial">
                                <i class="ph ph-pencil-simple"></i>
                            </button>
                            <button class="btn-tut-icon delete tut-delete-trigger" data-id="${esc(t.id)}" title="Delete tutorial">
                                <i class="ph ph-trash"></i>
                            </button>
                        </div>
                        ` : ''}
                    </div>
                </div>
            `;
            grid.appendChild(card);
        });

        // Attach Handlers to dynamic card elements
        grid.querySelectorAll('.tutorial-play-overlay, .btn-tut-card-watch').forEach(el => {
            el.addEventListener('click', () => {
                const id = el.dataset.id;
                const tutorial = allTutorials.find(x => x.id === id);
                if (tutorial) openWatchModal(tutorial);
            });
        });

        grid.querySelectorAll('.tut-edit-trigger').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                openEditModal(el.dataset.id);
            });
        });

        grid.querySelectorAll('.tut-delete-trigger').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteTutorial(el.dataset.id);
            });
        });
    }

    /* ── Universal Watch Modal ─────────────────────────────────────────── */
    function openWatchModal(t) {
        if (!watchModal) return;

        const ytId = extractYoutubeId(t.youtube_url || t.video_url);
        const isUpload = (t.video_type === 'upload') || (!ytId && !!t.video_url);

        watchTitle.textContent = t.title || 'Tutorial & Clinic';

        // Badges
        const levelMeta = getLevelMeta(t.level);
        watchBadges.innerHTML = `
            <span class="tut-badge-level ${levelMeta.cls}"><i class="ph ${levelMeta.icon}"></i> ${esc(levelMeta.label)}</span>
            <span class="tut-badge-type ${isUpload ? 'upload' : 'youtube'}"><i class="ph ${isUpload ? 'ph-film-slate' : 'ph-youtube-logo'}"></i> ${isUpload ? 'Hub Original' : 'YouTube'}</span>
            ${t.duration ? `<span class="tut-badge-duration"><i class="ph ph-clock"></i> ${esc(t.duration)}</span>` : ''}
        `;

        // Description
        watchDesc.innerHTML = `<p>${esc(t.description || 'No additional instructions provided for this clinic.')}</p>`;

        // Uploader
        const prof = t.profiles || {};
        const uploaderName = (prof.first_name || prof.last_name)
            ? `${prof.first_name || ''} ${prof.last_name || ''}`.trim()
            : 'PickleballHub Coach';
        const uploaderRole = prof.role ? prof.role.toUpperCase() : 'COACH';
        watchUploader.innerHTML = `
            <div class="tut-uploader-avatar-placeholder" style="width:34px;height:34px;font-size:0.85rem;">
                ${esc(uploaderName.charAt(0) || 'P')}
            </div>
            <div class="tut-uploader-text">
                <span class="tut-uploader-name">${esc(uploaderName)}</span>
                <span class="tut-uploader-role">${esc(uploaderRole)}</span>
            </div>
        `;

        // Share button handler
        watchShareBtn.onclick = () => {
            const url = window.location.href.split('?')[0] + `?tutorial=${t.id}`;
            if (navigator.clipboard) {
                navigator.clipboard.writeText(url).then(() => {
                    notify('Link Copied', 'Tutorial link copied to clipboard.', 'success');
                }).catch(() => {
                    notify('Share Link', url, 'info');
                });
            } else {
                notify('Share Link', url, 'info');
            }
        };

        // Media Player Switcher
        if (isUpload) {
            // Uploaded HTML5 Video
            watchFrame.style.display = 'none';
            watchFrame.src = '';
            watchExternalBtn.style.display = 'none';

            watchVideoPlayer.style.display = 'block';
            watchVideoPlayer.src = t.video_url || t.youtube_url;
            watchVideoPlayer.load();
            watchVideoPlayer.play().catch(() => {});
        } else {
            // YouTube Iframe Embed
            watchVideoPlayer.pause();
            watchVideoPlayer.style.display = 'none';
            watchVideoPlayer.src = '';

            const embedUrl = `https://www.youtube.com/embed/${ytId}?autoplay=1&rel=0`;
            watchFrame.src = embedUrl;
            watchFrame.style.display = 'block';

            watchExternalBtn.href = t.youtube_url || `https://www.youtube.com/watch?v=${ytId}`;
            watchExternalBtn.style.display = 'inline-flex';
        }

        watchModal.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function closeWatchModal() {
        if (!watchModal) return;
        watchModal.classList.remove('open');
        document.body.style.overflow = '';

        // Stop video playback safely
        if (watchVideoPlayer) {
            watchVideoPlayer.pause();
            watchVideoPlayer.src = '';
        }
        if (watchFrame) {
            watchFrame.src = '';
        }
    }

    closeWatchBtn?.addEventListener('click', closeWatchModal);
    watchModal?.addEventListener('click', (e) => {
        if (e.target === watchModal) closeWatchModal();
    });

    /* ── Controls: Search, Clear, Filter Pills & Sort ──────────────────── */
    searchInput?.addEventListener('input', (e) => {
        searchQ = e.target.value;
        if (searchClearBtn) {
            searchClearBtn.style.display = searchQ.length > 0 ? 'flex' : 'none';
        }
        renderGrid();
    });

    searchClearBtn?.addEventListener('click', () => {
        if (searchInput) searchInput.value = '';
        searchQ = '';
        searchClearBtn.style.display = 'none';
        renderGrid();
        searchInput?.focus();
    });

    // Level Filter Pills
    levelPillsWrap?.querySelectorAll('.tut-filter-pill').forEach(btn => {
        btn.addEventListener('click', () => {
            levelPillsWrap.querySelectorAll('.tut-filter-pill').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterLevel = btn.dataset.level || 'all';
            renderGrid();
        });
    });

    // Source Filter Pills
    sourcePillsWrap?.querySelectorAll('.tut-filter-pill').forEach(btn => {
        btn.addEventListener('click', () => {
            sourcePillsWrap.querySelectorAll('.tut-filter-pill').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterSourceType = btn.dataset.type || 'all';
            renderGrid();
        });
    });

    // Sort Dropdown
    sortFilter?.addEventListener('change', (e) => {
        currentSort = e.target.value;
        renderGrid();
    });

    /* ── Add Tutorial Modal Logic ──────────────────────────────────────── */
    if (canManage && addBtn && addModal) {
        addBtn.addEventListener('click', () => {
            addForm?.reset();
            resetAddModalState();
            addModal.classList.add('open');
            document.body.style.overflow = 'hidden';
        });

        function closeAddModal() {
            addModal.classList.remove('open');
            document.body.style.overflow = '';
            resetAddModalState();
        }

        closeAddBtn?.addEventListener('click', closeAddModal);
        closeAddAltBtn?.addEventListener('click', closeAddModal);
        addModal.addEventListener('click', (e) => {
            if (e.target === addModal) closeAddModal();
        });

        // Tab Switchers: YouTube vs Upload
        tabAddYoutube?.addEventListener('click', () => setAddSourceType('youtube'));
        tabAddUpload?.addEventListener('click', () => setAddSourceType('upload'));

        function setAddSourceType(type) {
            addSourceType = type;
            tabAddYoutube.classList.toggle('active', type === 'youtube');
            tabAddUpload.classList.toggle('active', type === 'upload');

            groupAddYoutube.style.display = type === 'youtube' ? 'flex' : 'none';
            groupAddUpload.style.display = type === 'upload' ? 'flex' : 'none';

            if (type === 'youtube') {
                tUrlInput.setAttribute('required', 'required');
            } else {
                tUrlInput.removeAttribute('required');
            }
        }

        function resetAddModalState() {
            setAddSourceType('youtube');
            selectedVideoFile = null;
            selectedThumbFile = null;
            if (selectedFileCard) selectedFileCard.style.display = 'none';
            if (videoDropZone) videoDropZone.style.display = 'flex';
            if (videoPreviewWrap) {
                videoPreviewWrap.style.display = 'none';
                if (videoUploadPreview) {
                    videoUploadPreview.pause();
                    videoUploadPreview.src = '';
                }
            }
            if (ytLivePreview) ytLivePreview.style.display = 'none';
            if (progressWrap) progressWrap.style.display = 'none';
            if (submitAddBtn) {
                submitAddBtn.disabled = false;
                submitAddBtn.innerHTML = '<i class="ph ph-plus"></i> <span>Publish Tutorial</span>';
            }
        }

        // Live YouTube Preview
        tUrlInput?.addEventListener('input', () => {
            const vid = extractYoutubeId(tUrlInput.value.trim());
            if (vid) {
                ytPreviewImg.src = `https://img.youtube.com/vi/${vid}/hqdefault.jpg`;
                ytLivePreview.style.display = 'block';
            } else {
                ytLivePreview.style.display = 'none';
            }
        });

        // Drag & Drop Video Handling
        videoDropZone?.addEventListener('click', () => tVideoFileInput?.click());
        videoDropZone?.addEventListener('dragover', (e) => {
            e.preventDefault();
            videoDropZone.classList.add('drag-over');
        });
        videoDropZone?.addEventListener('dragleave', () => videoDropZone.classList.remove('drag-over'));
        videoDropZone?.addEventListener('drop', (e) => {
            e.preventDefault();
            videoDropZone.classList.remove('drag-over');
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleSelectedVideoFile(e.dataTransfer.files[0]);
            }
        });

        tVideoFileInput?.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                handleSelectedVideoFile(e.target.files[0]);
            }
        });

        function handleSelectedVideoFile(file) {
            const maxBytes = 50 * 1024 * 1024; // 50 MB (Supabase max limit)
            if (file.size > maxBytes) {
                notify('File Too Large', `Video size (${formatFileSize(file.size)}) exceeds 50 MB limit.`, 'error');
                return;
            }

            selectedVideoFile = file;
            if (selectedFileName) selectedFileName.textContent = file.name;
            if (selectedFileSize) selectedFileSize.textContent = formatFileSize(file.size);

            if (selectedFileCard) selectedFileCard.style.display = 'flex';
            if (videoDropZone) videoDropZone.style.display = 'none';

            // Show video preview
            try {
                const objectUrl = URL.createObjectURL(file);
                if (videoUploadPreview) videoUploadPreview.src = objectUrl;
                if (videoPreviewWrap) videoPreviewWrap.style.display = 'block';
            } catch (e) {
                console.warn('[Video Preview] could not create ObjectURL:', e);
            }
        }

        removeVideoBtn?.addEventListener('click', () => {
            selectedVideoFile = null;
            if (tVideoFileInput) tVideoFileInput.value = '';
            if (selectedFileCard) selectedFileCard.style.display = 'none';
            if (videoDropZone) videoDropZone.style.display = 'flex';
            if (videoPreviewWrap) {
                videoPreviewWrap.style.display = 'none';
                if (videoUploadPreview) {
                    videoUploadPreview.pause();
                    videoUploadPreview.src = '';
                }
            }
        });

        tThumbFileInput?.addEventListener('change', (e) => {
            if (e.target.files && e.target.files[0]) {
                selectedThumbFile = e.target.files[0];
            }
        });

        // ── Submit Add Tutorial Form ────────────────────────────────────
        addForm?.addEventListener('submit', async (e) => {
            e.preventDefault();

            const title = tTitleInput.value.trim();
            const level = tLevelInput.value;
            const duration = tDurationInput.value.trim();
            const desc = tDescInput.value.trim();

            if (!title) {
                notify('Title Required', 'Please enter a tutorial title.', 'error');
                return;
            }

            let videoUrl = '';
            let thumbnailUrl = '';
            let youtubeUrl = '';

            submitAddBtn.disabled = true;

            // 1. If Video Upload Mode:
            if (addSourceType === 'upload') {
                if (!selectedVideoFile) {
                    notify('No Video Selected', 'Please choose or drag & drop a video file to upload.', 'error');
                    submitAddBtn.disabled = false;
                    return;
                }

                progressWrap.style.display = 'block';
                progressBar.style.width = '0%';
                progressPercent.textContent = '0%';
                progressLabel.textContent = 'Uploading video file...';
                submitAddBtn.innerHTML = '<div class="tut-spinner sm"></div> <span>Uploading Video...</span>';

                try {
                    const uploadResult = await uploadVideoWithProgress(
                        selectedVideoFile,
                        selectedThumbFile,
                        (pct) => {
                            progressBar.style.width = pct + '%';
                            progressPercent.textContent = pct + '%';
                        }
                    );

                    if (!uploadResult || !uploadResult.success) {
                        throw new Error(uploadResult.error || 'Video upload failed.');
                    }

                    videoUrl = uploadResult.video_url;
                    thumbnailUrl = uploadResult.thumbnail_url || '';
                    youtubeUrl = videoUrl; // backward-compatibility
                } catch (upErr) {
                    notify('Upload Failed', upErr.message || 'Error uploading video.', 'error');
                    submitAddBtn.disabled = false;
                    submitAddBtn.innerHTML = '<i class="ph ph-plus"></i> <span>Publish Tutorial</span>';
                    progressWrap.style.display = 'none';
                    return;
                }
            } else {
                // 2. YouTube Mode
                youtubeUrl = tUrlInput.value.trim();
                const ytId = extractYoutubeId(youtubeUrl);
                if (!youtubeUrl || !ytId) {
                    notify('Invalid URL', 'Please enter a valid YouTube video URL.', 'error');
                    submitAddBtn.disabled = false;
                    return;
                }
                videoUrl = youtubeUrl;
                thumbnailUrl = `https://img.youtube.com/vi/${ytId}/hqdefault.jpg`;
                submitAddBtn.innerHTML = '<div class="tut-spinner sm"></div> <span>Publishing...</span>';
            }

            // 3. Save Record via REST API
            try {
                const savePayload = {
                    title,
                    description: desc,
                    level,
                    duration,
                    video_type: addSourceType,
                    video_url: videoUrl,
                    youtube_url: youtubeUrl,
                    thumbnail_url: thumbnailUrl
                };

                const res = await fetch('/api/tutorials/save', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify(savePayload)
                });

                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.error || 'Failed to publish tutorial.');
                }

                notify('Tutorial Published', 'Your clinic guide is now live for the community!', 'success');
                closeAddModal();
                loadTutorials();
            } catch (saveErr) {
                notify('Publish Error', saveErr.message || 'Could not save tutorial record.', 'error');
                submitAddBtn.disabled = false;
                submitAddBtn.innerHTML = '<i class="ph ph-plus"></i> <span>Publish Tutorial</span>';
            }
        });
    }

    /* ── Edit Tutorial Modal Logic ─────────────────────────────────────── */
    async function openEditModal(id) {
        if (!editModal) return;

        const tutorial = allTutorials.find(x => x.id === id);
        if (!tutorial) {
            notify('Error', 'Tutorial record not found.', 'error');
            return;
        }

        editIdInput.value = tutorial.id;
        editTitleInput.value = tutorial.title || '';
        editLevelInput.value = tutorial.level || 'Beginner';
        editDurationInput.value = tutorial.duration || '';
        editDescInput.value = tutorial.description || '';

        const ytId = extractYoutubeId(tutorial.youtube_url || tutorial.video_url);
        const isUpload = (tutorial.video_type === 'upload') || (!ytId && !!tutorial.video_url);

        editCurTypeInput.value = isUpload ? 'upload' : 'youtube';
        editExVidUrl.value = tutorial.video_url || '';
        editExThumbUrl.value = tutorial.thumbnail_url || '';

        setEditSourceType(isUpload ? 'upload' : 'youtube');

        if (!isUpload && editUrlInput) {
            editUrlInput.value = tutorial.youtube_url || tutorial.video_url || '';
            if (ytId && editYtPreviewImg) {
                editYtPreviewImg.src = `https://img.youtube.com/vi/${ytId}/hqdefault.jpg`;
                editYtPreview.style.display = 'block';
            }
        }

        if (isUpload && editExistingNotice) {
            editExistingNotice.style.display = 'flex';
        }

        editModal.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function closeEditModal() {
        if (!editModal) return;
        editModal.classList.remove('open');
        document.body.style.overflow = '';
        editForm?.reset();
        editSelectedVideoFile = null;
        editSelectedThumbFile = null;
        if (editSelectedFileCard) editSelectedFileCard.style.display = 'none';
        if (editVideoDropZone) editVideoDropZone.style.display = 'flex';
        if (editProgressWrap) editProgressWrap.style.display = 'none';
    }

    closeEditBtn?.addEventListener('click', closeEditModal);
    closeEditAltBtn?.addEventListener('click', closeEditModal);
    editModal?.addEventListener('click', (e) => {
        if (e.target === editModal) closeEditModal();
    });

    tabEditYoutube?.addEventListener('click', () => setEditSourceType('youtube'));
    tabEditUpload?.addEventListener('click', () => setEditSourceType('upload'));

    function setEditSourceType(type) {
        editSourceType = type;
        tabEditYoutube.classList.toggle('active', type === 'youtube');
        tabEditUpload.classList.toggle('active', type === 'upload');

        groupEditYoutube.style.display = type === 'youtube' ? 'flex' : 'none';
        groupEditUpload.style.display = type === 'upload' ? 'flex' : 'none';
    }

    // Edit YouTube Live Preview
    editUrlInput?.addEventListener('input', () => {
        const vid = extractYoutubeId(editUrlInput.value.trim());
        if (vid && editYtPreviewImg) {
            editYtPreviewImg.src = `https://img.youtube.com/vi/${vid}/hqdefault.jpg`;
            editYtPreview.style.display = 'block';
        } else {
            editYtPreview.style.display = 'none';
        }
    });

    // Edit Dropzone File Handling
    editVideoDropZone?.addEventListener('click', () => editVideoFileInput?.click());
    editVideoFileInput?.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            handleEditSelectedVideoFile(e.target.files[0]);
        }
    });

    function handleEditSelectedVideoFile(file) {
        const maxBytes = 50 * 1024 * 1024; // 50 MB (Supabase max limit)
        if (file.size > maxBytes) {
            notify('File Too Large', `Video size exceeds 50 MB limit.`, 'error');
            return;
        }
        editSelectedVideoFile = file;
        if (editSelectedFileName) editSelectedFileName.textContent = file.name;
        if (editSelectedFileSize) editSelectedFileSize.textContent = formatFileSize(file.size);
        if (editSelectedFileCard) editSelectedFileCard.style.display = 'flex';
        if (editVideoDropZone) editVideoDropZone.style.display = 'none';
        if (editExistingNotice) editExistingNotice.style.display = 'none';
    }

    editRemoveVideoBtn?.addEventListener('click', () => {
        editSelectedVideoFile = null;
        if (editVideoFileInput) editVideoFileInput.value = '';
        if (editSelectedFileCard) editSelectedFileCard.style.display = 'none';
        if (editVideoDropZone) editVideoDropZone.style.display = 'flex';
        if (editExistingNotice) editExistingNotice.style.display = 'flex';
    });

    editThumbFileInput?.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            editSelectedThumbFile = e.target.files[0];
        }
    });

    // ── Submit Edit Tutorial Form ───────────────────────────────────────
    editForm?.addEventListener('submit', async (e) => {
        e.preventDefault();

        const id = editIdInput.value;
        const title = editTitleInput.value.trim();
        const level = editLevelInput.value;
        const duration = editDurationInput.value.trim();
        const desc = editDescInput.value.trim();

        if (!title) {
            notify('Title Required', 'Please enter a tutorial title.', 'error');
            return;
        }

        submitEditBtn.disabled = true;

        let videoUrl = editExVidUrl.value;
        let thumbnailUrl = editExThumbUrl.value;
        let youtubeUrl = '';

        if (editSourceType === 'upload') {
            // If new video file selected, upload it
            if (editSelectedVideoFile) {
                editProgressWrap.style.display = 'block';
                editProgressBar.style.width = '0%';
                editProgressPercent.textContent = '0%';
                submitEditBtn.innerHTML = '<div class="tut-spinner sm"></div> <span>Uploading New Video...</span>';

                try {
                    const uploadResult = await uploadVideoWithProgress(
                        editSelectedVideoFile,
                        editSelectedThumbFile,
                        (pct) => {
                            editProgressBar.style.width = pct + '%';
                            editProgressPercent.textContent = pct + '%';
                        }
                    );

                    if (!uploadResult || !uploadResult.success) {
                        throw new Error(uploadResult.error || 'Video upload failed.');
                    }

                    videoUrl = uploadResult.video_url;
                    if (uploadResult.thumbnail_url) thumbnailUrl = uploadResult.thumbnail_url;
                } catch (upErr) {
                    notify('Upload Failed', upErr.message || 'Error uploading video.', 'error');
                    submitEditBtn.disabled = false;
                    submitEditBtn.innerHTML = '<i class="ph ph-check"></i> <span>Save Changes</span>';
                    editProgressWrap.style.display = 'none';
                    return;
                }
            }
            youtubeUrl = videoUrl;
        } else {
            // YouTube Mode
            youtubeUrl = editUrlInput.value.trim();
            const ytId = extractYoutubeId(youtubeUrl);
            if (!youtubeUrl || !ytId) {
                notify('Invalid URL', 'Please enter a valid YouTube video URL.', 'error');
                submitEditBtn.disabled = false;
                return;
            }
            videoUrl = youtubeUrl;
            thumbnailUrl = `https://img.youtube.com/vi/${ytId}/hqdefault.jpg`;
        }

        try {
            submitEditBtn.innerHTML = '<div class="tut-spinner sm"></div> <span>Saving...</span>';

            const payload = {
                id,
                title,
                description: desc,
                level,
                duration,
                video_type: editSourceType,
                video_url: videoUrl,
                youtube_url: youtubeUrl,
                thumbnail_url: thumbnailUrl
            };

            const res = await fetch('/api/tutorials/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.error || 'Could not update tutorial.');
            }

            notify('Tutorial Updated', 'Your changes have been saved.', 'success');
            closeEditModal();
            loadTutorials();
        } catch (saveErr) {
            notify('Update Error', saveErr.message || 'Could not update tutorial.', 'error');
            submitEditBtn.disabled = false;
            submitEditBtn.innerHTML = '<i class="ph ph-check"></i> <span>Save Changes</span>';
        }
    });

    /* ── Delete Tutorial ───────────────────────────────────────────────── */
    async function deleteTutorial(id) {
        const executeDelete = async () => {
            try {
                const res = await fetch(`/api/tutorials/delete/${id}`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken()
                    }
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.error || 'Could not delete tutorial.');
                }

                notify('Tutorial Deleted', 'The tutorial was successfully removed.', 'success');
                loadTutorials();
            } catch (err) {
                notify('Delete Error', err.message || 'Could not delete tutorial.', 'error');
            }
        };

        if (typeof showConfirmModal === 'function') {
            showConfirmModal({
                title: 'Delete Tutorial',
                message: 'Are you sure you want to delete this tutorial? This action cannot be undone.',
                confirmText: 'Delete',
                danger: true,
                onConfirm: executeDelete
            });
        } else {
            if (confirm('Delete this tutorial? This action cannot be undone.')) {
                executeDelete();
            }
        }
    }

    /* ── Helper: XHR Video Upload with Progress ────────────────────────── */
    function uploadVideoWithProgress(videoFile, thumbFile, onProgress) {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            formData.append('video', videoFile);
            if (thumbFile) {
                formData.append('thumbnail', thumbFile);
            }

            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/tutorials/upload', true);
            xhr.setRequestHeader('X-CSRFToken', getCsrfToken());

            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable && onProgress) {
                    const pct = Math.round((e.loaded / e.total) * 100);
                    onProgress(pct);
                }
            };

            xhr.onload = () => {
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (xhr.status >= 200 && xhr.status < 300 && response.success) {
                        resolve(response);
                    } else {
                        reject(new Error(response.error || `Upload failed with status ${xhr.status}`));
                    }
                } catch (e) {
                    reject(new Error('Malformed response from server during upload.'));
                }
            };

            xhr.onerror = () => {
                reject(new Error('Network error during video upload. Please check your connection.'));
            };

            xhr.send(formData);
        });
    }

    /* ── Keyboard Shortcuts (Escape to Close Modals) ───────────────────── */
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (watchModal?.classList.contains('open')) closeWatchModal();
            if (addModal?.classList.contains('open')) closeAddModal();
            if (editModal?.classList.contains('open')) closeEditModal();
        }
    });

    /* ── Realtime Supabase Channel ─────────────────────────────────────── */
    if (typeof supabaseClient !== 'undefined' && supabaseClient) {
        try {
            supabaseClient.channel('tutorials_realtime_sync')
                .on('postgres_changes', { event: '*', schema: 'public', table: 'tutorials' }, () => {
                    loadTutorials();
                })
                .subscribe();
        } catch (e) {
            console.warn('[Tutorials Realtime] subscription skipped:', e);
        }
    }

    /* ── Initial Load ──────────────────────────────────────────────────── */
    loadTutorials();
}

/* ── Bootstrap on DOM Ready ────────────────────────────────────────────── */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTutorials);
} else {
    initTutorials();
}
window.addEventListener('supabase-ready', initTutorials, { once: true });

