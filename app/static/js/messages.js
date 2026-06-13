/**
 * messages.js
 * Full-featured messaging with:
 *  - Sender name labels on each message bubble
 *  - Unread / read state (bold highlight on conversation list like Messenger)
 *  - Mark-as-read when conversation is opened
 *  - Read-receipt tick icons on sent messages
 *  - Date separators between day groups
 *  - Inline conversation filter search
 *  - Realtime updates via Supabase
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!supabaseClient) {
        console.error('[Messages] Supabase client not initialised.');
        return;
    }

    /* ── DOM refs ─────────────────────────────────────── */
    const contactsList      = document.getElementById('contactsList');
    const contactsSearch    = document.getElementById('contactsSearch');
    const chatMessages      = document.getElementById('chatMessages');
    const chatPlaceholder   = document.getElementById('chatPlaceholder');
    const chatHeader        = document.getElementById('chatHeader');
    const chatHeaderAvatar  = document.getElementById('chatHeaderAvatar');
    const chatHeaderName    = document.getElementById('chatHeaderName');
    const chatHeaderRole    = document.getElementById('chatHeaderRole');
    const chatInputWrap     = document.getElementById('chatInputWrap');
    const msgInput          = document.getElementById('msgInput');
    const sendMsgBtn        = document.getElementById('sendMsgBtn');
    const newChatBtn        = document.getElementById('newChatBtn');
    const newChatModal      = document.getElementById('newChatModal');
    const modalCloseBtn     = document.getElementById('modalCloseBtn');
    const userSearchInput   = document.getElementById('userSearchInput');
    const userSearchResults = document.getElementById('userSearchResults');

    /* ── State ────────────────────────────────────────── */
    let activeConversationId  = null;
    let activeOtherUser       = null;   // { id, name, role, initials, avatar_url }
    let searchDebounce        = null;
    let allConversations      = [];     // cached for inline filter
    let latestMsgMap          = {};
    let unreadMap             = {};     // convoId → unread count (messages not sent by me, read_at null)

    /* ── Helpers ──────────────────────────────────────── */
    function esc(str) {
        return (str || '').replace(/[&<>'"]/g, t =>
            ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[t] || t));
    }

    function timeAgo(isoStr) {
        const diff = Date.now() - new Date(isoStr).getTime();
        const m = Math.floor(diff / 60000);
        if (m < 1)  return 'just now';
        if (m < 60) return `${m}m`;
        const h = Math.floor(m / 60);
        if (h < 24) return `${h}h`;
        const d = Math.floor(h / 24);
        if (d < 7)  return `${d}d`;
        return new Date(isoStr).toLocaleDateString([], { month: 'short', day: 'numeric' });
    }

    function fullTime(isoStr) {
        return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function dateSep(isoStr) {
        const d = new Date(isoStr);
        const today = new Date();
        const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
        if (d.toDateString() === today.toDateString())     return 'Today';
        if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
        return d.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
    }

    function initials(first = '', last = '') {
        return ((first[0] || '') + (last[0] || '')).toUpperCase() || '?';
    }

    function capitalise(str = '') {
        return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, ' ');
    }

    /* ── Show chat window ─────────────────────────────── */
    function showChat(user) {
        chatPlaceholder.style.display  = 'none';
        chatHeader.style.display       = 'flex';
        chatMessages.style.display     = 'flex';
        chatInputWrap.style.display    = 'flex';
        if (user.avatar_url) {
            chatHeaderAvatar.innerHTML = `<img src="${esc(user.avatar_url)}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;">`;
        } else {
            chatHeaderAvatar.textContent = user.initials;
        }
        chatHeaderName.textContent     = user.name;
        chatHeaderRole.textContent     = user.role ? capitalise(user.role) : '';
    }

    /* ══════════════════════════════════════════════════
       LOAD CONVERSATIONS
    ══════════════════════════════════════════════════ */
    async function loadConversations() {
        if (!contactsList) return;

        const { data: mine, error: mErr } = await supabaseClient
            .from('conversation_participants')
            .select('conversation_id')
            .eq('profile_id', currentUserId);

        if (mErr || !mine || mine.length === 0) {
            renderEmptyContacts();
            return;
        }

        const ids = mine.map(r => r.conversation_id);
        
        // Fetch which conversation IDs are matchmaking lobbies to exclude them
        let privateIds = ids;
        try {
            const { data: lobbies } = await supabaseClient
                .from('matchmaker_lobbies')
                .select('id')
                .in('id', ids);
            
            if (lobbies && lobbies.length > 0) {
                const lobbyIds = new Set(lobbies.map(l => l.id));
                privateIds = ids.filter(id => !lobbyIds.has(id));
            }
        } catch (filterErr) {
            console.error('[Messages] error filtering lobby conversations:', filterErr);
        }

        if (privateIds.length === 0) {
            renderEmptyContacts();
            return;
        }

        // Fetch the OTHER participant with their profile
        const { data: others, error: oErr } = await supabaseClient
            .from('conversation_participants')
            .select(`
                conversation_id,
                profiles!conversation_participants_profile_id_fkey(id, first_name, last_name, role, avatar_url)
            `)
            .in('conversation_id', privateIds)
            .neq('profile_id', currentUserId);

        if (oErr) { console.error('[Messages] loadConversations:', oErr); return; }

        // Latest message per conversation (snippet + timestamp)
        const { data: latestMsgs } = await supabaseClient
            .from('messages')
            .select('conversation_id, content, created_at, sender_id, read_at')
            .in('conversation_id', privateIds)
            .order('created_at', { ascending: false });

        latestMsgMap = {};
        (latestMsgs || []).forEach(m => {
            if (!latestMsgMap[m.conversation_id]) latestMsgMap[m.conversation_id] = m;
        });

        // Count unread: messages NOT sent by me AND read_at IS NULL
        unreadMap = {};
        (latestMsgs || []).forEach(m => {
            if (m.sender_id !== currentUserId && !m.read_at) {
                unreadMap[m.conversation_id] = (unreadMap[m.conversation_id] || 0) + 1;
            }
        });

        // Sort conversations: most recent first
        allConversations = (others || []).sort((a, b) => {
            const ta = latestMsgMap[a.conversation_id]?.created_at || '';
            const tb = latestMsgMap[b.conversation_id]?.created_at || '';
            return tb.localeCompare(ta);
        });

        renderContacts(allConversations);
    }

    function renderEmptyContacts() {
        contactsList.innerHTML = `
            <div class="contacts-empty">
                <i class="ph ph-chats"></i>
                No conversations yet.<br>Tap <strong>+</strong> to start one.
            </div>`;
    }

    function renderContacts(convos) {
        contactsList.innerHTML = '';

        if (!convos || convos.length === 0) {
            renderEmptyContacts();
            return;
        }

        convos.forEach(row => {
            const p = row.profiles;
            if (!p) return;

            const name    = `${p.first_name || ''} ${p.last_name || ''}`.trim();
            const ini     = initials(p.first_name, p.last_name);
            const avatarUrl = p.avatar_url || null;
            const latest  = latestMsgMap[row.conversation_id];
            const unread  = unreadMap[row.conversation_id] || 0;
            const isActive = activeConversationId === row.conversation_id;

            let snippet = 'No messages yet';
            if (latest) {
                const prefix = latest.sender_id === currentUserId ? 'You: ' : '';
                const text   = latest.content.slice(0, 38);
                snippet      = prefix + esc(text) + (latest.content.length > 38 ? '…' : '');
            }
            const time = latest ? timeAgo(latest.created_at) : '';

            const classes = [
                'contact-item',
                isActive ? 'active' : '',
                (unread > 0 && !isActive) ? 'unread' : ''
            ].filter(Boolean).join(' ');

            const avatarHtml = avatarUrl
                ? `<div class="contact-avatar" style="overflow:hidden;"><img src="${esc(avatarUrl)}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;"></div>`
                : `<div class="contact-avatar">${esc(ini)}</div>`;

            const item = document.createElement('div');
            item.className = classes;
            item.dataset.convoId = row.conversation_id;
            item.innerHTML = `
                ${avatarHtml}
                <div class="contact-info">
                    <p class="contact-name">${esc(name)}</p>
                    <p class="contact-snippet">${snippet}</p>
                </div>
                <div class="contact-meta">
                    <span class="contact-time">${esc(time)}</span>
                    ${unread > 0 && !isActive
                        ? `<span class="unread-badge">${unread > 99 ? '99+' : unread}</span>`
                        : ''}
                </div>`;

            item.addEventListener('click', () =>
                openConversation(row.conversation_id, {
                    id: p.id, name, role: p.role, initials: ini, avatar_url: avatarUrl
                })
            );
            contactsList.appendChild(item);
        });
    }

    /* ── Inline filter ────────────────────────────────── */
    contactsSearch?.addEventListener('input', e => {
        const q = e.target.value.trim().toLowerCase();
        if (!q) { renderContacts(allConversations); return; }
        const filtered = allConversations.filter(row => {
            const p = row.profiles;
            if (!p) return false;
            const name = `${p.first_name || ''} ${p.last_name || ''}`.toLowerCase();
            return name.includes(q);
        });
        renderContacts(filtered);
    });

    /* ══════════════════════════════════════════════════
       OPEN A CONVERSATION
    ══════════════════════════════════════════════════ */
    function highlightActiveContact(convoId) {
        const items = contactsList.querySelectorAll('.contact-item');
        items.forEach(item => {
            if (item.dataset.convoId === convoId) {
                item.classList.add('active');
                item.classList.remove('unread');
                const badge = item.querySelector('.unread-badge');
                if (badge) badge.remove();
            } else {
                item.classList.remove('active');
            }
        });
    }

    function showLoader() {
        chatMessages.innerHTML = `
            <div class="chat-loading">
                <i class="ph ph-spinner"></i>
                <p>Loading messages...</p>
            </div>`;
    }

    async function openConversation(convoId, user) {
        activeConversationId = convoId;
        activeOtherUser      = user;
        
        // Highlight active contact immediately and show loading spinner
        highlightActiveContact(convoId);
        showChat(user);
        showLoader();

        await markAsRead(convoId);
        await loadMessages(convoId);
        loadConversations(); // refresh sidebar (clear unread badge)
    }

    /* ══════════════════════════════════════════════════
       MARK AS READ
    ══════════════════════════════════════════════════ */
    async function markAsRead(convoId) {
        // Mark all messages in this conversation (not sent by me) where read_at is null
        const now = new Date().toISOString();
        await supabaseClient
            .from('messages')
            .update({ read_at: now })
            .eq('conversation_id', convoId)
            .neq('sender_id', currentUserId)
            .is('read_at', null);
    }

    /* ══════════════════════════════════════════════════
       LOAD MESSAGES
    ══════════════════════════════════════════════════ */
    async function loadMessages(convoId = activeConversationId) {
        if (!convoId) return;

        const { data: msgs, error } = await supabaseClient
            .from('messages')
            .select(`
                *,
                sender:profiles!messages_sender_id_fkey(first_name, last_name)
            `)
            .eq('conversation_id', convoId)
            .order('created_at', { ascending: true });

        if (error) { console.error('[Messages] loadMessages:', error); return; }
        
        if (activeConversationId === convoId) {
            renderMessages(msgs || []);
        }
    }

    function renderMessages(msgs) {
        chatMessages.innerHTML = '';
        if (msgs.length === 0) {
            chatMessages.innerHTML = `
                <div style="text-align:center;color:var(--text-muted);font-size:0.85rem;margin:auto;">
                    No messages yet. Say hi! 👋
                </div>`;
            chatMessages.scrollTop = chatMessages.scrollHeight;
            return;
        }

        let lastDate  = '';
        let lastSender = '';
        let currentGroup = null;

        msgs.forEach((msg, idx) => {
            const isMine   = msg.sender_id === currentUserId;
            const msgDate  = dateSep(msg.created_at);
            const senderFull = msg.sender
                ? `${msg.sender.first_name || ''} ${msg.sender.last_name || ''}`.trim()
                : 'Unknown';

            // Date separator
            if (msgDate !== lastDate) {
                const sep = document.createElement('div');
                sep.className = 'msg-date-sep';
                sep.textContent = msgDate;
                chatMessages.appendChild(sep);
                lastDate   = msgDate;
                lastSender = '';   // reset group on new day
                currentGroup = null;
            }

            // Start a new group if sender changed
            const senderKey = msg.sender_id;
            if (senderKey !== lastSender || !currentGroup) {
                currentGroup = document.createElement('div');
                currentGroup.className = `msg-group ${isMine ? 'sent' : 'received'}`;

                // Sender label (only on received messages)
                if (!isMine) {
                    const label = document.createElement('div');
                    label.className = 'msg-sender-label';
                    label.textContent = senderFull;
                    currentGroup.appendChild(label);
                }

                chatMessages.appendChild(currentGroup);
                lastSender = senderKey;
            }

            // Bubble + meta
            const wrap = document.createElement('div');
            wrap.className = `msg-bubble-wrap ${isMine ? 'sent' : 'received'}`;

            const isRead = !!msg.read_at;
            const tickIcon = isMine
                ? `<span class="msg-read-status ${isRead ? 'read' : 'sent-ok'}" title="${isRead ? 'Read' : 'Sent'}">
                       ${isRead ? '✓✓' : '✓'}
                   </span>`
                : '';

            wrap.innerHTML = `
                <div class="msg-bubble ${isMine ? 'sent' : 'received'}">${esc(msg.content)}</div>
                <div class="msg-meta">
                    <span class="msg-time">${fullTime(msg.created_at)}</span>
                    ${tickIcon}
                </div>`;
            currentGroup.appendChild(wrap);
        });

        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    /* ══════════════════════════════════════════════════
       SEND MESSAGE
    ══════════════════════════════════════════════════ */
    async function sendMessage() {
        if (!activeConversationId) return;
        const text = msgInput.value.trim();
        if (!text) return;

        sendMsgBtn.disabled = true;
        msgInput.value = '';

        const { error } = await supabaseClient.from('messages').insert({
            conversation_id: activeConversationId,
            sender_id:       currentUserId,
            content:         text
        });

        sendMsgBtn.disabled = false;

        if (error) {
            console.error('[Messages] sendMessage:', error);
            msgInput.value = text; // restore on failure
        }
        // Realtime will refresh the chat automatically
    }

    /* ══════════════════════════════════════════════════
       NEW CHAT MODAL
    ══════════════════════════════════════════════════ */
    function openModal() {
        newChatModal.classList.add('open');
        userSearchInput.value = '';
        userSearchResults.innerHTML = '<p class="search-hint">Start typing to find a user...</p>';
        setTimeout(() => userSearchInput.focus(), 100);
    }

    function closeModal() { newChatModal.classList.remove('open'); }

    async function searchUsers(query) {
        if (!query || query.length < 2) {
            userSearchResults.innerHTML = '<p class="search-hint">Start typing to find a user...</p>';
            return;
        }
        userSearchResults.innerHTML = '<p class="search-hint">Searching…</p>';

        const { data: users, error } = await supabaseClient
            .from('profiles')
            .select('id, first_name, last_name, role, avatar_url')
            .neq('id', currentUserId)
            .or(`first_name.ilike.%${query}%,last_name.ilike.%${query}%`)
            .limit(12);

        if (error) {
            userSearchResults.innerHTML = '<p class="search-hint">Error searching users.</p>';
            return;
        }

        if (!users || users.length === 0) {
            userSearchResults.innerHTML = '<p class="search-hint">No users found.</p>';
            return;
        }

        userSearchResults.innerHTML = '';
        users.forEach(user => {
            const name      = `${user.first_name || ''} ${user.last_name || ''}`.trim();
            const ini       = initials(user.first_name, user.last_name);
            const roleLabel = user.role ? capitalise(user.role) : 'User';
            const avatarUrl = user.avatar_url || null;

            const avatarHtml = avatarUrl
                ? `<div class="user-result-avatar" style="overflow:hidden;"><img src="${esc(avatarUrl)}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;"></div>`
                : `<div class="user-result-avatar">${esc(ini)}</div>`;

            const item = document.createElement('div');
            item.className = 'user-result-item';
            item.innerHTML = `
                ${avatarHtml}
                <div>
                    <div class="user-result-name">${esc(name)}</div>
                    <div class="user-result-role">${esc(roleLabel)}</div>
                </div>`;
            item.addEventListener('click', () => startConversationWith(user));
            userSearchResults.appendChild(item);
        });
    }

    /* ══════════════════════════════════════════════════
       GET OR CREATE CONVERSATION
    ══════════════════════════════════════════════════ */
    async function startConversationWith(targetUser) {
        closeModal();
        const ini      = initials(targetUser.first_name, targetUser.last_name);
        const name     = `${targetUser.first_name || ''} ${targetUser.last_name || ''}`.trim();
        const userObj  = { id: targetUser.id, name, role: targetUser.role, initials: ini, avatar_url: targetUser.avatar_url || null };

        // Check if conversation already exists
        const { data: mine } = await supabaseClient
            .from('conversation_participants')
            .select('conversation_id')
            .eq('profile_id', currentUserId);

        const myIds = (mine || []).map(r => r.conversation_id);

        if (myIds.length > 0) {
            const { data: shared } = await supabaseClient
                .from('conversation_participants')
                .select('conversation_id')
                .eq('profile_id', targetUser.id)
                .in('conversation_id', myIds);

            if (shared && shared.length > 0) {
                await openConversation(shared[0].conversation_id, userObj);
                return;
            }
        }

        // Create new conversation
        const { data: newConvo, error: convoErr } = await supabaseClient
            .from('conversations').insert({}).select().single();

        if (convoErr || !newConvo) {
            alert('Could not start conversation. Please try again.');
            return;
        }

        const { error: partErr } = await supabaseClient
            .from('conversation_participants')
            .insert([
                { conversation_id: newConvo.id, profile_id: currentUserId },
                { conversation_id: newConvo.id, profile_id: targetUser.id }
            ]);

        if (partErr) { alert('Could not start conversation. Please try again.'); return; }

        await openConversation(newConvo.id, userObj);
    }

    /* ══════════════════════════════════════════════════
       EVENT LISTENERS
    ══════════════════════════════════════════════════ */
    newChatBtn?.addEventListener('click', openModal);
    modalCloseBtn?.addEventListener('click', closeModal);
    newChatModal?.addEventListener('click', e => { if (e.target === newChatModal) closeModal(); });

    userSearchInput?.addEventListener('input', e => {
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(() => searchUsers(e.target.value.trim()), 300);
    });

    sendMsgBtn?.addEventListener('click', sendMessage);
    msgInput?.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    /* ══════════════════════════════════════════════════
       REALTIME
    ══════════════════════════════════════════════════ */
    supabaseClient.channel('messages_realtime')
        .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'messages' }, async payload => {
            const convoId = payload.new?.conversation_id;

            if (convoId === activeConversationId) {
                // Mark as read immediately if we're looking at this conversation
                if (payload.new.sender_id !== currentUserId) {
                    await markAsRead(convoId);
                }
                await loadMessages();
            }
            // Always refresh sidebar to update snippet + unread badge
            loadConversations();
        })
        .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'messages' }, payload => {
            // read_at was updated — refresh ticks + sidebar
            const convoId = payload.new?.conversation_id;
            if (convoId === activeConversationId) loadMessages();
            loadConversations();
        })
        .subscribe();

    /* ── Initial load ─────────────────────────────────── */
    loadConversations();
});
