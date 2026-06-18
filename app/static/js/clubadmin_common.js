// clubadmin_common.js
// Common Drawer & Lightbox functionality for Club Admin dashboard

document.addEventListener('DOMContentLoaded', () => {
    // 1. Inject CSS Styles
    const style = document.createElement('style');
    style.innerHTML = `
        .details-drawer {
            position: fixed;
            top: 0;
            right: -420px;
            width: 420px;
            height: 100vh;
            background: var(--sidebar-bg);
            border-left: 1px solid var(--border-color);
            box-shadow: -10px 0 35px rgba(0, 0, 0, 0.15);
            z-index: 999999 !important;
            transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            padding: 24px;
            overflow-y: auto;
            color: var(--text-primary);
            display: flex;
            flex-direction: column;
        }
        html.dark-mode .details-drawer {
            box-shadow: -10px 0 35px rgba(0, 0, 0, 0.5);
        }
        .details-drawer.active {
            right: 0;
        }
        .details-drawer-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(15, 18, 25, 0.45);
            backdrop-filter: blur(4px);
            z-index: 999998 !important;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        }
        html.dark-mode .details-drawer-overlay {
            background: rgba(0, 0, 0, 0.7);
        }
        .details-drawer-overlay.active {
            opacity: 1;
            pointer-events: auto;
        }
        .clickable-name {
            color: var(--text-primary);
            cursor: pointer;
            font-weight: 600;
            transition: color 0.2s ease;
        }
        .clickable-name:hover {
            color: var(--primary-orange) !important;
            text-decoration: underline;
        }

        /* ----- PROFILE DRAWER CONTENT DETAILS ----- */
        .player-profile-modal-body {
            display: flex;
            flex-direction: column;
            gap: 20px;
            margin-top: 10px;
        }
        
        .profile-header-card {
            text-align: center;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px 16px;
        }
        
        .profile-avatar-wrapper {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            overflow: hidden;
            margin: 0 auto 12px;
            border: 2px solid var(--primary-orange);
            box-shadow: 0 4px 10px rgba(225, 86, 35, 0.15);
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--sidebar-bg);
        }
        
        .profile-avatar-wrapper img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .profile-avatar-initials {
            width: 100%;
            height: 100%;
            background: var(--primary-orange-light);
            color: var(--primary-orange);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.8rem;
            font-weight: 700;
        }
        
        .profile-name-title {
            font-size: 1.2rem;
            font-weight: 700;
            margin: 0 0 4px 0;
            color: var(--text-primary);
        }
        
        .profile-role-badge {
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .profile-ratings-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
            margin-top: 18px;
        }
        
        .rating-badge-card {
            display: flex;
            flex-direction: column;
            padding: 10px 4px;
            background: var(--sidebar-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            align-items: center;
        }
        
        .rating-label {
            font-size: 0.65rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        
        .rating-value {
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .profile-section-card {
            background: var(--sidebar-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
        }
        
        .section-card-title {
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--text-primary);
            margin: 0 0 14px 0;
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
            text-align: left;
        }
        
        .section-card-title i {
            color: var(--primary-orange);
            font-size: 1.15rem;
        }
        
        .detail-info-row {
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
            margin-bottom: 10px;
        }
        
        .detail-info-row:last-child {
            margin-bottom: 0;
        }
        
        .detail-label {
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .detail-value {
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .profile-stats-container {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 8px;
        }
        
        .stat-box-mini {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 12px 4px;
            border-radius: 8px;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
        }
        
        .stat-number {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .stat-lbl {
            font-size: 0.65rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-top: 2px;
        }
        
        .stat-box-mini.win { border-color: rgba(41, 163, 86, 0.2); }
        .stat-box-mini.win .stat-number { color: var(--btn-green); }
        
        .stat-box-mini.loss { border-color: rgba(239, 68, 68, 0.2); }
        .stat-box-mini.loss .stat-number { color: #ef4444; }
        
        .stat-box-mini.rate { border-color: rgba(225, 86, 35, 0.2); }
        .stat-box-mini.rate .stat-number { color: var(--primary-orange); }
        
        .modal-match-history-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .modal-match-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            border-radius: 8px;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
        }
        
        .match-meta-info {
            display: flex;
            flex-direction: column;
            gap: 2px;
            text-align: left;
        }
        
        .match-event-name {
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .match-opponent {
            font-size: 0.72rem;
            color: var(--text-muted);
        }
        
        .match-score-result {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .match-score-val {
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--text-secondary);
        }
        
        .match-result-pill {
            font-size: 0.65rem;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
        }
        
        .match-result-pill.win { background: #e6f6ee; color: var(--btn-green); }
        .match-result-pill.loss { background: #fee2e2; color: #ef4444; }
        .match-result-pill.draw { background: var(--border-color); color: var(--text-secondary); }
        
        .drawer-spinner {
            width: 32px;
            height: 32px;
            border: 3px solid var(--border-color);
            border-top-color: var(--primary-orange);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Mobile Responsive Drawer override */
        @media (max-width: 576px) {
            .details-drawer {
                width: 100% !important;
                right: -100% !important;
                padding: 20px 16px !important;
            }
            .details-drawer.active {
                right: 0 !important;
            }
        }
    `;
    document.head.appendChild(style);

    // 2. Inject HTML Elements (Overlay, Drawer, Lightbox Modal)
    const container = document.createElement('div');
    container.innerHTML = `
        <!-- Drawer Overlay -->
        <div id="drawerOverlay" class="details-drawer-overlay" onclick="closeMemberDrawer()"></div>
        
        <!-- Member Details Drawer -->
        <div id="memberDrawer" class="details-drawer">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom:1px solid var(--border-color); padding-bottom:15px;">
                <h3 style="margin:0; font-size:1.2rem; font-weight:700; color:var(--text-primary); display:flex; align-items:center; gap:8px;"><i class="ph ph-user-focus" style="color:var(--primary-orange); font-size:1.4rem;"></i> Member Details</h3>
                <button onclick="closeMemberDrawer()" style="background:none; border:none; color:var(--text-muted); font-size:1.4rem; cursor:pointer; display:flex; align-items:center; justify-content:center; padding:6px; border-radius:50%; transition:background-color 0.2s;" onmouseover="this.style.backgroundColor='var(--input-bg)';this.style.color='var(--text-primary)'" onmouseout="this.style.backgroundColor='transparent';this.style.color='var(--text-muted)'"><i class="ph ph-x"></i></button>
            </div>
            
            <!-- Loading Indicator -->
            <div id="pDrawerLoading" style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; height:200px; color:var(--text-muted);">
                <div class="drawer-spinner"></div>
                <p style="font-size:0.85rem;">Loading member details...</p>
            </div>
            
            <!-- Content Card -->
            <div id="pDrawerContent" style="display:none;" class="player-profile-modal-body">
                <!-- Header/Avatar Section -->
                <div class="profile-header-card">
                    <div id="drawerAvatar" class="profile-avatar-wrapper">
                        <!-- Filled dynamically -->
                    </div>
                    <h3 id="drawerName" class="profile-name-title">John Doe</h3>
                    <span id="drawerStatus" class="profile-role-badge">Active</span>
                    
                    <!-- Ratings Section -->
                    <div class="profile-ratings-grid">
                        <div class="rating-badge-card elo">
                            <span class="rating-label">ELO</span>
                            <span id="drawerElo" class="rating-value">0</span>
                        </div>
                        <div class="rating-badge-card dupr">
                            <span class="rating-label">DUPR</span>
                            <span id="drawerDupr" class="rating-value">0.00</span>
                        </div>
                        <div class="rating-badge-card proficiency">
                            <span class="rating-label">LEVEL</span>
                            <span id="drawerSkill" class="rating-value">Beginner</span>
                        </div>
                    </div>
                </div>

                <!-- Contact & Membership details -->
                <div class="profile-section-card">
                    <h4 class="section-card-title"><i class="ph ph-shield-check"></i> Membership Details</h4>
                    <div class="detail-info-row">
                        <span class="detail-label"><i class="ph ph-phone"></i> Phone:</span>
                        <span id="drawerPhone" class="detail-value">—</span>
                    </div>
                    <div class="detail-info-row">
                        <span class="detail-label"><i class="ph ph-calendar"></i> Joined:</span>
                        <span id="drawerJoined" class="detail-value">—</span>
                    </div>
                    <div class="detail-info-row">
                        <span class="detail-label"><i class="ph ph-calendar-x"></i> Expiration:</span>
                        <span id="drawerExpires" class="detail-value">Lifetime</span>
                    </div>
                </div>

                <!-- Active Registrations Tab -->
                <div class="profile-section-card">
                    <h4 class="section-card-title"><i class="ph ph-calendar-star"></i> Active Registrations</h4>
                    <div id="drawerRegistrations" class="modal-match-history-list">
                        <!-- Filled dynamically -->
                    </div>
                </div>

                <!-- Tournament History Tab -->
                <div class="profile-section-card">
                    <h4 class="section-card-title"><i class="ph ph-sword"></i> Tournament History</h4>
                    <div id="drawerMatches" class="modal-match-history-list">
                        <!-- Filled dynamically -->
                    </div>
                </div>

                <!-- Rating History Section -->
                <div class="profile-section-card">
                    <h4 class="section-card-title"><i class="ph ph-chart-line-up"></i> Rating History (Recent)</h4>
                    <div id="drawerRatingHistory" style="display:flex; flex-direction:column; gap:8px; max-height:200px; overflow-y:auto; padding-right:4px;">
                        <!-- Filled dynamically -->
                    </div>
                </div>

                <!-- Membership Payments Tab -->
                <div class="profile-section-card">
                    <h4 class="section-card-title"><i class="ph ph-receipt"></i> Membership Payments</h4>
                    <div id="drawerPayments">
                        <!-- Filled dynamically -->
                    </div>
                </div>
            </div>
        </div>

        <!-- Lightbox Modal for Receipt -->
        <div id="receiptModal" class="details-drawer-overlay" style="display:none; justify-content:center; align-items:center; opacity:0; pointer-events:none; transition: opacity 0.2s ease; z-index: 99999999 !important;">
            <div style="background:var(--sidebar-bg); border: 1px solid var(--border-color); border-radius:12px; padding:20px; max-width:500px; width:90%; max-height:90vh; box-shadow:var(--shadow-hover); position:relative; display:flex; flex-direction:column; align-items:center; z-index: 999999999 !important;">
                <button onclick="closeReceiptModal()" style="position:absolute; top:15px; right:15px; background:none; border:none; color:var(--text-muted); font-size:1.5rem; cursor:pointer;"><i class="ph ph-x"></i></button>
                <h3 style="margin: 0 0 15px 0; color:var(--text-primary); font-size:1.2rem; display:flex; align-items:center; gap:8px;"><i class="ph ph-wallet" style="color:#00c6ff;"></i> GCash Receipt Screenshot</h3>
                <img id="receiptImage" src="" style="width:100%; max-height:60vh; object-fit:contain; border-radius:8px; border:1px solid var(--border-color); background:#000;">
                <div id="receiptRef" style="margin-top:15px; font-family:monospace; font-size:1.1rem; color:var(--text-secondary); background:var(--bg-color); padding:8px 16px; border-radius:6px; border:1px solid var(--border-color);">Ref: -</div>
            </div>
        </div>
    `;
    document.body.appendChild(container);
});

function openMemberDrawer(playerId) {
    const drawer = document.getElementById('memberDrawer');
    const overlay = document.getElementById('drawerOverlay');
    if (!drawer || !overlay) return;
    
    // Reset loader states
    document.getElementById('pDrawerLoading').style.display = 'flex';
    document.getElementById('pDrawerLoading').innerHTML = `
        <div class="drawer-spinner"></div>
        <p style="font-size:0.85rem;">Loading member details...</p>
    `;
    document.getElementById('pDrawerContent').style.display = 'none';
    
    // Show drawer
    overlay.classList.add('active');
    drawer.classList.add('active');
    
    fetch(`/clubadmin/members/${playerId}/details`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                const loadingDiv = document.getElementById('pDrawerLoading');
                loadingDiv.style.display = 'flex';
                loadingDiv.innerHTML = `<p style="color:#ef4444;"><i class="ph ph-warning-circle" style="font-size:2rem; display:block; margin-bottom:8px;"></i>Error loading details</p>`;
                return;
            }
            
            // Profile & Meta
            document.getElementById('drawerName').innerText = `${data.first_name} ${data.last_name}`;
            document.getElementById('drawerPhone').innerText = data.phone || '—';
            document.getElementById('drawerJoined').innerText = data.joined_at || '—';
            document.getElementById('drawerExpires').innerText = data.expires_at || 'Lifetime';
            document.getElementById('drawerElo').innerText = data.elo;
            document.getElementById('drawerDupr').innerText = parseFloat(data.dupr).toFixed(2);
            document.getElementById('drawerSkill').innerText = data.proficiency || 'Beginner';
            
            // Avatar
            const avatarDiv = document.getElementById('drawerAvatar');
            if (data.avatar_url) {
                avatarDiv.innerHTML = `<img src="${data.avatar_url}">`;
            } else {
                const initials = ((data.first_name || ' ')[0] + (data.last_name || ' ')[0]).toUpperCase().trim() || '?';
                avatarDiv.innerHTML = `<div class="profile-avatar-initials">${initials}</div>`;
            }
            
            // Status text
            const statusEl = document.getElementById('drawerStatus');
            statusEl.innerText = data.status.charAt(0).toUpperCase() + data.status.slice(1);
            
            // Active registrations
            const regsDiv = document.getElementById('drawerRegistrations');
            if (data.registrations && data.registrations.length > 0) {
                regsDiv.innerHTML = data.registrations.map(r => {
                    let statusClass = 'draw';
                    if (r.status === 'registered') statusClass = 'win';
                    else if (r.status === 'pending') statusClass = 'loss';
                    
                    return `
                        <div class="modal-match-item">
                            <div class="match-meta-info">
                                <span class="match-event-name">${r.title}</span>
                                <span class="match-opponent">${r.date} | ${r.type.toUpperCase()}</span>
                            </div>
                            <div class="match-score-result">
                                <span class="match-result-pill ${statusClass}">${r.status}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                regsDiv.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; font-style:italic;">No active registrations</div>';
            }
            
            // Tournament History (matches)
            const matchesDiv = document.getElementById('drawerMatches');
            if (data.matches && data.matches.length > 0) {
                matchesDiv.innerHTML = data.matches.map(m => {
                    let pillClass = 'draw';
                    let resText = m.result.toUpperCase();
                    if (resText === 'WIN') pillClass = 'win';
                    else if (resText === 'LOSS') pillClass = 'loss';
                    
                    return `
                        <div class="modal-match-item">
                            <div class="match-meta-info">
                                <span class="match-event-name">vs ${m.opponent}</span>
                                <span class="match-opponent">${m.event_title} (Round ${m.round})</span>
                            </div>
                            <div class="match-score-result">
                                <span class="match-score-val">${m.score}</span>
                                <span class="match-result-pill ${pillClass}">${resText}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                matchesDiv.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; font-style:italic;">No tournament matches</div>';
            }
            
            // Rating history list
            const ratingHistoryDiv = document.getElementById('drawerRatingHistory');
            if (data.rating_history && data.rating_history.length > 0) {
                ratingHistoryDiv.innerHTML = data.rating_history.map((h, index) => {
                    const dateStr = h.recorded_at ? h.recorded_at.split('T')[0] : '—';
                    return `
                        <div style="padding:6px 0; border-bottom: 1px dashed var(--border-color); display:flex; justify-content:space-between; font-size:0.8rem;">
                            <span style="color:var(--text-secondary);">${dateStr}</span>
                            <span style="font-weight:600; color:var(--text-primary);">DUPR: ${parseFloat(h.dupr).toFixed(2)} | ELO: ${h.elo}</span>
                        </div>
                    `;
                }).join('');
            } else {
                ratingHistoryDiv.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; font-style:italic;">No rating history logs</div>';
            }
            
            // Membership Payments info
            const paymentsDiv = document.getElementById('drawerPayments');
            if (data.gcash_ref) {
                paymentsDiv.innerHTML = `
                    <div style="background:var(--input-bg); border:1px solid var(--border-color); border-radius:8px; padding:12px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:0.8rem;">
                            <span style="color:var(--text-secondary);">GCash Reference:</span>
                            <strong style="color:var(--text-primary); font-family:monospace;">${data.gcash_ref}</strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:0.8rem;">
                            <span style="color:var(--text-secondary);">Amount:</span>
                            <strong style="color:var(--text-primary);">₱${parseFloat(data.membership_fee).toFixed(2)}</strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:0.8rem;">
                            <span style="color:var(--text-secondary);">Submission Date:</span>
                            <span style="color:var(--text-primary);">${data.joined_at}</span>
                        </div>
                        ${data.receipt_url ? `
                        <div style="margin-top:12px; text-align:center;">
                            <button onclick="showReceipt('${data.receipt_url}', '${data.gcash_ref}')" style="background:rgba(0,198,255,0.15); color:#00c6ff; border:1px solid rgba(0,198,255,0.3); border-radius:6px; padding:6px 12px; cursor:pointer; font-size:0.75rem; display:inline-flex; align-items:center; gap:6px; font-weight:600;">
                                <i class="ph ph-image"></i> View Receipt Screenshot
                            </button>
                        </div>
                        ` : ''}
                    </div>
                `;
            } else {
                paymentsDiv.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; font-style:italic;">No payment reference details</div>';
            }
            
            // Toggle visibility
            document.getElementById('pDrawerLoading').style.display = 'none';
            document.getElementById('pDrawerContent').style.display = 'flex';
        })
        .catch(err => {
            console.error('Drawer fetch error:', err);
            const loadingDiv = document.getElementById('pDrawerLoading');
            loadingDiv.style.display = 'flex';
            loadingDiv.innerHTML = `<p style="color:#ef4444;"><i class="ph ph-warning-circle" style="font-size:2rem; display:block; margin-bottom:8px;"></i>An error occurred while loading details</p>`;
        });
}

function closeMemberDrawer() {
    const drawer = document.getElementById('memberDrawer');
    const overlay = document.getElementById('drawerOverlay');
    if (drawer && overlay) {
        drawer.classList.remove('active');
        overlay.classList.remove('active');
    }
}

function showReceipt(url, ref) {
    const modal = document.getElementById('receiptModal');
    const img = document.getElementById('receiptImage');
    const refText = document.getElementById('receiptRef');
    if (!modal || !img || !refText) return;
    
    img.src = url;
    refText.innerText = "Ref: " + (ref || '—');
    modal.style.display = 'flex';
    setTimeout(() => {
        modal.style.opacity = '1';
        modal.style.pointerEvents = 'auto';
    }, 10);
}

function closeReceiptModal() {
    const modal = document.getElementById('receiptModal');
    if (!modal) return;
    modal.style.opacity = '0';
    modal.style.pointerEvents = 'none';
    setTimeout(() => {
        modal.style.display = 'none';
    }, 200);
}
