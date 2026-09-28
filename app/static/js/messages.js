/**
 * messages.js — Sports Platform 2.0 Direct Messaging & Realtime Chat
 * Features:
 *  - Instant Optimistic UI (0ms delay on sending, no refresh required)
 *  - Authenticated Supabase Realtime WebSocket (realtime.setAuth)
 *  - Smart Background Heartbeat Polling fallback (2.5s)
 *  - Dynamic sport avatar gradients
 *  - Role badges (Facility Staff, Club Captain, Owner, Player)
 *  - Real-time conversation filtering (All, Unread, Staff & Clubs, Players)
 *  - Search by player name and message text
 *  - Quick Court Reply chips for on-court messaging
 *  - Read-receipt tick icons (single/double check)
 *  - Date separators between day groups
 */
function initMessages() {
    if (!supabaseClient) {
        console.error('[Messages] Supabase client not initialised.');
        return;
    }

    /* ── DOM refs ─────────────────────────────────────── */
    const contactsList           = document.getElementById('contactsList');
    const contactsSearch         = document.getElementById('contactsSearch');
    const chatMessages           = document.getElementById('chatMessages');
    const chatPlaceholder        = document.getElementById('chatPlaceholder');
    const chatHeader             = document.getElementById('chatHeader');
    const chatHeaderAvatar       = document.getElementById('chatHeaderAvatar');
    const chatHeaderName         = document.getElementById('chatHeaderName');
    const chatHeaderRole         = document.getElementById('chatHeaderRole');
    const chatHeaderRoleBadge    = document.getElementById('chatHeaderRoleBadge');
    const chatInputWrap          = document.getElementById('chatInputWrap');
    const msgInput               = document.getElementById('msgInput');
    const sendMsgBtn             = document.getElementById('sendMsgBtn');
    const newChatBtn             = document.getElementById('newChatBtn');
    const heroNewChatBtn         = document.getElementById('heroNewChatBtn');
    const placeholderNewChatBtn  = document.getElementById('placeholderNewChatBtn');
    const newChatModal           = document.getElementById('newChatModal');
    const modalCloseBtn          = document.getElementById('modalCloseBtn');
    const userSearchInput        = document.getElementById('userSearchInput');
    const userSearchResults      = document.getElementById('userSearchResults');
    const chatBackBtn            = document.getElementById('chatBackBtn');
    const refreshChatBtn         = document.getElementById('refreshChatBtn');
    const closeChatBtn           = document.getElementById('closeChatBtn');
    const quickRepliesWrap       = document.getElementById('quickRepliesWrap');
    const convoCountPill         = document.getElementById('convoCountPill');
    const heroConvoCountText     = document.getElementById('heroConvoCountText');
    const cardQuickStaff         = document.getElementById('cardQuickStaff');
    const cardQuickClubs         = document.getElementById('cardQuickClubs');
    const cardQuickPlayers       = document.getElementById('cardQuickPlayers');

    /* ── State ────────────────────────────────────────── */
    let activeConversationId  = null;
    let activeOtherUser       = null;   // { id, name, role, initials, avatar_url }
    let searchDebounce        = null;
    let allConversations      = [];     // cached for inline filter
    let latestMsgMap          = {};
    let unreadMap             = {};     // convoId → unread count
    let allMessagesMap        = {};     // convoId → array of messages
    let currentFilter         = 'all';  // 'all' | 'unread' | 'staff' | 'players'
    let pollTimer             = null;   // background smart heartbeat

    /* ── Helpers ──────────────────────────────────────── */
    function esc(str) {
        return (str || '').replace(/[&<>'"]/g, t =>
            ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[t] || t));
    }

    function timeAgo(isoStr) {
        if (!isoStr) return '';
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
        if (!isoStr) return '';
        return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function dateSep(isoStr) {
        const d = new Date(isoStr);
        const today = new Date();
        const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
        if (d.toDateString() === today.toDateString())     return 'Today';
        if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
        return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
    }

    function initials(first, last) {
        const f = first || '';
        const l = last || '';
        return ((f[0] || '') + (l[0] || '')).toUpperCase() || '?';
    }

    function capitalise(str = '') {
        return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, ' ');
    }

    function getAvatarGradient(name = '') {
        const gradients = [
            'linear-gradient(135deg, #ff5722 0%, #ea580c 100%)',
            'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
            'linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%)',
            'linear-gradient(135deg, #10b981 0%, #059669 100%)',
            'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
            'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
        ];
        let hash = 0;
        for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
        return gradients[Math.abs(hash) % gradients.length];
    }

    function getRoleBadge(role = '') {
        if (!role) return '<span class="convo-role-badge badge-player"><i class="ph ph-tennis-ball"></i> Player</span>';
        const r = role.toLowerCase().replace(/_/g, '');
        if (r === 'adminstaff' || r === 'superadmin') {
            return `<span class="convo-role-badge badge-admin"><i class="ph ph-shield-check"></i> Admin</span>`;
        } else if (r === 'owner') {
            return `<span class="convo-role-badge badge-owner"><i class="ph ph-crown"></i> Owner</span>`;
        } else if (r === 'facilitystaff') {
            return `<span class="convo-role-badge badge-staff"><i class="ph ph-headset"></i> Staff</span>`;
        } else if (r === 'clubadmin') {
            return `<span class="convo-role-badge badge-club"><i class="ph ph-users"></i> Club</span>`;
        }
        return `<span class="convo-role-badge badge-player"><i class="ph ph-tennis-ball"></i> Player</span>`;
    }

    let cachedLobbyIdSet = null;

    async function getLobbyIdSet() {
        if (cachedLobbyIdSet) return cachedLobbyIdSet;
        try {
            const resp = await fetch('/auth/lobby-ids');
            if (resp.ok) {
                const data = await resp.json();
                cachedLobbyIdSet = new Set(data.lobby_ids || []);
                return cachedLobbyIdSet;
            }
        } catch (e) {
            console.warn('[Messages] Could not fetch lobby IDs:', e);
        }
        return new Set();
    }

    /* ── Show / Hide chat window ─────────────────────── */
    function showChat(user) {
        if (chatPlaceholder) chatPlaceholder.style.display = 'none';
        if (chatHeader) chatHeader.style.display = 'flex';
        if (chatMessages) chatMessages.style.display = 'flex';
        if (chatInputWrap) chatInputWrap.style.display = 'flex';
        if (quickRepliesWrap) quickRepliesWrap.style.display = 'flex';

        if (user.avatar_url) {
            chatHeaderAvatar.innerHTML = `<img src="${esc(user.avatar_url)}" style="width:100%;height:100%;object-fit:cover;">`;
            chatHeaderAvatar.style.background = '';
        } else {
            chatHeaderAvatar.innerHTML = esc(user.initials);
            chatHeaderAvatar.style.background = getAvatarGradient(user.name);
        }

        if (chatHeaderName) chatHeaderName.textContent = user.name;
        if (chatHeaderRoleBadge) chatHeaderRoleBadge.innerHTML = getRoleBadge(user.role);
        if (chatHeaderRole) {
            chatHeaderRole.innerHTML = `<span class="status-pulse-dot"></span> Active in PickleballHub`;
        }
    }

    function hideChat() {
        stopActivePolling();
        activeConversationId = null;
        activeOtherUser = null;
        if (chatPlaceholder) chatPlaceholder.style.display = 'flex';
        if (chatHeader) chatHeader.style.display = 'none';
        if (chatMessages) chatMessages.style.display = 'none';
        if (chatInputWrap) chatInputWrap.style.display = 'none';
        if (quickRepliesWrap) quickRepliesWrap.style.display = 'none';

        const layout = document.querySelector('.messages-layout');
        layout?.classList.remove('chat-active');

        if (contactsList) {
            contactsList.querySelectorAll('.contact-item').forEach(item => item.classList.remove('active'));
        }
    }

    function updateConvoCounters(total) {
        if (convoCountPill) convoCountPill.textContent = total;
        if (heroConvoCountText) {
            heroConvoCountText.textContent = `${total} conversation${total !== 1 ? 's' : ''}`;
        }
    }

    /* ── Smart Background Polling (Fallback for instant reliability) ── */
    function startActivePolling() {
        stopActivePolling();
        pollTimer = setInterval(async () => {
            if (activeConversationId) {
                // Check if any new message was inserted or updated
                const { data: latest } = await supabaseClient
                    .from('messages')
                    .select('id, created_at, read_at')
                    .eq('conversation_id', activeConversationId)
                    .order('created_at', { ascending: false })
                    .limit(1);

                const currentList = allMessagesMap[activeConversationId] || [];
                const currentLatest = currentList[currentList.length - 1];

                if (latest && latest.length > 0) {
                    const l = latest[0];
                    if (!currentLatest || currentLatest.id !== l.id || currentLatest.read_at !== l.read_at) {
                        await loadMessages(activeConversationId);
                        loadConversations();
                    }
                }
            } else {
                loadConversations();
            }
        }, 2500);
    }

    function stopActivePolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
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
            updateConvoCounters(0);
            return;
        }

        const ids = mine.map(r => r.conversation_id);

        // Exclude matchmaking lobbies via reliable server endpoint
        const lobbyIdSet = await getLobbyIdSet();
        const privateIds = ids.filter(id => !lobbyIdSet.has(id));

        if (privateIds.length === 0) {
            renderEmptyContacts();
            updateConvoCounters(0);
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

        if (oErr) {
            console.error('[Messages] loadConversations:', oErr);
            return;
        }

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

        updateConvoCounters(allConversations.length);
        applyFilter();
    }

    function renderEmptyContacts() {
        contactsList.innerHTML = `
            <div class="contacts-empty">
                <i class="ph ph-chats"></i>
                No conversations found.<br>Tap <strong>+</strong> or Start Conversation to message someone!
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

            const name      = `${p.first_name || ''} ${p.last_name || ''}`.trim() || 'Unknown User';
            const ini       = initials(p.first_name, p.last_name);
            const avatarUrl = p.avatar_url || null;
            const latest    = latestMsgMap[row.conversation_id];
            const unread    = unreadMap[row.conversation_id] || 0;
            const isActive  = activeConversationId === row.conversation_id;

            let snippet = 'No messages yet';
            if (latest) {
                const prefix = latest.sender_id === currentUserId ? 'You: ' : '';
                const text   = latest.content.slice(0, 36);
                snippet      = prefix + esc(text) + (latest.content.length > 36 ? '…' : '');
            }
            const time = latest ? timeAgo(latest.created_at) : '';

            const classes = [
                'contact-item',
                isActive ? 'active' : '',
                (unread > 0 && !isActive) ? 'unread' : ''
            ].filter(Boolean).join(' ');

            const avatarHtml = avatarUrl
                ? `<div class="contact-avatar"><img src="${esc(avatarUrl)}" style="width:100%;height:100%;object-fit:cover;"></div>`
                : `<div class="contact-avatar" style="background:${getAvatarGradient(name)}">${esc(ini)}</div>`;

            const item = document.createElement('div');
            item.className = classes;
            item.dataset.convoId = row.conversation_id;
            item.innerHTML = `
                <div class="contact-avatar-wrap">
                    ${avatarHtml}
                    <span class="contact-online-dot"></span>
                </div>
                <div class="contact-info">
                    <div class="contact-top-row">
                        <div class="contact-name-wrap">
                            <p class="contact-name">${esc(name)}</p>
                            ${getRoleBadge(p.role)}
                        </div>
                        <span class="contact-time">${esc(time)}</span>
                    </div>
                    <div class="contact-bottom-row">
                        <p class="contact-snippet">${snippet}</p>
                        ${unread > 0 && !isActive
                            ? `<span class="unread-badge">${unread > 99 ? '99+' : unread}</span>`
                            : ''}
                    </div>
                </div>`;

            item.addEventListener('click', () =>
                openConversation(row.conversation_id, {
                    id: p.id, name, role: p.role, initials: ini, avatar_url: avatarUrl
                })
            );
            contactsList.appendChild(item);
        });
    }

    /* ── Filtering & Search ───────────────────────────── */
    function applyFilter() {
        const q = contactsSearch ? contactsSearch.value.trim().toLowerCase() : '';
        let filtered = allConversations;

        // 1. Role / Status chip filter
        if (currentFilter === 'unread') {
            filtered = filtered.filter(row => (unreadMap[row.conversation_id] || 0) > 0);
        } else if (currentFilter === 'staff') {
            filtered = filtered.filter(row => {
                const r = (row.profiles?.role || '').toLowerCase().replace(/_/g, '');
                return r === 'facilitystaff' || r === 'owner' || r === 'clubadmin' || r === 'adminstaff' || r === 'superadmin';
            });
        } else if (currentFilter === 'players') {
            filtered = filtered.filter(row => {
                const r = (row.profiles?.role || '').toLowerCase().replace(/_/g, '');
                return !r || r === 'player';
            });
        }

        // 2. Search query filter
        if (q) {
            filtered = filtered.filter(row => {
                const p = row.profiles;
                if (!p) return false;
                const name = `${p.first_name || ''} ${p.last_name || ''}`.toLowerCase();
                const latest = (latestMsgMap[row.conversation_id]?.content || '').toLowerCase();
                return name.includes(q) || latest.includes(q);
            });
        }

        renderContacts(filtered);
    }

    contactsSearch?.addEventListener('input', applyFilter);

    // Filter Chips
    document.querySelectorAll('.convo-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.convo-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            currentFilter = chip.dataset.filter || 'all';
            applyFilter();
        });
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
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;margin:auto;gap:10px;color:var(--text-muted);">
                <i class="ph ph-circle-notch" style="font-size:1.8rem;animation:spin 0.8s linear infinite;color:var(--primary-orange);"></i>
                <p style="font-size:0.85rem;font-weight:700;">Loading conversation...</p>
            </div>`;
    }

    async function openConversation(convoId, user) {
        if (!convoId) return;
        const lobbyIdSet = await getLobbyIdSet();
        if (lobbyIdSet.has(convoId)) {
            console.warn('[Messages] Refusing to open matchmaker lobby in personal messages tab:', convoId);
            return;
        }

        activeConversationId = convoId;
        activeOtherUser      = user;

        highlightActiveContact(convoId);
        showChat(user);

        // Instant render from cache if available, else show loader
        if (allMessagesMap[convoId] && allMessagesMap[convoId].length > 0) {
            renderMessages(allMessagesMap[convoId]);
        } else {
            showLoader();
        }

        const layout = document.querySelector('.messages-layout');
        layout?.classList.add('chat-active');

        // Start background polling for this active chat
        startActivePolling();

        try {
            await markAsRead(convoId);
        } catch (err) {
            console.error('[Messages] markAsRead failed:', err);
        }

        try {
            await loadMessages(convoId);
        } catch (err) {
            console.error('[Messages] loadMessages failed:', err);
        }

        try {
            await loadConversations();
        } catch (err) {
            console.error('[Messages] loadConversations failed after open:', err);
        }
    }

    /* ══════════════════════════════════════════════════
       MARK AS READ
    ══════════════════════════════════════════════════ */
    async function markAsRead(convoId) {
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
                sender:profiles!messages_sender_id_fkey(first_name, last_name, role, avatar_url)
            `)
            .eq('conversation_id', convoId)
            .order('created_at', { ascending: true });

        if (error) {
            console.error('[Messages] loadMessages:', error);
            if (activeConversationId === convoId && (!allMessagesMap[convoId] || allMessagesMap[convoId].length === 0)) {
                chatMessages.innerHTML = `<div style="text-align:center;color:#ef4444;font-size:0.85rem;margin:auto;padding:20px;font-weight:700;">
                    Failed to load messages. Please try again.
                </div>`;
            }
            return;
        }

        allMessagesMap[convoId] = msgs || [];
        if (activeConversationId === convoId) {
            renderMessages(allMessagesMap[convoId]);
        }
    }

    function renderMessages(msgs) {
        chatMessages.innerHTML = '';
        if (msgs.length === 0) {
            chatMessages.innerHTML = `
                <div style="text-align:center;color:var(--text-muted);font-size:0.88rem;font-weight:700;margin:auto;padding:20px;">
                    No messages yet. Say hi and start your court chat! 🏸
                </div>`;
            chatMessages.scrollTop = chatMessages.scrollHeight;
            return;
        }

        let lastDate     = '';
        let lastSender   = '';
        let currentGroup = null;

        msgs.forEach(msg => {
            const isMine   = msg.sender_id === currentUserId;
            const msgDate  = dateSep(msg.created_at);
            const senderFull = msg.sender
                ? `${msg.sender.first_name || ''} ${msg.sender.last_name || ''}`.trim()
                : (isMine ? 'You' : 'Player');

            // Date separator
            if (msgDate !== lastDate) {
                const sep = document.createElement('div');
                sep.className = 'msg-date-sep';
                sep.textContent = msgDate;
                chatMessages.appendChild(sep);
                lastDate     = msgDate;
                lastSender   = '';
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

        // Always smoothly scroll to latest message
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    /* ══════════════════════════════════════════════════
       SEND MESSAGE (Instant Optimistic Delivery)
    ══════════════════════════════════════════════════ */
    async function sendMessage() {
        if (!activeConversationId) return;
        const text = msgInput.value.trim();
        if (!text) return;

        // 1. Instantly clear input
        msgInput.value = '';
        sendMsgBtn.disabled = true;

        // 2. Generate optimistic local message
        const tempId = 'temp-' + Date.now();
        const nowIso = new Date().toISOString();
        const optimisticMsg = {
            id: tempId,
            conversation_id: activeConversationId,
            sender_id: currentUserId,
            content: text,
            created_at: nowIso,
            read_at: null,
            sender: {
                first_name: 'You',
                last_name: ''
            }
        };

        // 3. Immediately render locally with 0ms lag
        if (!allMessagesMap[activeConversationId]) {
            allMessagesMap[activeConversationId] = [];
        }
        allMessagesMap[activeConversationId].push(optimisticMsg);
        renderMessages(allMessagesMap[activeConversationId]);

        // 4. Immediately update sidebar preview and order
        latestMsgMap[activeConversationId] = optimisticMsg;
        applyFilter();

        // 5. Post to Supabase database
        const { data, error } = await supabaseClient
            .from('messages')
            .insert({
                conversation_id: activeConversationId,
                sender_id:       currentUserId,
                content:         text
            })
            .select(`
                *,
                sender:profiles!messages_sender_id_fkey(first_name, last_name, role, avatar_url)
            `)
            .single();

        sendMsgBtn.disabled = false;

        if (error) {
            console.error('[Messages] sendMessage error:', error);
            // Restore text to input on failure
            msgInput.value = text;
            // Remove the failed optimistic message
            allMessagesMap[activeConversationId] = allMessagesMap[activeConversationId].filter(m => m.id !== tempId);
            renderMessages(allMessagesMap[activeConversationId]);
            if (typeof showToast === 'function') {
                showToast('Send Failed', 'Could not send message. Please retry.', 'error');
            }
            return;
        }

        // 6. Swap temp message with official saved message record
        if (data && allMessagesMap[activeConversationId]) {
            const idx = allMessagesMap[activeConversationId].findIndex(m => m.id === tempId);
            if (idx !== -1) {
                allMessagesMap[activeConversationId][idx] = data;
            }
            latestMsgMap[activeConversationId] = data;
            renderMessages(allMessagesMap[activeConversationId]);
            applyFilter();
        }

        // Refresh conversation snippets and ordering
        loadConversations();
    }

    /* ── Quick Court Reply Pills ── */
    document.querySelectorAll('.quick-reply-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            const text = pill.dataset.text;
            if (!text || !msgInput) return;
            msgInput.value = text;
            msgInput.focus();
        });
    });

    /* ══════════════════════════════════════════════════
       NEW CHAT MODAL
    ══════════════════════════════════════════════════ */
    function openModal() {
        if (!newChatModal) return;
        newChatModal.classList.add('open');
        userSearchInput.value = '';
        userSearchResults.innerHTML = '<p class="search-hint">Start typing a name to find court staff, club leaders, or players...</p>';
        setTimeout(() => userSearchInput.focus(), 120);
    }

    function closeModal() {
        if (newChatModal) newChatModal.classList.remove('open');
    }

    async function searchUsers(query) {
        if (!query || query.length < 2) {
            userSearchResults.innerHTML = '<p class="search-hint">Start typing a name to find court staff, club leaders, or players...</p>';
            return;
        }
        userSearchResults.innerHTML = '<p class="search-hint"><i class="ph ph-circle-notch" style="animation:spin 0.8s linear infinite;"></i> Searching users…</p>';

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
            userSearchResults.innerHTML = '<p class="search-hint">No players or staff found matching your search.</p>';
            return;
        }

        userSearchResults.innerHTML = '';
        users.forEach(user => {
            const name      = `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'Pickleball Player';
            const ini       = initials(user.first_name, user.last_name);
            const avatarUrl = user.avatar_url || null;

            const avatarHtml = avatarUrl
                ? `<div class="user-result-avatar"><img src="${esc(avatarUrl)}" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;"></div>`
                : `<div class="user-result-avatar" style="background:${getAvatarGradient(name)}">${esc(ini)}</div>`;

            const item = document.createElement('div');
            item.className = 'user-result-item';
            item.innerHTML = `
                ${avatarHtml}
                <div style="flex:1;min-width:0;">
                    <div class="user-result-name">${esc(name)}</div>
                    <div class="user-result-role">${getRoleBadge(user.role)}</div>
                </div>
                <i class="ph ph-chat-circle-dots" style="color:var(--primary-orange);font-size:1.2rem;"></i>`;
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
        const name     = `${targetUser.first_name || ''} ${targetUser.last_name || ''}`.trim() || 'User';
        const userObj  = { id: targetUser.id, name, role: targetUser.role, initials: ini, avatar_url: targetUser.avatar_url || null };

        // Check if private direct conversation already exists (strictly excluding matchmaker lobbies)
        const { data: mine } = await supabaseClient
            .from('conversation_participants')
            .select('conversation_id')
            .eq('profile_id', currentUserId);

        const myIds = (mine || []).map(r => r.conversation_id);
        const lobbyIdSet = await getLobbyIdSet();
        const privateIds = myIds.filter(id => !lobbyIdSet.has(id));

        if (privateIds.length > 0) {
            const { data: shared } = await supabaseClient
                .from('conversation_participants')
                .select('conversation_id')
                .eq('profile_id', targetUser.id)
                .in('conversation_id', privateIds);

            if (shared && shared.length > 0) {
                await openConversation(shared[0].conversation_id, userObj);
                return;
            }
        }

        // Create new conversation
        const { data: newConvo, error: convoErr } = await supabaseClient
            .from('conversations').insert({}).select().single();

        if (convoErr || !newConvo) {
            if (typeof showToast === 'function') {
                showToast('Chat Error', 'Could not start conversation. Please try again.', 'error');
            } else {
                alert('Could not start conversation. Please try again.');
            }
            return;
        }

        const { error: partErr } = await supabaseClient
            .from('conversation_participants')
            .insert([
                { conversation_id: newConvo.id, profile_id: currentUserId },
                { conversation_id: newConvo.id, profile_id: targetUser.id }
            ]);

        if (partErr) {
            if (typeof showToast === 'function') {
                showToast('Chat Error', 'Could not start conversation. Please try again.', 'error');
            } else {
                alert('Could not start conversation. Please try again.');
            }
            return;
        }

        await openConversation(newConvo.id, userObj);
    }

    /* ══════════════════════════════════════════════════
       EVENT LISTENERS
    ══════════════════════════════════════════════════ */
    chatBackBtn?.addEventListener('click', hideChat);
    closeChatBtn?.addEventListener('click', hideChat);
    refreshChatBtn?.addEventListener('click', () => {
        if (activeConversationId) loadMessages(activeConversationId);
    });

    newChatBtn?.addEventListener('click', openModal);
    heroNewChatBtn?.addEventListener('click', openModal);
    placeholderNewChatBtn?.addEventListener('click', openModal);

    // Placeholder Quick Card Shortcuts
    cardQuickStaff?.addEventListener('click', () => {
        openModal();
        userSearchInput.value = 'staff';
        searchUsers('staff');
    });
    cardQuickClubs?.addEventListener('click', () => {
        openModal();
        userSearchInput.value = 'club';
        searchUsers('club');
    });
    cardQuickPlayers?.addEventListener('click', () => {
        openModal();
        userSearchInput.focus();
    });

    modalCloseBtn?.addEventListener('click', closeModal);
    newChatModal?.addEventListener('click', e => { if (e.target === newChatModal) closeModal(); });

    userSearchInput?.addEventListener('input', e => {
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(() => searchUsers(e.target.value.trim()), 280);
    });

    sendMsgBtn?.addEventListener('click', sendMessage);
    msgInput?.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    /* ══════════════════════════════════════════════════
       REALTIME WEBSOCKET SUBSCRIPTION
    ══════════════════════════════════════════════════ */
    try {
        supabaseClient.channel('messages_realtime_channel')
            .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'messages' }, async payload => {
                const newMsg = payload.new;
                if (!newMsg) return;
                const convoId = newMsg.conversation_id;

                if (convoId === activeConversationId) {
                    if (newMsg.sender_id !== currentUserId) {
                        await markAsRead(convoId);
                    }
                    await loadMessages(convoId);
                }
                loadConversations();
            })
            .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'messages' }, async payload => {
                const updatedMsg = payload.new;
                if (!updatedMsg) return;
                const convoId = updatedMsg.conversation_id;
                if (convoId === activeConversationId) {
                    await loadMessages(convoId);
                }
                loadConversations();
            })
            .subscribe((status, err) => {
                if (err) console.warn('[Messages Realtime status]', status, err);
            });
    } catch (rtErr) {
        console.warn('[Messages] Realtime channel setup failed:', rtErr);
    }

    /* ── Initial load ─────────────────────────────────── */
    loadConversations();

    // Auto-open chat if ?chat_user= query parameter is present
    const urlParams = new URLSearchParams(window.location.search);
    const chatUserId = urlParams.get('chat_user');
    if (chatUserId) {
        (async () => {
            const { data: user, error } = await supabaseClient
                .from('profiles')
                .select('id, first_name, last_name, role, avatar_url')
                .eq('id', chatUserId)
                .single();
            if (!error && user) {
                setTimeout(() => {
                    startConversationWith(user);
                }, 500);
            }
        })();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (supabaseClient) initMessages();
    else window.addEventListener('supabase-ready', initMessages);
});
