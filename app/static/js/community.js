/**
 * community.js — Image upload, Share, Smart News Feed
 */
function initCommunity() {
    if (!supabaseClient) { console.error('[Community] Supabase not init.'); return; }

    /* ── DOM refs ─────────────────────────────────── */
    const feedWrapper = document.getElementById('community-feed-wrapper');
    const postTextarea = document.getElementById('post-textarea');
    const postBtn = document.getElementById('btn-post');
    const postsCountEl = document.getElementById('posts-count-label');
    const currentAvatarEl = document.getElementById('current-user-avatar');
    const imageInput = document.getElementById('post-image-input');
    const imagePreviewWrap = document.getElementById('post-image-preview-wrap');
    const imagePreview = document.getElementById('post-image-preview');
    const removeImageBtn = document.getElementById('btn-remove-image');
    const refreshBtn = document.getElementById('btn-refresh-feed');
    const smartBanner = document.getElementById('smart-feed-banner');
    const smartMsg = document.getElementById('smart-feed-message');
    const closeBanner = document.getElementById('btn-close-banner');
    const shareOverlay = document.getElementById('share-modal-overlay');
    const closeShare = document.getElementById('btn-close-share');
    const sharePreview = document.getElementById('share-post-preview');
    const shareCopyLink = document.getElementById('share-copy-link');
    const shareTwitter = document.getElementById('share-twitter');
    const shareFacebook = document.getElementById('share-facebook');
    const shareCopyText = document.getElementById('share-copy-text');
    const copiedToast = document.getElementById('share-copied-toast');

    /* ── State ────────────────────────────────────── */
    let selectedImageFile = null;
    let viewedPostIds = new Set(JSON.parse(localStorage.getItem('viewed_post_ids') || '[]'));
    let allPosts = [];
    let currentSharePost = null;
    let currentUserName = '';
    let currentCategoryFilter = 'all';
    let currentSearchQuery = '';

    /* ── Helpers ─────────────────────────────────── */
    function escapeHTML(str = '') {
        return String(str).replace(/[&<>'"]/g, t => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[t]
        ));
    }

    function formatPostContent(rawText = '') {
        const escaped = escapeHTML(rawText);
        return escaped.replace(/#([a-zA-Z0-9_]+)/g, '<span class="post-tag-pill" data-tag="#$1">#$1</span>');
    }

    function timeAgo(iso) {
        const d = Math.floor((Date.now() - new Date(iso)) / 60000);
        const h = Math.floor(d / 60), day = Math.floor(h / 24);
        if (d < 1) return 'just now';
        if (d < 60) return `${d}m ago`;
        if (h < 24) return `${h}h ago`;
        if (day < 7) return `${day}d ago`;
        return new Date(iso).toLocaleDateString();
    }

    function initials(f = '?', l = '') {
        return ((f[0] || '') + (l[0] || '')).toUpperCase() || '?';
    }

    function markViewed(postId) {
        viewedPostIds.add(postId);
        localStorage.setItem('viewed_post_ids', JSON.stringify([...viewedPostIds]));
    }

    function showCopiedToast() {
        copiedToast.style.display = 'flex';
        setTimeout(() => { copiedToast.style.display = 'none'; }, 2000);
    }

    /* ── Bootstrap current-user avatar ──────────── */
    (async () => {
        if (!currentUserId || !currentAvatarEl) return;
        try {
            const { data } = await supabaseClient.from('profiles')
                .select('first_name, last_name, avatar_url').eq('id', currentUserId).single();
            if (data) {
                const ini = initials(data.first_name, data.last_name);
                if (data.avatar_url) {
                    currentAvatarEl.innerHTML = `<img src="${escapeHTML(data.avatar_url)}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;">`;
                } else {
                    currentAvatarEl.textContent = ini;
                }
                currentUserName = `${data.first_name || ''} ${data.last_name || ''}`.trim();
            }
        } catch (_) { }
    })();

    /* ══════════════════════════════════════════════
       IMAGE UPLOAD
    ══════════════════════════════════════════════ */
    if (imageInput) {
        imageInput.addEventListener('change', e => {
            const file = e.target.files[0];
            if (!file) return;
            if (file.size > 5 * 1024 * 1024) {
                if (typeof showToast === 'function') {
                    showToast('Upload Error', 'Image must be under 5 MB.', 'warning');
                } else {
                    alert('Image must be under 5 MB.');
                }
                imageInput.value = '';
                return;
            }
            selectedImageFile = file;
            const reader = new FileReader();
            reader.onload = ev => {
                imagePreview.src = ev.target.result;
                imagePreviewWrap.style.display = 'block';
            };
            reader.readAsDataURL(file);
        });
    }

    if (removeImageBtn) {
        removeImageBtn.addEventListener('click', () => {
            selectedImageFile = null;
            imageInput.value = '';
            imagePreview.src = '';
            imagePreviewWrap.style.display = 'none';
        });
    }

    async function uploadImage(file) {
        const ext = file.name.split('.').pop();
        const path = `${currentUserId}/${Date.now()}.${ext}`;
        const { data, error } = await supabaseClient.storage
            .from('community-images')
            .upload(path, file, { cacheControl: '3600', upsert: false });
        if (error) throw error;
        const { data: urlData } = supabaseClient.storage
            .from('community-images').getPublicUrl(path);
        return urlData.publicUrl;
    }

    /* ══════════════════════════════════════════════
       SMART NEWS FEED & FILTERING
    ══════════════════════════════════════════════ */
    function filterPosts() {
        let filtered = allPosts;

        // 1. Category Filter
        if (currentCategoryFilter === 'announcements') {
            filtered = filtered.filter(p => {
                const role = (p.author?.role || '').toLowerCase();
                const text = (p.content || '').toLowerCase();
                return role === 'adminstaff' || role === 'clubadmin' || role === 'owner' || text.includes('announcement') || text.includes('official');
            });
        } else if (currentCategoryFilter === 'matchplay') {
            filtered = filtered.filter(p => {
                const text = (p.content || '').toLowerCase();
                return text.includes('match') || text.includes('partner') || text.includes('game') || text.includes('league') || text.includes('open play') || text.includes('play') || text.includes('#openplay') || text.includes('#matchrecap');
            });
        } else if (currentCategoryFilter === 'drills') {
            filtered = filtered.filter(p => {
                const text = (p.content || '').toLowerCase();
                return text.includes('drill') || text.includes('tip') || text.includes('drop') || text.includes('dink') || text.includes('paddle') || text.includes('serve') || text.includes('third shot') || text.includes('#drilltip') || text.includes('#thirdshotdrop');
            });
        }

        // 2. Search Query Filter
        if (currentSearchQuery) {
            const q = currentSearchQuery.toLowerCase().trim();
            filtered = filtered.filter(p => {
                const author = `${p.author?.first_name || ''} ${p.author?.last_name || ''}`.toLowerCase();
                const text = (p.content || '').toLowerCase();
                return author.includes(q) || text.includes(q);
            });
        }

        renderSmartFeed(filtered);
    }

    async function loadPosts() {
        const { data: posts, error } = await supabaseClient
            .from('community_posts')
            .select(`
                *,
                author:profiles!community_posts_author_id_fkey(first_name, last_name, role, avatar_url),
                post_likes(profile_id),
                community_comments(id)
            `)
            .order('created_at', { ascending: false });

        if (error) {
            feedWrapper.innerHTML = `<div class="community-empty">
                <i class="ph ph-warning-circle"></i>
                <p>Could not load posts. Please try refreshing.</p></div>`;
            return;
        }

        allPosts = posts || [];
        if (postsCountEl) {
            postsCountEl.innerHTML = `<i class="ph ph-chat-circle-dots"></i> ${allPosts.length} post${allPosts.length !== 1 ? 's' : ''}`;
        }
        const filterAllBadge = document.getElementById('filter-all-count');
        if (filterAllBadge) filterAllBadge.textContent = allPosts.length;

        // Mark all currently rendered posts as viewed
        allPosts.forEach(p => markViewed(p.id));

        filterPosts();
    }

    function renderSmartFeed(posts) {
        feedWrapper.innerHTML = '';
        if (!posts || posts.length === 0) {
            feedWrapper.innerHTML = `<div class="community-empty">
                <i class="ph ph-chats-circle"></i>
                <p>No discussions found matching your filter. Be the first to start a conversation!</p></div>`;
            return;
        }
        posts.forEach(post => renderPostCard(post));
        bindFeedEvents();
    }

    /* ── Smart refresh: show an unviewed post first ── */
    async function smartRefresh() {
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = '<i class="ph ph-circle-notch" style="animation:spin 0.8s linear infinite"></i> Refreshing…';
        }

        const { data: posts } = await supabaseClient
            .from('community_posts')
            .select(`*, author:profiles!community_posts_author_id_fkey(first_name, last_name, role, avatar_url), post_likes(profile_id), community_comments(id)`)
            .order('created_at', { ascending: false });

        allPosts = posts || [];
        if (postsCountEl) {
            postsCountEl.innerHTML = `<i class="ph ph-chat-circle-dots"></i> ${allPosts.length} post${allPosts.length !== 1 ? 's' : ''}`;
        }
        const filterAllBadge = document.getElementById('filter-all-count');
        if (filterAllBadge) filterAllBadge.textContent = allPosts.length;

        // Find unviewed posts not from current user
        const unviewed = allPosts.filter(p => !viewedPostIds.has(p.id) && p.author_id !== currentUserId);

        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = '<i class="ph ph-arrows-clockwise"></i> Refresh';
        }

        feedWrapper.innerHTML = '';

        if (unviewed.length > 0) {
            // Pick one random unviewed post to highlight at top
            const featured = unviewed[Math.floor(Math.random() * unviewed.length)];
            markViewed(featured.id);

            // Show banner
            if (smartBanner && smartMsg) {
                smartMsg.textContent = `New discussion from the community you haven't seen yet!`;
                smartBanner.style.display = 'flex';
            }

            // Render featured card first, then rest
            renderPostCard(featured, true);
            allPosts.forEach(p => { if (p.id !== featured.id) renderPostCard(p); });
        } else {
            // No unviewed — show most recent with info banner
            if (smartBanner && smartMsg) {
                smartMsg.textContent = `You're all caught up! Showing the latest discussions.`;
                smartBanner.style.display = 'flex';
            }
            allPosts.forEach(p => renderPostCard(p));
        }

        bindFeedEvents();

        // Scroll to top of feed smoothly
        feedWrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    /* ══════════════════════════════════════════════
       RENDER POST CARD
    ══════════════════════════════════════════════ */
    function renderPostCard(post, featured = false) {
        const author = post.author || {};
        const postInitials = initials(author.first_name, author.last_name);
        const fullName = `${author.first_name || 'Unknown'} ${author.last_name || ''}`.trim();
        const rawRole = (author.role || '').toLowerCase();
        const role = author.role ? author.role.replace(/_/g, ' ') : '';
        const hasLiked = post.post_likes?.some(l => l.profile_id === currentUserId);
        const likesCount = post.post_likes?.length ?? 0;
        const commentsCount = post.community_comments?.length ?? 0;
        const isOwner = post.author_id === currentUserId;
        const avatarColors = ['#1A213B', '#29A356', '#3B82F6', '#8B5CF6', '#E15623', '#0EA5E9'];
        const colorIdx = (author.first_name?.charCodeAt(0) || 0) % avatarColors.length;
        const avatarColor = avatarColors[colorIdx];
        const authorAvatarUrl = author.avatar_url || null;

        // Check if official announcement
        const isAnnouncement = (
            rawRole === 'adminstaff' ||
            rawRole === 'clubadmin' ||
            rawRole === 'owner' ||
            (post.content && post.content.toLowerCase().includes('official announcement')) ||
            (post.content && post.content.toLowerCase().includes('#announcement'))
        );

        // Role Badge HTML with crisp icons
        let roleBadgeHtml = '';
        if (rawRole === 'adminstaff' || rawRole === 'admin staff') {
            roleBadgeHtml = `<span class="author-role-badge admin"><i class="ph ph-shield-check"></i> Admin Staff</span>`;
        } else if (rawRole === 'clubadmin' || rawRole === 'club admin') {
            roleBadgeHtml = `<span class="author-role-badge club"><i class="ph ph-crown"></i> Club Captain</span>`;
        } else if (rawRole === 'facilitystaff' || rawRole === 'facility staff') {
            roleBadgeHtml = `<span class="author-role-badge admin"><i class="ph ph-wrench"></i> Facility Staff</span>`;
        } else if (rawRole === 'owner') {
            roleBadgeHtml = `<span class="author-role-badge owner"><i class="ph ph-buildings"></i> Facility Owner</span>`;
        } else if (rawRole === 'player') {
            roleBadgeHtml = `<span class="author-role-badge player"><i class="ph ph-tennis-ball"></i> Player</span>`;
        } else if (rawRole) {
            roleBadgeHtml = `<span class="author-role-badge player">${escapeHTML(role)}</span>`;
        }

        const feedAvatarHtml = authorAvatarUrl
            ? `<div class="feed-avatar" style="overflow:hidden;"><img src="${escapeHTML(authorAvatarUrl)}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;"></div>`
            : `<div class="feed-avatar" style="background:${avatarColor}">${escapeHTML(postInitials)}</div>`;

        const card = document.createElement('div');
        card.className = `feed-post-card${featured ? ' feed-post-featured' : ''}${isAnnouncement ? ' is-announcement' : ''}`;
        card.dataset.postId = post.id;

        card.innerHTML = `
            ${isAnnouncement ? `<div class="post-announcement-ribbon"><i class="ph-fill ph-megaphone"></i> Official Announcement</div>` : ''}
            ${featured && !isAnnouncement ? `<div class="featured-badge"><i class="ph ph-sparkle"></i> New for you</div>` : ''}
            <div class="feed-post-header">
                ${feedAvatarHtml}
                <div class="feed-post-meta">
                    <div class="feed-author-line">
                        <h4 class="feed-author-name">${escapeHTML(fullName)}</h4>
                        ${roleBadgeHtml}
                    </div>
                    <span class="post-time"><i class="ph ph-clock"></i> ${timeAgo(post.created_at)}</span>
                </div>
                ${isOwner ? `
                <button class="delete-post-btn" title="Delete post" data-id="${post.id}">
                    <i class="ph ph-trash"></i>
                </button>` : ''}
            </div>

            <p class="feed-post-body">${formatPostContent(post.content)}</p>

            ${post.image_url ? `
            <div class="feed-post-image-wrap">
                <img src="${escapeHTML(post.image_url)}" alt="Post image" class="feed-post-image"
                     onclick="this.closest('.feed-post-image-wrap').classList.toggle('expanded')" />
            </div>` : ''}

            <div class="feed-post-footer">
                <button class="feed-action like-btn ${hasLiked ? 'liked' : ''}" data-id="${post.id}">
                    <i class="ph ${hasLiked ? 'ph-fill ph-heart' : 'ph-heart'}"></i>
                    <span class="like-count">${likesCount}</span> <span>${likesCount === 1 ? 'Like' : 'Likes'}</span>
                </button>
                <button class="feed-action comment-toggle-btn" data-id="${post.id}">
                    <i class="ph ph-chat-circle-dots"></i>
                    <span class="comment-count">${commentsCount}</span> <span>${commentsCount === 1 ? 'Comment' : 'Comments'}</span>
                </button>
                <button class="feed-action share-btn" data-id="${post.id}"
                    data-author="${escapeHTML(fullName)}"
                    data-content="${escapeHTML(post.content).substring(0, 200)}"
                    data-image="${post.image_url ? escapeHTML(post.image_url) : ''}">
                    <i class="ph ph-share-network"></i> <span>Share</span>
                </button>
            </div>

            <!-- Comment Section -->
            <div class="comment-section" id="comments-${post.id}">
                <div class="comment-input-row">
                    <div class="comment-avatar" id="ca-${post.id}">${currentAvatarEl?.textContent || '?'}</div>
                    <div class="comment-input-wrap">
                        <textarea class="comment-input" placeholder="Write a comment…" rows="1"
                            data-post-id="${post.id}"></textarea>
                        <button class="btn-comment-send" data-post-id="${post.id}" title="Send comment (Ctrl+Enter)">
                            <i class="ph ph-paper-plane-tilt"></i>
                        </button>
                    </div>
                </div>
                <div class="comments-list" id="comments-list-${post.id}">
                    <p class="comments-loading">Loading comments…</p>
                </div>
            </div>
        `;

        feedWrapper.appendChild(card);
    }

    /* ── Bind feed events after render ─────────── */
    function bindFeedEvents() {
        feedWrapper.querySelectorAll('.like-btn').forEach(b => b.addEventListener('click', handleLike));
        feedWrapper.querySelectorAll('.delete-post-btn').forEach(b => b.addEventListener('click', handleDeletePost));
        feedWrapper.querySelectorAll('.comment-toggle-btn').forEach(b => b.addEventListener('click', handleToggleComments));
        feedWrapper.querySelectorAll('.btn-comment-send').forEach(b => b.addEventListener('click', handlePostComment));
        feedWrapper.querySelectorAll('.share-btn').forEach(b => b.addEventListener('click', handleShare));
        feedWrapper.querySelectorAll('.post-tag-pill').forEach(pill => {
            pill.addEventListener('click', e => {
                e.stopPropagation();
                const tag = pill.dataset.tag;
                if (!tag) return;
                const searchInp = document.getElementById('community-search-input');
                if (searchInp) searchInp.value = tag;
                currentSearchQuery = tag;
                filterPosts();
                feedWrapper?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        });
        feedWrapper.querySelectorAll('.comment-input').forEach(ta => {
            ta.addEventListener('keydown', e => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    feedWrapper.querySelector(`.btn-comment-send[data-post-id="${ta.dataset.postId}"]`)?.click();
                }
            });
        });
    }

    /* ══════════════════════════════════════════════
       SHARE
    ══════════════════════════════════════════════ */
    function handleShare(e) {
        const btn = e.currentTarget;
        currentSharePost = {
            id: btn.dataset.id,
            author: btn.dataset.author,
            content: btn.dataset.content,
            image: btn.dataset.image
        };

        sharePreview.innerHTML = `
            <div class="share-preview-author"><strong>${escapeHTML(currentSharePost.author)}</strong></div>
            <p class="share-preview-text">${escapeHTML(currentSharePost.content)}${currentSharePost.content.length >= 200 ? '…' : ''}</p>
            ${currentSharePost.image ? `<img src="${escapeHTML(currentSharePost.image)}" class="share-preview-image" />` : ''}
        `;

        shareOverlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function closeShareModal() {
        shareOverlay.style.display = 'none';
        document.body.style.overflow = '';
        currentSharePost = null;
    }

    if (closeShare) closeShare.addEventListener('click', closeShareModal);
    if (shareOverlay) shareOverlay.addEventListener('click', e => { if (e.target === shareOverlay) closeShareModal(); });

    if (shareCopyLink) {
        shareCopyLink.addEventListener('click', () => {
            const url = `${window.location.origin}${window.location.pathname}#post-${currentSharePost?.id}`;
            navigator.clipboard.writeText(url).then(showCopiedToast);
        });
    }

    if (shareCopyText) {
        shareCopyText.addEventListener('click', () => {
            const text = `${currentSharePost?.author}: ${currentSharePost?.content}`;
            navigator.clipboard.writeText(text).then(showCopiedToast);
        });
    }

    if (shareTwitter) {
        shareTwitter.addEventListener('click', () => {
            const text = encodeURIComponent(`${currentSharePost?.content.substring(0, 200)} — via PickleballHub`);
            window.open(`https://twitter.com/intent/tweet?text=${text}`, '_blank');
        });
    }

    if (shareFacebook) {
        shareFacebook.addEventListener('click', () => {
            const url = encodeURIComponent(window.location.href);
            window.open(`https://www.facebook.com/sharer/sharer.php?u=${url}`, '_blank');
        });
    }

    /* ══════════════════════════════════════════════
       LIKE
    ══════════════════════════════════════════════ */
    async function handleLike(e) {
        const btn = e.currentTarget;
        const postId = btn.dataset.id;
        const liked = btn.classList.contains('liked');
        const icon = btn.querySelector('i');
        const countSpan = btn.querySelector('.like-count');
        const current = parseInt(countSpan.textContent) || 0;

        if (liked) {
            btn.classList.remove('liked');
            icon.className = 'ph ph-heart';
            countSpan.textContent = Math.max(0, current - 1);
            await supabaseClient.from('post_likes').delete().eq('post_id', postId).eq('profile_id', currentUserId);
        } else {
            btn.classList.add('liked');
            icon.className = 'ph ph-fill ph-heart';
            countSpan.textContent = current + 1;
            btn.classList.add('like-bounce');
            setTimeout(() => btn.classList.remove('like-bounce'), 400);
            await supabaseClient.from('post_likes').insert({ post_id: postId, profile_id: currentUserId });
        }
    }

    /* ══════════════════════════════════════════════
       DELETE POST
    ══════════════════════════════════════════════ */
    async function handleDeletePost(e) {
        const btn = e.currentTarget;
        const postId = btn.dataset.id;
        const card = btn.closest('.feed-post-card');

        const proceedDelete = async () => {
            card.style.opacity = '0';
            card.style.transform = 'scale(0.97)';
            card.style.transition = 'opacity 0.2s, transform 0.2s';
            const { error } = await supabaseClient.from('community_posts').delete().eq('id', postId);
            if (error) {
                if (typeof showToast === 'function') {
                    showToast('Delete Failed', error.message, 'error');
                } else {
                    alert('Could not delete: ' + error.message);
                }
                card.style.opacity = '';
                card.style.transform = '';
            } else {
                setTimeout(() => card.remove(), 200);
                if (typeof showToast === 'function') {
                    showToast('Post Deleted', 'Your post has been removed.', 'success');
                }
                if (postsCountEl) {
                    const n = Math.max(0, parseInt(postsCountEl.textContent) - 1);
                    postsCountEl.textContent = `${n} post${n !== 1 ? 's' : ''}`;
                }
            }
        };

        if (typeof showConfirmModal === 'function') {
            showConfirmModal({
                title: 'Delete Post',
                message: 'Delete this post and all its comments? This action cannot be undone.',
                confirmText: 'Delete',
                danger: true,
                onConfirm: proceedDelete
            });
        } else {
            if (confirm('Delete this post and all its comments?')) proceedDelete();
        }
    }

    /* ══════════════════════════════════════════════
       COMMENTS
    ══════════════════════════════════════════════ */
    function handleToggleComments(e) {
        const btn = e.currentTarget;
        const postId = btn.dataset.id;
        const section = document.getElementById(`comments-${postId}`);
        if (!section) return;
        const isOpen = section.classList.contains('open');
        btn.classList.toggle('active', !isOpen);
        if (isOpen) {
            section.classList.remove('open');
        } else {
            section.classList.add('open');
            loadComments(postId);
        }
    }

    async function loadComments(postId) {
        const listEl = document.getElementById(`comments-list-${postId}`);
        if (!listEl) return;
        listEl.innerHTML = '<p class="comments-loading">Loading comments…</p>';
        const { data: comments, error } = await supabaseClient
            .from('community_comments')
            .select(`*, author:profiles!community_comments_author_id_fkey(first_name, last_name, role, avatar_url)`)
            .eq('post_id', postId)
            .order('created_at', { ascending: true });
        if (error) { listEl.innerHTML = '<p class="no-comments-msg">Could not load comments.</p>'; return; }
        renderComments(postId, comments);
    }

    function renderComments(postId, comments) {
        const listEl = document.getElementById(`comments-list-${postId}`);
        if (!listEl) return;
        listEl.innerHTML = '';
        if (!comments || comments.length === 0) {
            listEl.innerHTML = '<p class="no-comments-msg">No comments yet. Be the first!</p>';
            return;
        }
        comments.forEach(c => {
            const a = c.author || {};
            const ini = initials(a.first_name, a.last_name);
            const fullName = `${a.first_name || 'Unknown'} ${a.last_name || ''}`.trim();
            const role = a.role ? a.role.replace(/_/g, ' ') : '';
            const canDel = c.author_id === currentUserId;
            const commentAvatarUrl = a.avatar_url || null;
            const commentAvatarHtml = commentAvatarUrl
                ? `<div class="comment-avatar" style="overflow:hidden;"><img src="${escapeHTML(commentAvatarUrl)}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;"></div>`
                : `<div class="comment-avatar">${escapeHTML(ini)}</div>`;
            const item = document.createElement('div');
            item.className = 'comment-item';
            item.dataset.commentId = c.id;
            item.innerHTML = `
                ${commentAvatarHtml}
                <div class="comment-body-wrap">
                    <div class="comment-author-name">${escapeHTML(fullName)}
                        ${role ? `<span class="comment-role">(${escapeHTML(role)})</span>` : ''}
                    </div>
                    <p class="comment-text">${escapeHTML(c.content)}</p>
                    <div class="comment-meta-row">
                        <span class="comment-time"><i class="ph ph-clock"></i> ${timeAgo(c.created_at)}</span>
                        ${canDel ? `<button class="delete-comment-btn" data-id="${c.id}" data-post-id="${postId}">
                            <i class="ph ph-trash"></i> Delete</button>` : ''}
                    </div>
                </div>`;
            listEl.appendChild(item);
        });
        listEl.querySelectorAll('.delete-comment-btn').forEach(b => b.addEventListener('click', handleDeleteComment));
    }

    async function handlePostComment(e) {
        const btn = e.currentTarget;
        const postId = btn.dataset.postId;
        const ta = feedWrapper.querySelector(`.comment-input[data-post-id="${postId}"]`);
        if (!ta) return;
        const text = ta.value.trim();
        if (!text) return;
        btn.disabled = true; ta.disabled = true;
        const { error } = await supabaseClient.from('community_comments')
            .insert({ post_id: postId, author_id: currentUserId, content: text });
        btn.disabled = false; ta.disabled = false;
        if (error) {
            if (typeof showToast === 'function') {
                showToast('Comment Error', error.message, 'error');
            } else {
                alert('Could not post comment: ' + error.message);
            }
        } else {
            ta.value = '';
            await loadComments(postId);
            updateCommentCount(postId, 1);
        }
    }

    async function handleDeleteComment(e) {
        const btn = e.currentTarget;
        const commentId = btn.dataset.id;
        const postId = btn.dataset.postId;
        const item = btn.closest('.comment-item');

        const proceedCommentDelete = async () => {
            item.style.opacity = '0'; item.style.transition = 'opacity 0.2s';
            const { error } = await supabaseClient.from('community_comments').delete().eq('id', commentId);
            if (error) {
                if (typeof showToast === 'function') {
                    showToast('Delete Error', error.message, 'error');
                } else {
                    alert('Could not delete: ' + error.message);
                }
                item.style.opacity = '';
            } else {
                setTimeout(() => item.remove(), 200);
                updateCommentCount(postId, -1);
                const listEl = document.getElementById(`comments-list-${postId}`);
                if (listEl && listEl.querySelectorAll('.comment-item').length === 0) {
                    listEl.innerHTML = '<p class="no-comments-msg">No comments yet. Be the first!</p>';
                }
                if (typeof showToast === 'function') {
                    showToast('Comment Removed', 'Your comment has been deleted.', 'success');
                }
            }
        };

        if (typeof showConfirmModal === 'function') {
            showConfirmModal({
                title: 'Delete Comment',
                message: 'Delete this comment? This action cannot be undone.',
                confirmText: 'Delete',
                danger: true,
                onConfirm: proceedCommentDelete
            });
        } else {
            if (confirm('Delete this comment?')) proceedCommentDelete();
        }
    }

    function updateCommentCount(postId, delta) {
        const card = feedWrapper.querySelector(`.feed-post-card[data-post-id="${postId}"]`);
        if (!card) return;
        const el = card.querySelector('.comment-toggle-btn .comment-count');
        if (el) el.textContent = Math.max(0, (parseInt(el.textContent) || 0) + delta);
    }

    /* ══════════════════════════════════════════════
       CREATE POST (with optional image)
    ══════════════════════════════════════════════ */
    async function handlePost() {
        const text = postTextarea?.value.trim();
        if (!text && !selectedImageFile) return;
        if (!postBtn) return;

        postBtn.disabled = true;
        postBtn.innerHTML = '<i class="ph ph-circle-notch" style="animation:spin 0.8s linear infinite"></i> Posting…';

        let imageUrl = null;
        if (selectedImageFile) {
            try {
                imageUrl = await uploadImage(selectedImageFile);
            } catch (err) {
                if (typeof showToast === 'function') {
                    showToast('Upload Error', 'Image upload failed: ' + err.message, 'error');
                } else {
                    alert('Image upload failed: ' + err.message);
                }
                postBtn.disabled = false;
                postBtn.innerHTML = '<i class="ph ph-paper-plane-tilt"></i> Post';
                return;
            }
        }

        const payload = { author_id: currentUserId, content: text || '' };
        if (imageUrl) payload.image_url = imageUrl;

        const { error } = await supabaseClient.from('community_posts').insert(payload);

        postBtn.disabled = false;
        postBtn.innerHTML = '<i class="ph ph-paper-plane-tilt"></i> Post';

        if (error) {
            if (typeof showToast === 'function') {
                showToast('Post Error', 'Failed to post: ' + error.message, 'error');
            } else {
                alert('Failed to post: ' + error.message);
            }
        } else {
            postTextarea.value = '';
            selectedImageFile = null;
            imageInput.value = '';
            imagePreview.src = '';
            imagePreviewWrap.style.display = 'none';
            if (typeof showToast === 'function') {
                showToast('Post Shared', 'Your message has been published to the community!', 'success');
            }
            loadPosts();
        }
    }

    if (postBtn) postBtn.addEventListener('click', handlePost);
    if (postTextarea) {
        postTextarea.addEventListener('keydown', e => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); handlePost(); }
        });
        // Auto-expand textarea
        postTextarea.addEventListener('input', () => {
            postTextarea.style.height = 'auto';
            postTextarea.style.height = postTextarea.scrollHeight + 'px';
        });
    }

    if (refreshBtn) refreshBtn.addEventListener('click', smartRefresh);

    if (closeBanner) {
        closeBanner.addEventListener('click', () => {
            smartBanner.style.display = 'none';
        });
    }

    /* ── Search & Filter Listeners ── */
    const searchInput = document.getElementById('community-search-input');
    if (searchInput) {
        searchInput.addEventListener('input', e => {
            currentSearchQuery = e.target.value;
            filterPosts();
        });
    }

    // Category filter tabs
    document.querySelectorAll('.comm-filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.comm-filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentCategoryFilter = tab.dataset.filter || 'all';
            filterPosts();
        });
    });

    // Quick tag chips in composer
    document.querySelectorAll('.quick-tag-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const tag = chip.dataset.tag;
            if (!tag || !postTextarea) return;
            const currentVal = postTextarea.value;
            postTextarea.value = currentVal ? `${currentVal.trim()} ${tag} ` : `${tag} `;
            postTextarea.focus();
            postTextarea.style.height = 'auto';
            postTextarea.style.height = postTextarea.scrollHeight + 'px';
        });
    });

    // Trending topic chips in sidebar
    document.querySelectorAll('.trending-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const term = chip.dataset.search || chip.textContent.trim();
            if (searchInput) searchInput.value = term;
            currentSearchQuery = term;
            filterPosts();
            feedWrapper?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    });

    /* ── Realtime subscriptions ──────────────────── */
    supabaseClient.channel('community_realtime')
        .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'community_posts' }, () => loadPosts())
        .on('postgres_changes', { event: 'DELETE', schema: 'public', table: 'community_posts' }, () => loadPosts())
        .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'community_comments' }, payload => {
            const postId = payload.new?.post_id;
            if (!postId) return;
            const section = document.getElementById(`comments-${postId}`);
            if (section?.classList.contains('open')) loadComments(postId);
            updateCommentCount(postId, 1);
        })
        .on('postgres_changes', { event: 'DELETE', schema: 'public', table: 'community_comments' }, payload => {
            const postId = payload.old?.post_id;
            if (!postId) return;
            const section = document.getElementById(`comments-${postId}`);
            if (section?.classList.contains('open')) loadComments(postId);
            updateCommentCount(postId, -1);
        })
        .subscribe();

    /* ── Initial load ────────────────────────────── */
    loadPosts();
}

document.addEventListener('DOMContentLoaded', () => {
    if (supabaseClient) initCommunity();
    else window.addEventListener('supabase-ready', initCommunity);
});

/* spin keyframe (used inline) */
const _spinStyle = document.createElement('style');
_spinStyle.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
document.head.appendChild(_spinStyle);
