// player_common.js
// Common Drawer functionality for Player dashboard

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

    // 2. Inject HTML Elements (Overlay, Drawer Container)
    const container = document.createElement('div');
    container.innerHTML = `
        <!-- Drawer Overlay -->
        <div id="playerDrawerOverlay" class="details-drawer-overlay" onclick="closePlayerDrawer()"></div>
        
        <!-- Player Details Drawer -->
        <div id="playerDrawer" class="details-drawer">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; border-bottom:1px solid var(--border-color); padding-bottom:15px;">
                <h3 style="margin:0; font-size:1.2rem; font-weight:700; color:var(--text-primary); display:flex; align-items:center; gap:8px;"><i class="ph ph-user-focus" style="color:var(--primary-orange); font-size:1.4rem;"></i> Player Profile</h3>
                <button onclick="closePlayerDrawer()" style="background:none; border:none; color:var(--text-muted); font-size:1.4rem; cursor:pointer; display:flex; align-items:center; justify-content:center; padding:6px; border-radius:50%; transition:background-color 0.2s;" onmouseover="this.style.backgroundColor='var(--input-bg)';this.style.color='var(--text-primary)'" onmouseout="this.style.backgroundColor='transparent';this.style.color='var(--text-muted)'"><i class="ph ph-x"></i></button>
            </div>
            
            <!-- Loading Indicator -->
            <div id="pDrawerLoading" style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; height:200px; color:var(--text-muted);">
                <div class="drawer-spinner"></div>
                <p style="font-size:0.85rem;">Loading player details...</p>
            </div>
            
            <!-- Content Card -->
            <div id="pDrawerContent" style="display:none;" class="player-profile-modal-body">
                <!-- Header/Avatar Section -->
                <div class="profile-header-card">
                    <div id="pDrawerAvatar" class="profile-avatar-wrapper">
                        <!-- Filled dynamically -->
                    </div>
                    <h3 id="pDrawerName" class="profile-name-title">John Doe</h3>
                    <span class="profile-role-badge">Player</span>
                    
                    <!-- Ratings Section -->
                    <div class="profile-ratings-grid">
                        <div class="rating-badge-card elo">
                            <span class="rating-label">ELO</span>
                            <span id="pDrawerElo" class="rating-value">0</span>
                        </div>
                        <div class="rating-badge-card dupr">
                            <span class="rating-label">DUPR</span>
                            <span id="pDrawerDupr" class="rating-value">0.00</span>
                        </div>
                        <div class="rating-badge-card proficiency">
                            <span class="rating-label">LEVEL</span>
                            <span id="pDrawerSkill" class="rating-value">Beginner</span>
                        </div>
                    </div>
                </div>

                <!-- Contact details -->
                <div class="profile-section-card">
                    <h4 class="section-card-title"><i class="ph ph-user-focus"></i> Player Details</h4>
                    <div class="detail-info-row">
                        <span class="detail-label"><i class="ph ph-phone"></i> Phone:</span>
                        <span id="pDrawerPhone" class="detail-value">—</span>
                    </div>
                </div>

                <!-- Stats Section -->
                <div class="profile-section-card">
                    <h4 class="section-card-title"><i class="ph ph-chart-bar"></i> Performance Stats</h4>
                    <div class="profile-stats-container">
                        <div class="stat-box-mini">
                            <span id="pDrawerPlayed" class="stat-number">0</span>
                            <span class="stat-lbl">Played</span>
                        </div>
                        <div class="stat-box-mini win">
                            <span id="pDrawerWins" class="stat-number">0</span>
                            <span class="stat-lbl">Wins</span>
                        </div>
                        <div class="stat-box-mini loss">
                            <span id="pDrawerLosses" class="stat-number">0</span>
                            <span class="stat-lbl">Losses</span>
                        </div>
                        <div class="stat-box-mini rate">
                            <span id="pDrawerWinRate" class="stat-number">0%</span>
                            <span class="stat-lbl">Win Rate</span>
                        </div>
                    </div>
                </div>

                <!-- Match History Section -->
                <div class="profile-section-card">
                    <h4 class="section-card-title"><i class="ph ph-clock-counter-clockwise"></i> Recent Matches</h4>
                    <div id="pDrawerMatches" class="modal-match-history-list">
                        <!-- Filled dynamically -->
                    </div>
                </div>

                <!-- Rating History Section -->
                <div class="profile-section-card">
                    <h4 class="section-card-title"><i class="ph ph-chart-line-up"></i> Rating History (Recent)</h4>
                    <div id="pDrawerRatingHistory" style="display:flex; flex-direction:column; gap:8px; max-height:200px; overflow-y:auto; padding-right:4px;">
                        <!-- Filled dynamically -->
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(container);
});

function openPlayerDrawer(playerId) {
    if (!playerId || playerId === 'None') return;
    const drawer = document.getElementById('playerDrawer');
    const overlay = document.getElementById('playerDrawerOverlay');
    if (!drawer || !overlay) return;
    
    // Reset loader states
    document.getElementById('pDrawerLoading').style.display = 'flex';
    document.getElementById('pDrawerLoading').innerHTML = `
        <div class="drawer-spinner"></div>
        <p style="font-size:0.85rem;">Loading player details...</p>
    `;
    document.getElementById('pDrawerContent').style.display = 'none';
    
    // Show drawer
    overlay.classList.add('active');
    drawer.classList.add('active');
    
    fetch(`/player/leaderboard/${playerId}/details`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                const loadingDiv = document.getElementById('pDrawerLoading');
                loadingDiv.style.display = 'flex';
                loadingDiv.innerHTML = `<p style="color:#ef4444;"><i class="ph ph-warning-circle" style="font-size:2rem; display:block; margin-bottom:8px;"></i>Error loading details</p>`;
                return;
            }
            
            // Basic details
            document.getElementById('pDrawerName').innerText = `${data.first_name} ${data.last_name}`;
            document.getElementById('pDrawerDupr').innerText = parseFloat(data.dupr).toFixed(2);
            document.getElementById('pDrawerElo').innerText = data.elo;
            document.getElementById('pDrawerPlayed').innerText = parseInt(data.wins || 0) + parseInt(data.losses || 0);
            document.getElementById('pDrawerWins').innerText = data.wins;
            document.getElementById('pDrawerLosses').innerText = data.losses;
            document.getElementById('pDrawerWinRate').innerText = `${data.win_rate}%`;
            document.getElementById('pDrawerPhone').innerText = data.phone || '—';
            
            // Skill badge
            document.getElementById('pDrawerSkill').innerText = data.proficiency || 'Beginner';
            
            // Avatar
            const avatarDiv = document.getElementById('pDrawerAvatar');
            if (data.avatar_url) {
                avatarDiv.innerHTML = `<img src="${data.avatar_url}">`;
            } else {
                const initials = (((data.first_name || ' ')[0] + (data.last_name || ' ')[0]).toUpperCase().trim() || '?');
                avatarDiv.innerHTML = `<div class="profile-avatar-initials">${initials}</div>`;
            }
            
            // Match history list
            const matchesDiv = document.getElementById('pDrawerMatches');
            if (data.matches && data.matches.length > 0) {
                matchesDiv.innerHTML = data.matches.map(m => {
                    let pillClass = 'draw';
                    let resText = m.result.toUpperCase();
                    if (resText === 'WIN') pillClass = 'win';
                    else if (resText === 'LOSS') pillClass = 'loss';
                    
                    return `
                        <div class="modal-match-item">
                            <div class="match-meta-info">
                                <span class="match-event-name">${m.event_title}</span>
                                <span class="match-opponent">vs ${m.opponent}</span>
                            </div>
                            <div class="match-score-result">
                                <span class="match-score-val">${m.score}</span>
                                <span class="match-result-pill ${pillClass}">${resText}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                matchesDiv.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; font-style:italic;">No matches played yet</div>';
            }
            
            // Rating history list
            const ratingHistoryDiv = document.getElementById('pDrawerRatingHistory');
            if (data.rating_history && data.rating_history.length > 0) {
                ratingHistoryDiv.innerHTML = data.rating_history.map(h => {
                    const dateStr = h.recorded_at ? h.recorded_at.split('T')[0] : '—';
                    return `
                        <div style="padding:6px 0; border-bottom: 1px dashed var(--border-color); display:flex; justify-content:space-between; font-size:0.8rem;">
                            <span style="color:var(--text-secondary);">${dateStr}</span>
                            <span style="font-weight:600; color:var(--text-primary);">DUPR: ${parseFloat(h.dupr).toFixed(2)} | ELO: ${h.elo}</span>
                        </div>
                    `;
                }).join('');
            } else {
                ratingHistoryDiv.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; font-style:italic;">No rating logs available</div>';
            }
            
            // Toggle visibility
            document.getElementById('pDrawerLoading').style.display = 'none';
            document.getElementById('pDrawerContent').style.display = 'flex';
        })
        .catch(err => {
            console.error('Drawer details fetch error:', err);
            const loadingDiv = document.getElementById('pDrawerLoading');
            loadingDiv.style.display = 'flex';
            loadingDiv.innerHTML = `<p style="color:#ef4444;"><i class="ph ph-warning-circle" style="font-size:2rem; display:block; margin-bottom:8px;"></i>An error occurred while loading details</p>`;
        });
}

function closePlayerDrawer() {
    const drawer = document.getElementById('playerDrawer');
    const overlay = document.getElementById('playerDrawerOverlay');
    if (drawer && overlay) {
        drawer.classList.remove('active');
        overlay.classList.remove('active');
    }
}
