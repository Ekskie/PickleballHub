// clubadmin_common.js
// Common Drawer & Lightbox functionality for Club Admin dashboard

document.addEventListener('DOMContentLoaded', () => {
    // 1. Inject CSS Styles
    const style = document.createElement('style');
    style.innerHTML = `
        .details-drawer {
            position: fixed;
            top: 0;
            right: -480px;
            width: 480px;
            height: 100vh;
            background: var(--sidebar-bg);
            border-left: 1px solid var(--border-color);
            box-shadow: -10px 0 35px rgba(0, 0, 0, 0.1);
            z-index: 10000;
            transition: right 0.35s cubic-bezier(0.4, 0, 0.2, 1);
            padding: 30px;
            overflow-y: auto;
            color: var(--text-primary);
        }
        html.dark-mode .details-drawer {
            box-shadow: -10px 0 35px rgba(0, 0, 0, 0.45);
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
            background: rgba(0, 0, 0, 0.4);
            backdrop-filter: blur(2px);
            z-index: 9999;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        }
        html.dark-mode .details-drawer-overlay {
            background: rgba(0, 0, 0, 0.65);
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

        /* Unified Theme-Aware Status Pills */
        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            width: max-content;
            border: 1px solid transparent;
            transition: background 0.3s, color 0.3s, border-color 0.3s;
        }
        
        /* Light Mode Pill Styles */
        .status-pill.success, .status-pill.active {
            background: #E6F6EE;
            color: #166534;
            border-color: #bbf7d0;
        }
        .status-pill.warning, .status-pill.pending, .status-pill.advanced {
            background: #FEF3C7;
            color: #92400E;
            border-color: #fde68a;
        }
        .status-pill.error, .status-pill.expired, .status-pill.rejected {
            background: #FEE2E2;
            color: #991B1B;
            border-color: #fca5a5;
        }
        .status-pill.intermediate {
            background: #E0F2FE;
            color: #075985;
            border-color: #bae6fd;
        }
        .status-pill.pro {
            background: #F3E8FF;
            color: #6B21A8;
            border-color: #e9d5ff;
        }
        .status-pill.beginner, .status-pill.disabled {
            background: #F3F4F6;
            color: #374151;
            border-color: #e5e7eb;
        }
        
        /* Dark Mode Pill Styles */
        html.dark-mode .status-pill.success, html.dark-mode .status-pill.active {
            background: rgba(41, 163, 86, 0.15);
            color: #4ade80;
            border-color: rgba(74, 222, 128, 0.2);
        }
        html.dark-mode .status-pill.warning, html.dark-mode .status-pill.pending, html.dark-mode .status-pill.advanced {
            background: rgba(245, 158, 11, 0.12);
            color: #fbbf24;
            border-color: rgba(251, 191, 36, 0.2);
        }
        html.dark-mode .status-pill.error, html.dark-mode .status-pill.expired, html.dark-mode .status-pill.rejected {
            background: rgba(239, 68, 68, 0.12);
            color: #f87171;
            border-color: rgba(248, 113, 113, 0.2);
        }
        html.dark-mode .status-pill.intermediate {
            background: rgba(14, 165, 233, 0.12);
            color: #38bdf8;
            border-color: rgba(56, 189, 248, 0.2);
        }
        html.dark-mode .status-pill.pro {
            background: rgba(168, 85, 247, 0.12);
            color: #c084fc;
            border-color: rgba(192, 132, 252, 0.2);
        }
        html.dark-mode .status-pill.beginner, html.dark-mode .status-pill.disabled {
            background: rgba(148, 163, 184, 0.12);
            color: #cbd5e1;
            border-color: rgba(203, 213, 225, 0.2);
        }

        /* Accessible Text colors for match history result */
        .text-success {
            color: #166534;
        }
        html.dark-mode .text-success {
            color: #4ade80;
        }
        .text-danger {
            color: #991B1B;
        }
        html.dark-mode .text-danger {
            color: #f87171;
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
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; border-bottom:1px solid var(--border-color); padding-bottom:15px;">
                <h2 style="margin:0; font-size:1.4rem; color:var(--text-primary); display:flex; align-items:center; gap:8px;"><i class="ph ph-user"></i> Member Details</h2>
                <button onclick="closeMemberDrawer()" style="background:none; border:none; color:var(--text-primary); font-size:1.5rem; cursor:pointer;"><i class="ph ph-x"></i></button>
            </div>
            
            <!-- Profile Card Header -->
            <div style="display:flex; align-items:center; gap:16px; margin-bottom:24px;">
                <div id="drawerAvatar" style="width:70px; height:70px; border-radius:50%; background:var(--btn-navy); color:white; display:flex; align-items:center; justify-content:center; font-size:1.8rem; font-weight:700; overflow:hidden; flex-shrink:0; border:2px solid var(--border-color);">
                    ?
                </div>
                <div>
                    <h3 id="drawerName" style="margin:0; font-size:1.25rem; color:var(--text-primary);">John Doe</h3>
                    <span id="drawerSkill" class="status-pill" style="margin-top:6px; display:inline-block;">Beginner</span>
                    <div id="drawerPhone" style="font-size:0.85rem; color:var(--text-secondary); margin-top:6px;">Phone: —</div>
                </div>
            </div>
            
            <!-- General Membership Info -->
            <div style="padding:15px; margin-bottom:24px; border:1px solid var(--border-color); border-radius:12px; background: var(--bg-color);">
                <h4 style="margin:0 0 10px 0; color:var(--text-primary); font-size:0.95rem; display:flex; align-items:center; gap:6px;"><i class="ph ph-shield-check" style="color:var(--btn-green);"></i> Membership Info</h4>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; font-size:0.85rem;">
                    <div>
                        <span style="color:var(--text-secondary); display:block;">Status</span>
                        <strong id="drawerStatus" style="color:var(--text-primary);">Active</strong>
                    </div>
                    <div>
                        <span style="color:var(--text-secondary); display:block;">Expiration</span>
                        <strong id="drawerExpires" style="color:var(--text-primary);">Lifetime</strong>
                    </div>
                    <div>
                        <span style="color:var(--text-secondary); display:block;">Joined Date</span>
                        <strong id="drawerJoined" style="color:var(--text-primary);">—</strong>
                    </div>
                    <div>
                        <span style="color:var(--text-secondary); display:block;">Ratings</span>
                        <strong id="drawerRatings" style="color:var(--btn-green);">DUPR: 0.00 | ELO: 0</strong>
                    </div>
                </div>
            </div>
            
            <!-- Active Registrations Tab -->
            <div style="margin-bottom:24px;">
                <h4 style="margin:0 0 12px 0; color:var(--text-primary); font-size:0.95rem; border-bottom:1px solid var(--border-color); padding-bottom:6px; display:flex; align-items:center; gap:6px;"><i class="ph ph-calendar-star" style="color:#00c6ff;"></i> Active Registrations</h4>
                <div id="drawerRegistrations" style="display:flex; flex-direction:column; gap:8px;">
                    <!-- Dynamic content -->
                </div>
            </div>
            
            <!-- Tournament History Tab -->
            <div style="margin-bottom:24px;">
                <h4 style="margin:0 0 12px 0; color:var(--text-primary); font-size:0.95rem; border-bottom:1px solid var(--border-color); padding-bottom:6px; display:flex; align-items:center; gap:6px;"><i class="ph ph-sword" style="color:#f59e0b;"></i> Tournament History</h4>
                <div id="drawerMatches" style="display:flex; flex-direction:column; gap:8px;">
                    <!-- Dynamic content -->
                </div>
            </div>
            
            <!-- Rating History Tab -->
            <div style="margin-bottom:24px;">
                <h4 style="margin:0 0 12px 0; color:var(--text-primary); font-size:0.95rem; border-bottom:1px solid var(--border-color); padding-bottom:6px; display:flex; align-items:center; gap:6px;"><i class="ph ph-chart-line-up" style="color:#a855f7;"></i> Rating History (Recent)</h4>
                <div id="drawerRatingHistory" style="display:flex; flex-direction:column; gap:8px; font-size:0.85rem; max-height:200px; overflow-y:auto; padding-right:4px;">
                    <!-- Dynamic content -->
                </div>
            </div>
            
            <!-- Membership Payments Tab -->
            <div style="margin-bottom:24px;">
                <h4 style="margin:0 0 12px 0; color:var(--text-primary); font-size:0.95rem; border-bottom:1px solid var(--border-color); padding-bottom:6px; display:flex; align-items:center; gap:6px;"><i class="ph ph-receipt" style="color:#00c6ff;"></i> Membership Payments</h4>
                <div id="drawerPayments" style="font-size:0.85rem;">
                    <!-- Dynamic content -->
                </div>
            </div>
        </div>

        <!-- Lightbox Modal for Receipt -->
        <div id="receiptModal" class="details-drawer-overlay" style="display:none; justify-content:center; align-items:center; opacity:0; pointer-events:none; transition: opacity 0.2s ease; z-index: 10001;">
            <div style="background:var(--sidebar-bg); border: 1px solid var(--border-color); border-radius:12px; padding:20px; max-width:500px; width:90%; max-height:90vh; box-shadow:var(--shadow-hover); position:relative; display:flex; flex-direction:column; align-items:center;">
                <button onclick="closeReceiptModal()" style="position:absolute; top:15px; right:15px; background:none; border:none; color:var(--text-primary); font-size:1.5rem; cursor:pointer;"><i class="ph ph-x"></i></button>
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
    
    // Clear drawer elements or show a loader
    document.getElementById('drawerName').innerText = "Loading...";
    document.getElementById('drawerSkill').className = "status-pill";
    document.getElementById('drawerSkill').innerText = "—";
    document.getElementById('drawerPhone').innerText = "Phone: —";
    document.getElementById('drawerStatus').innerText = "—";
    document.getElementById('drawerExpires').innerText = "—";
    document.getElementById('drawerJoined').innerText = "—";
    document.getElementById('drawerRatings').innerText = "—";
    document.getElementById('drawerRegistrations').innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem;">Loading...</div>';
    document.getElementById('drawerMatches').innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem;">Loading...</div>';
    document.getElementById('drawerRatingHistory').innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem;">Loading...</div>';
    document.getElementById('drawerPayments').innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem;">Loading...</div>';
    
    // Show drawer
    overlay.classList.add('active');
    drawer.classList.add('active');
    
    fetch(`/clubadmin/members/${playerId}/details`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                document.getElementById('drawerName').innerText = "Error loading details";
                return;
            }
            
            // Profile & Meta
            document.getElementById('drawerName').innerText = `${data.first_name} ${data.last_name}`;
            document.getElementById('drawerPhone').innerText = `Phone: ${data.phone}`;
            
            // Avatar
            const avatarDiv = document.getElementById('drawerAvatar');
            if (data.avatar_url) {
                avatarDiv.innerHTML = `<img src="${data.avatar_url}" style="width:100%; height:100%; object-fit:cover;">`;
            } else {
                const initials = ((data.first_name || ' ')[0] + (data.last_name || ' ')[0]).toUpperCase().trim() || '?';
                avatarDiv.innerHTML = initials;
            }
            
            // Skill pill
            const skill = (data.proficiency || 'beginner').toLowerCase();
            const skillPill = document.getElementById('drawerSkill');
            skillPill.innerText = data.proficiency || 'Beginner';
            skillPill.removeAttribute('style'); // Clear inline styles
            skillPill.className = `status-pill ${skill}`;
            
            // Status and expiry
            const statusEl = document.getElementById('drawerStatus');
            statusEl.innerText = data.status.charAt(0).toUpperCase() + data.status.slice(1);
            statusEl.removeAttribute('style'); // Clear inline styles
            statusEl.className = `status-pill ${data.status}`;
            
            document.getElementById('drawerExpires').innerText = data.expires_at || 'Lifetime';
            document.getElementById('drawerJoined').innerText = data.joined_at || '—';
            document.getElementById('drawerRatings').innerText = `DUPR: ${parseFloat(data.dupr).toFixed(2)} | ELO: ${data.elo}`;
            
            // Active registrations
            const regsDiv = document.getElementById('drawerRegistrations');
            if (data.registrations && data.registrations.length > 0) {
                regsDiv.innerHTML = data.registrations.map(r => `
                    <div style="background:var(--bg-color); border:1px solid var(--border-color); border-radius:6px; padding:10px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div style="font-weight:600; color:var(--text-primary); font-size:0.85rem;">${r.title}</div>
                            <small style="color:var(--text-muted); font-size:0.75rem;">${r.date} | ${r.type.toUpperCase()}</small>
                        </div>
                        <span class="status-pill ${r.status === 'registered' ? 'success' : 'warning'}" style="font-size:0.75rem;">${r.status}</span>
                    </div>
                `).join('');
            } else {
                regsDiv.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem; font-style:italic;">No active registrations</div>';
            }
            
            // Tournament History (matches)
            const matchesDiv = document.getElementById('drawerMatches');
            if (data.matches && data.matches.length > 0) {
                matchesDiv.innerHTML = data.matches.map(m => `
                    <div style="background:var(--bg-color); border:1px solid var(--border-color); border-radius:6px; padding:10px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div style="font-weight:600; color:var(--text-primary); font-size:0.85rem;">vs ${m.opponent}</div>
                            <small style="color:var(--text-muted); font-size:0.75rem;">${m.event_title} (Round ${m.round})</small>
                        </div>
                        <div style="text-align:right;">
                            <span class="${m.result === 'Win' ? 'text-success' : m.result === 'Loss' ? 'text-danger' : ''}" style="font-weight:700; font-size:0.85rem; ${m.result !== 'Win' && m.result !== 'Loss' ? 'color:var(--text-secondary);' : ''}">${m.result}</span>
                            <div style="font-size:0.75rem; color:var(--text-muted);">${m.score}</div>
                        </div>
                    </div>
                `).join('');
            } else {
                matchesDiv.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem; font-style:italic;">No tournament matches</div>';
            }
            
            // Rating history list
            const ratingHistoryDiv = document.getElementById('drawerRatingHistory');
            if (data.rating_history && data.rating_history.length > 0) {
                ratingHistoryDiv.innerHTML = data.rating_history.map((h, index) => {
                    const dateStr = h.recorded_at ? h.recorded_at.split('T')[0] : '—';
                    return `
                        <div style="padding:6px 0; border-bottom: 1px dashed var(--border-color); display:flex; justify-content:space-between;">
                            <span style="color:var(--text-secondary); font-size:0.8rem;">${dateStr}</span>
                            <span style="font-weight:600; color:var(--text-primary); font-size:0.8rem;">DUPR: ${parseFloat(h.dupr).toFixed(2)} | ELO: ${h.elo}</span>
                        </div>
                    `;
                }).join('');
            } else {
                ratingHistoryDiv.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem; font-style:italic;">No rating history logs</div>';
            }
            
            // Membership Payments info
            const paymentsDiv = document.getElementById('drawerPayments');
            if (data.gcash_ref) {
                paymentsDiv.innerHTML = `
                    <div style="background:var(--bg-color); border:1px solid var(--border-color); border-radius:6px; padding:12px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:0.8rem;">
                            <span style="color:var(--text-secondary);">GCash Reference</span>
                            <strong style="color:var(--text-primary); font-family:monospace;">${data.gcash_ref}</strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:0.8rem;">
                            <span style="color:var(--text-secondary);">Amount</span>
                            <strong style="color:var(--text-primary);">₱${parseFloat(data.membership_fee).toFixed(2)}</strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:0.8rem;">
                            <span style="color:var(--text-secondary);">Submission Date</span>
                            <span style="color:var(--text-primary);">${data.joined_at}</span>
                        </div>
                        ${data.receipt_url ? `
                        <div style="margin-top:12px; text-align:center;">
                            <button onclick="showReceipt('${data.receipt_url}', '${data.gcash_ref}')" style="background:rgba(0,198,255,0.15); color:#00c6ff; border:1px solid rgba(0,198,255,0.3); border-radius:6px; padding:6px 12px; cursor:pointer; font-size:0.75rem; display:inline-flex; align-items:center; gap:6px; font-weight:600;">
                                <i class="ph ph-image"></i> View Receipt screenshot
                            </button>
                        </div>
                        ` : ''}
                    </div>
                `;
            } else {
                paymentsDiv.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem; font-style:italic;">No payment reference details</div>';
            }
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
