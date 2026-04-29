/**
 * tutorials.js
 * Handles:
 *  - Loading tutorials from Supabase
 *  - YouTube embed modal (player view)
 *  - Add / delete tutorial (admin view)
 *  - Search & level filter
 *  - Realtime updates
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!supabaseClient) {
        console.error('[Tutorials] Supabase client not initialised.');
        return;
    }

    /* ── DOM ──────────────────────────────────────────── */
    const grid         = document.getElementById('tutorialsGrid');
    const searchInput  = document.getElementById('tutorialsSearch');
    const levelFilter  = document.getElementById('levelFilter');
    const countLabel   = document.getElementById('tutorialsCount');

    // Admin elements (may not exist on player page)
    const addBtn       = document.getElementById('addTutorialBtn');
    const addModal     = document.getElementById('addTutorialModal');
    const addForm      = document.getElementById('addTutorialForm');
    const closeModalBtn= document.getElementById('closeTutorialModal');
    const submitBtn    = document.getElementById('submitTutorialBtn');

    // Watch modal (player page)
    const watchModal   = document.getElementById('watchModal');
    const watchFrame   = document.getElementById('watchFrame');
    const watchTitle   = document.getElementById('watchTitle');
    const closeWatch   = document.getElementById('closeWatch');

    /* ── State ────────────────────────────────────────── */
    let allTutorials = [];
    let searchQ      = '';
    let filterLevel  = 'all';

    /* ── Helpers ──────────────────────────────────────── */
    function esc(str) {
        return (str || '').replace(/[&<>"']/g, t =>
            ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[t]));
    }

    function toEmbedUrl(url) {
        // Handle both full URL and short forms
        try {
            const u = new URL(url);
            let vid = u.searchParams.get('v');
            if (!vid && u.hostname === 'youtu.be') vid = u.pathname.slice(1);
            if (!vid) return null;
            return `https://www.youtube.com/embed/${vid}?autoplay=1&rel=0`;
        } catch { return null; }
    }

    function toThumbUrl(url) {
        try {
            const u = new URL(url);
            let vid = u.searchParams.get('v');
            if (!vid && u.hostname === 'youtu.be') vid = u.pathname.slice(1);
            if (!vid) return 'https://img.youtube.com/vi/default/hqdefault.jpg';
            return `https://img.youtube.com/vi/${vid}/hqdefault.jpg`;
        } catch {
            return 'https://img.youtube.com/vi/default/hqdefault.jpg';
        }
    }

    function levelClass(lvl) {
        return { Beginner:'beginner', Intermediate:'intermediate', Advanced:'advanced' }[lvl] || 'beginner';
    }

    function levelIcon(lvl) {
        return { Beginner:'ph-leaf', Intermediate:'ph-flame', Advanced:'ph-lightning' }[lvl] || 'ph-leaf';
    }

    /* ── Load tutorials ───────────────────────────────── */
    async function loadTutorials() {
        if (!grid) return;
        grid.innerHTML = `<div class="tutorials-loading"><i class="ph ph-spinner"></i> Loading...</div>`;

        const { data, error } = await supabaseClient
            .from('tutorials')
            .select('*')
            .order('created_at', { ascending: false });

        if (error) {
            console.error('[Tutorials] load error:', error);
            grid.innerHTML = `<div class="tutorials-empty"><i class="ph ph-warning"></i><p>Could not load tutorials.</p></div>`;
            return;
        }

        allTutorials = data || [];
        renderGrid();
    }

    function renderGrid() {
        const q   = searchQ.toLowerCase();
        const filtered = allTutorials.filter(t => {
            const matchSearch = !q || t.title.toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q);
            const matchLevel  = filterLevel === 'all' || t.level === filterLevel;
            return matchSearch && matchLevel;
        });

        if (countLabel) countLabel.textContent = `${filtered.length} Tutorial${filtered.length !== 1 ? 's' : ''}`;

        if (filtered.length === 0) {
            grid.innerHTML = `<div class="tutorials-empty"><i class="ph ph-video-slash"></i><p>No tutorials found.</p></div>`;
            return;
        }

        grid.innerHTML = '';
        filtered.forEach(t => {
            const thumb  = toThumbUrl(t.youtube_url);
            const lvlCls = levelClass(t.level);
            const lvlIco = levelIcon(t.level);
            const isAdmin = !!addBtn; // admin pages have the add button

            const card = document.createElement('div');
            card.className = 'tutorial-card';
            card.innerHTML = `
                <div class="tutorial-thumb" style="background-image:url('${esc(thumb)}');">
                    <button class="tutorial-play-btn" data-url="${esc(t.youtube_url)}" data-title="${esc(t.title)}">
                        <i class="ph-fill ph-play-circle"></i>
                    </button>
                    <span class="tutorial-level ${lvlCls}"><i class="ph ${lvlIco}"></i> ${esc(t.level)}</span>
                </div>
                <div class="tutorial-info">
                    <h4>${esc(t.title)}</h4>
                    <p>${esc(t.description || '')}</p>
                    <div class="tutorial-footer">
                        <a href="${esc(t.youtube_url)}" target="_blank" rel="noopener" class="tutorial-yt-link">
                            <i class="ph ph-youtube-logo"></i> Watch on YouTube
                        </a>
                        ${isAdmin ? `<button class="tutorial-delete-btn" data-id="${esc(t.id)}" title="Remove tutorial"><i class="ph ph-trash"></i></button>` : ''}
                    </div>
                </div>`;
            grid.appendChild(card);
        });

        // Attach play handlers
        grid.querySelectorAll('.tutorial-play-btn').forEach(btn => {
            btn.addEventListener('click', () => openWatch(btn.dataset.url, btn.dataset.title));
        });

        // Attach delete handlers (admin only)
        grid.querySelectorAll('.tutorial-delete-btn').forEach(btn => {
            btn.addEventListener('click', () => deleteTutorial(btn.dataset.id));
        });
    }

    /* ── Watch modal ──────────────────────────────────── */
    function openWatch(url, title) {
        if (!watchModal || !watchFrame) return;
        const embed = toEmbedUrl(url);
        if (!embed) { window.open(url, '_blank'); return; }
        watchFrame.src = embed;
        if (watchTitle) watchTitle.textContent = title || 'Tutorial';
        watchModal.classList.add('open');
    }

    function closeWatchModal() {
        if (!watchModal) return;
        watchModal.classList.remove('open');
        if (watchFrame) watchFrame.src = '';
    }

    closeWatch?.addEventListener('click', closeWatchModal);
    watchModal?.addEventListener('click', e => { if (e.target === watchModal) closeWatchModal(); });

    /* ── Add tutorial (admin) ─────────────────────────── */
    addBtn?.addEventListener('click', () => addModal?.classList.add('open'));
    closeModalBtn?.addEventListener('click', () => addModal?.classList.remove('open'));
    addModal?.addEventListener('click', e => { if (e.target === addModal) addModal.classList.remove('open'); });

    addForm?.addEventListener('submit', async e => {
        e.preventDefault();
        const title   = document.getElementById('tTitle')?.value.trim();
        const desc    = document.getElementById('tDesc')?.value.trim();
        const url     = document.getElementById('tUrl')?.value.trim();
        const level   = document.getElementById('tLevel')?.value;

        if (!title || !url) return;

        submitBtn && (submitBtn.disabled = true);
        submitBtn && (submitBtn.textContent = 'Adding…');

        const { error } = await supabaseClient.from('tutorials').insert({
            title, description: desc, youtube_url: url, level,
            uploaded_by: currentUserId || null
        });

        submitBtn && (submitBtn.disabled = false);
        submitBtn && (submitBtn.textContent = 'Add Tutorial');

        if (error) {
            alert('Error adding tutorial: ' + error.message);
            return;
        }

        addForm.reset();
        addModal?.classList.remove('open');
        loadTutorials();
    });

    /* ── Delete tutorial (admin) ──────────────────────── */
    async function deleteTutorial(id) {
        if (!confirm('Remove this tutorial?')) return;
        const { error } = await supabaseClient.from('tutorials').delete().eq('id', id);
        if (error) { alert('Could not delete tutorial: ' + error.message); return; }
        loadTutorials();
    }

    /* ── Search & filter ──────────────────────────────── */
    searchInput?.addEventListener('input', e => {
        searchQ = e.target.value.trim();
        renderGrid();
    });

    levelFilter?.addEventListener('change', e => {
        filterLevel = e.target.value;
        renderGrid();
    });

    /* ── Realtime ─────────────────────────────────────── */
    supabaseClient.channel('tutorials_realtime')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'tutorials' }, () => {
            loadTutorials();
        })
        .subscribe();

    /* ── Init ─────────────────────────────────────────── */
    loadTutorials();
});
