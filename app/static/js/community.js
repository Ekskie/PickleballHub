/**
 * community.js
 * Handles posts, likes, comments and realtime updates for the Community page.
 * Works across all role dashboards (adminstaff, player, clubadmin, owner, facilitystaff, superadmin).
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!supabaseClient) {
        console.error('[Community] Supabase client not initialised.');
        return;
    }

    /* ── DOM refs ────────────────────────────────────── */
    const feedWrapper     = document.getElementById('community-feed-wrapper');
    const postTextarea    = document.getElementById('post-textarea');
    const postBtn         = document.getElementById('btn-post');
    const postsCountEl    = document.getElementById('posts-count-label');
    const currentAvatarEl = document.getElementById('current-user-avatar');

    /* ── Helpers ─────────────────────────────────────── */
    function escapeHTML(str = '') {
        return String(str).replace(/[&<>'"]/g, t => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
        }[t]));
    }

    function timeAgo(isoString) {
        const diffMs   = Date.now() - new Date(isoString).getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHrs  = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHrs / 24);
        if (diffMins < 1)  return 'just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHrs < 24)  return `${diffHrs}h ago`;
        if (diffDays < 7)  return `${diffDays}d ago`;
        return new Date(isoString).toLocaleDateString();
    }

    function initials(firstName = '?', lastName = '') {
        return ((firstName[0] || '') + (lastName[0] || '')).toUpperCase() || '?';
    }

    /* ── Bootstrap current-user avatar ──────────────── */
    (async () => {
        if (!currentUserId || !currentAvatarEl) return;
        try {
            const { data } = await supabaseClient
                .from('profiles')
                .select('first_name, last_name')
                .eq('id', currentUserId)
                .single();
            if (data) {
                currentAvatarEl.textContent = initials(data.first_name, data.last_name);
            }
        } catch (_) {}
    })();

    /* ══════════════════════════════════════════════════
       POSTS
    ══════════════════════════════════════════════════ */
    async function loadPosts() {
        const { data: posts, error } = await supabaseClient
            .from('community_posts')
            .select(`
                *,
                author:profiles!community_posts_author_id_fkey(first_name, last_name, role),
                post_likes(profile_id),
                community_comments(id)
            `)
            .order('created_at', { ascending: false });

        if (error) {
            console.error('[Community] Error loading posts:', error);
            feedWrapper.innerHTML = `
                <div class="community-empty">
                    <i class="ph ph-warning-circle"></i>
                    <p>Could not load posts. Please try refreshing.</p>
                </div>`;
            return;
        }

        renderPosts(posts);
        if (postsCountEl) {
            postsCountEl.textContent = `${posts.length} post${posts.length !== 1 ? 's' : ''}`;
        }
    }

    function renderPosts(posts) {
        feedWrapper.innerHTML = '';

        if (!posts || posts.length === 0) {
            feedWrapper.innerHTML = `
                <div class="community-empty">
                    <i class="ph ph-chats-circle"></i>
                    <p>No posts yet — be the first to share something!</p>
                </div>`;
            return;
        }

        posts.forEach(post => {
            const author      = post.author || {};
            const postInitials = initials(author.first_name, author.last_name);
            const fullName    = `${author.first_name || 'Unknown'} ${author.last_name || ''}`.trim();
            const role        = author.role ? author.role.replace(/_/g, ' ') : '';
            const hasLiked    = post.post_likes?.some(l => l.profile_id === currentUserId);
            const likesCount  = post.post_likes?.length ?? 0;
            const commentsCount = post.community_comments?.length ?? 0;
            const isOwner     = post.author_id === currentUserId;
            const canDelete   = isOwner; // JS-side guard; DB RLS handles admin deletion too

            const card = document.createElement('div');
            card.className = 'feed-post-card';
            card.dataset.postId = post.id;

            card.innerHTML = `
                <div class="feed-post-header">
                    <div class="feed-avatar">${escapeHTML(postInitials)}</div>
                    <div class="feed-post-meta">
                        <h4>${escapeHTML(fullName)}${role ? `<span class="author-role">(${escapeHTML(role)})</span>` : ''}</h4>
                        <span class="post-time"><i class="ph ph-clock"></i>${timeAgo(post.created_at)}</span>
                    </div>
                    ${canDelete ? `
                    <button class="delete-post-btn" title="Delete post" data-id="${post.id}">
                        <i class="ph ph-trash"></i>
                    </button>` : ''}
                </div>

                <p class="feed-post-body">${escapeHTML(post.content)}</p>

                <div class="feed-post-footer">
                    <button class="feed-action like-btn ${hasLiked ? 'liked' : ''}" data-id="${post.id}">
                        <i class="ph ${hasLiked ? 'ph-fill ph-thumbs-up' : 'ph-thumbs-up'}"></i>
                        <span class="like-count">${likesCount}</span>
                    </button>
                    <button class="feed-action comment-toggle-btn" data-id="${post.id}">
                        <i class="ph ph-chat-circle"></i>
                        <span class="comment-count">${commentsCount}</span>
                        comment${commentsCount !== 1 ? 's' : ''}
                    </button>
                </div>

                <!-- Comment Section (collapsed by default) -->
                <div class="comment-section" id="comments-${post.id}">
                    <div class="comment-input-row">
                        <div class="comment-avatar" id="ca-${post.id}">?</div>
                        <div class="comment-input-wrap">
                            <textarea
                                class="comment-input"
                                placeholder="Write a comment…"
                                rows="1"
                                data-post-id="${post.id}"
                            ></textarea>
                            <button class="btn-comment-send" data-post-id="${post.id}" title="Send comment">
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

            // Set current-user initials in the comment avatar
            if (currentAvatarEl) {
                const caEl = card.querySelector(`#ca-${post.id}`);
                if (caEl) caEl.textContent = currentAvatarEl.textContent || '?';
            }
        });

        /* ── Bind events ── */
        feedWrapper.querySelectorAll('.like-btn').forEach(btn =>
            btn.addEventListener('click', handleLike)
        );
        feedWrapper.querySelectorAll('.delete-post-btn').forEach(btn =>
            btn.addEventListener('click', handleDeletePost)
        );
        feedWrapper.querySelectorAll('.comment-toggle-btn').forEach(btn =>
            btn.addEventListener('click', handleToggleComments)
        );
        feedWrapper.querySelectorAll('.btn-comment-send').forEach(btn =>
            btn.addEventListener('click', handlePostComment)
        );
        // Allow Ctrl+Enter in comment textarea
        feedWrapper.querySelectorAll('.comment-input').forEach(ta => {
            ta.addEventListener('keydown', e => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    const postId = ta.dataset.postId;
                    const sendBtn = feedWrapper.querySelector(`.btn-comment-send[data-post-id="${postId}"]`);
                    if (sendBtn) sendBtn.click();
                }
            });
        });
    }

    /* ── Like ────────────────────────────────────────── */
    async function handleLike(e) {
        const btn    = e.currentTarget;
        const postId = btn.dataset.id;
        const liked  = btn.classList.contains('liked');

        // Optimistic UI
        const icon      = btn.querySelector('i');
        const countSpan = btn.querySelector('.like-count');
        const current   = parseInt(countSpan.textContent) || 0;

        if (liked) {
            btn.classList.remove('liked');
            icon.className = 'ph ph-thumbs-up';
            countSpan.textContent = Math.max(0, current - 1);
            await supabaseClient.from('post_likes')
                .delete().eq('post_id', postId).eq('profile_id', currentUserId);
        } else {
            btn.classList.add('liked');
            icon.className = 'ph ph-fill ph-thumbs-up';
            countSpan.textContent = current + 1;
            await supabaseClient.from('post_likes')
                .insert({ post_id: postId, profile_id: currentUserId });
        }
    }

    /* ── Delete post ─────────────────────────────────── */
    async function handleDeletePost(e) {
        if (!confirm('Delete this post and all its comments?')) return;
        const btn    = e.currentTarget;
        const postId = btn.dataset.id;
        const card   = btn.closest('.feed-post-card');

        // Animate out
        card.style.opacity = '0';
        card.style.transform = 'scale(0.97)';
        card.style.transition = 'opacity 0.2s, transform 0.2s';

        const { error } = await supabaseClient
            .from('community_posts').delete().eq('id', postId);

        if (error) {
            alert('Could not delete post: ' + error.message);
            card.style.opacity = '';
            card.style.transform = '';
        } else {
            setTimeout(() => card.remove(), 200);
            // Update count
            if (postsCountEl) {
                const n = Math.max(0, parseInt(postsCountEl.textContent) - 1);
                postsCountEl.textContent = `${n} post${n !== 1 ? 's' : ''}`;
            }
        }
    }

    /* ── Toggle comment section ──────────────────────── */
    function handleToggleComments(e) {
        const btn    = e.currentTarget;
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

    /* ══════════════════════════════════════════════════
       COMMENTS
    ══════════════════════════════════════════════════ */
    async function loadComments(postId) {
        const listEl = document.getElementById(`comments-list-${postId}`);
        if (!listEl) return;

        listEl.innerHTML = '<p class="comments-loading">Loading comments…</p>';

        const { data: comments, error } = await supabaseClient
            .from('community_comments')
            .select(`
                *,
                author:profiles!community_comments_author_id_fkey(first_name, last_name, role)
            `)
            .eq('post_id', postId)
            .order('created_at', { ascending: true });

        if (error) {
            listEl.innerHTML = '<p class="no-comments-msg">Could not load comments.</p>';
            return;
        }

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
            const author   = c.author || {};
            const ini      = initials(author.first_name, author.last_name);
            const fullName = `${author.first_name || 'Unknown'} ${author.last_name || ''}`.trim();
            const role     = author.role ? author.role.replace(/_/g, ' ') : '';
            const canDel   = c.author_id === currentUserId;

            const item = document.createElement('div');
            item.className = 'comment-item';
            item.dataset.commentId = c.id;
            item.innerHTML = `
                <div class="comment-avatar">${escapeHTML(ini)}</div>
                <div class="comment-body-wrap">
                    <div class="comment-author-name">
                        ${escapeHTML(fullName)}
                        ${role ? `<span class="comment-role">(${escapeHTML(role)})</span>` : ''}
                    </div>
                    <p class="comment-text">${escapeHTML(c.content)}</p>
                    <div class="comment-meta-row">
                        <span class="comment-time"><i class="ph ph-clock"></i> ${timeAgo(c.created_at)}</span>
                        ${canDel ? `
                        <button class="delete-comment-btn" data-id="${c.id}" data-post-id="${postId}">
                            <i class="ph ph-trash"></i> Delete
                        </button>` : ''}
                    </div>
                </div>
            `;
            listEl.appendChild(item);
        });

        listEl.querySelectorAll('.delete-comment-btn').forEach(btn =>
            btn.addEventListener('click', handleDeleteComment)
        );
    }

    /* ── Post a comment ──────────────────────────────── */
    async function handlePostComment(e) {
        const btn    = e.currentTarget;
        const postId = btn.dataset.postId;
        const ta     = feedWrapper.querySelector(`.comment-input[data-post-id="${postId}"]`);
        if (!ta) return;

        const text = ta.value.trim();
        if (!text) return;

        btn.disabled = true;
        ta.disabled  = true;

        const { error } = await supabaseClient
            .from('community_comments')
            .insert({ post_id: postId, author_id: currentUserId, content: text });

        btn.disabled = false;
        ta.disabled  = false;

        if (error) {
            alert('Could not post comment: ' + error.message);
        } else {
            ta.value = '';
            // Reload comments list for this post
            await loadComments(postId);
            // Update comment count badge on the toggle button
            updateCommentCount(postId, 1);
        }
    }

    /* ── Delete a comment ────────────────────────────── */
    async function handleDeleteComment(e) {
        if (!confirm('Delete this comment?')) return;
        const btn       = e.currentTarget;
        const commentId = btn.dataset.id;
        const postId    = btn.dataset.postId;
        const item      = btn.closest('.comment-item');

        item.style.opacity = '0';
        item.style.transition = 'opacity 0.2s';

        const { error } = await supabaseClient
            .from('community_comments').delete().eq('id', commentId);

        if (error) {
            alert('Could not delete comment: ' + error.message);
            item.style.opacity = '';
        } else {
            setTimeout(() => item.remove(), 200);
            updateCommentCount(postId, -1);
            // If list now empty, show message
            const listEl = document.getElementById(`comments-list-${postId}`);
            if (listEl && listEl.querySelectorAll('.comment-item').length === 0) {
                listEl.innerHTML = '<p class="no-comments-msg">No comments yet. Be the first!</p>';
            }
        }
    }

    /* ── Update comment badge count ──────────────────── */
    function updateCommentCount(postId, delta) {
        const card = feedWrapper.querySelector(`.feed-post-card[data-post-id="${postId}"]`);
        if (!card) return;
        const countEl = card.querySelector('.comment-toggle-btn .comment-count');
        if (countEl) {
            const n = Math.max(0, (parseInt(countEl.textContent) || 0) + delta);
            countEl.textContent = n;
        }
    }

    /* ── Post new post ───────────────────────────────── */
    async function handlePost() {
        const text = postTextarea?.value.trim();
        if (!text || !postBtn) return;

        postBtn.disabled = true;
        postBtn.innerHTML = '<i class="ph ph-circle-notch" style="animation:spin 0.8s linear infinite"></i> Posting…';

        const { error } = await supabaseClient
            .from('community_posts')
            .insert({ content: text, author_id: currentUserId });

        postBtn.disabled = false;
        postBtn.innerHTML = '<i class="ph ph-paper-plane-tilt"></i> Post';

        if (error) {
            alert('Failed to post: ' + error.message);
        } else {
            postTextarea.value = '';
            loadPosts();
        }
    }

    if (postBtn) postBtn.addEventListener('click', handlePost);

    // Also allow Ctrl+Enter in the main post textarea
    if (postTextarea) {
        postTextarea.addEventListener('keydown', e => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                handlePost();
            }
        });
    }

    /* ── Realtime subscriptions ──────────────────────── */
    supabaseClient.channel('community_realtime')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'community_posts' }, () => {
            loadPosts();
        })
        .on('postgres_changes', { event: '*', schema: 'public', table: 'post_likes' }, payload => {
            // For likes we do optimistic UI, so just refresh
            loadPosts();
        })
        .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'community_comments' }, payload => {
            const postId = payload.new?.post_id;
            if (!postId) return;
            // If the comment section for this post is open, reload it
            const section = document.getElementById(`comments-${postId}`);
            if (section?.classList.contains('open')) {
                loadComments(postId);
            }
            // Update badge
            updateCommentCount(postId, 1);
        })
        .on('postgres_changes', { event: 'DELETE', schema: 'public', table: 'community_comments' }, payload => {
            const postId = payload.old?.post_id;
            if (!postId) return;
            const section = document.getElementById(`comments-${postId}`);
            if (section?.classList.contains('open')) {
                loadComments(postId);
            }
            updateCommentCount(postId, -1);
        })
        .subscribe();

    /* ── Initial load ────────────────────────────────── */
    loadPosts();
});
