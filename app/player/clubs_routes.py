from flask import render_template, request, redirect, url_for, session, flash
from app.decorators import require_role
from datetime import datetime, timezone
from app.db import get_db
from app.player import player_bp
from app.player.routes import check_player_memberships_expiry

@player_bp.route('/clubs')
@require_role('player')
def clubs():
    player_id = session.get('user_id')
    db = get_db()
    clubs_list = []
    try:
        # Fetch all active clubs
        resp = db.table('clubs').select(
            'id, name, description, logo_url, location, membership_type, membership_fee, admin_id, profiles!admin_id(first_name, last_name)'
        ).eq('status', 'active').order('created_at', desc=True).execute()
        clubs_list = resp.data or []
        
        # Attach member count and player's status
        if clubs_list:
            club_ids = [c['id'] for c in clubs_list]
            
            # Batch fetch active members counts
            members_resp = db.table('club_memberships').select('club_id').in_('club_id', club_ids).eq('status', 'active').execute()
            member_counts = {}
            for m in (members_resp.data or []):
                member_counts[m['club_id']] = member_counts.get(m['club_id'], 0) + 1
                
            # Batch fetch player's status
            my_resp = db.table('club_memberships').select('club_id, status').in_('club_id', club_ids).eq('player_id', player_id).execute()
            my_status_map = {m['club_id']: m['status'] for m in (my_resp.data or [])}

            for c in clubs_list:
                c['member_count'] = member_counts.get(c['id'], 0)
                c['my_status'] = my_status_map.get(c['id'])

            # Batch fetch banner URLs from platform_settings
            keys = [f"club_banner_{c['id']}" for c in clubs_list]
            try:
                from app.db import get_admin_db
                admin_db = get_admin_db() or db
                b_res = admin_db.table('platform_settings').select('key, value').in_('key', keys).execute()
                b_map = {item['key'].replace('club_banner_', ''): item['value'] for item in (b_res.data or []) if item.get('value')}
                for c in clubs_list:
                    if not c.get('banner_url') and c['id'] in b_map:
                        c['banner_url'] = b_map[c['id']]
            except Exception:
                pass

        # Calculate summary metrics for filters and header
        joined_count = sum(1 for c in clubs_list if c.get('my_status') in ['active', 'pending'])
        active_joined_count = sum(1 for c in clubs_list if c.get('my_status') == 'active')
        free_count = sum(1 for c in clubs_list if c.get('membership_type') == 'free')
        paid_count = sum(1 for c in clubs_list if c.get('membership_type') == 'paid')

    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        joined_count = 0
        active_joined_count = 0
        free_count = 0
        paid_count = 0
        
    return render_template(
        'player/clubs.html',
        clubs=clubs_list,
        joined_count=joined_count,
        active_joined_count=active_joined_count,
        free_count=free_count,
        paid_count=paid_count
    )


@player_bp.route('/clubs/<club_id>')
@require_role('player')
def club_detail(club_id):
    player_id = session.get('user_id')
    db = get_db()
    check_player_memberships_expiry(db, player_id)
    club = None
    members = []
    events_list = []
    my_membership = None
    
    try:
        # 1. Fetch club details and admin profile
        club_resp = db.table('clubs').select(
            'id, name, description, logo_url, location, membership_type, membership_fee, admin_id, '
            'profiles!admin_id(id, first_name, last_name, dupr, elo, avatar_url)'
        ).eq('id', club_id).eq('status', 'active').single().execute()
        club = club_resp.data
        if not club:
            flash("Club not found.", "error")
            return redirect(url_for('player.clubs'))

        # Fetch banner URL for club
        if club and not club.get('banner_url'):
            try:
                from app.db import get_admin_db
                admin_db = get_admin_db() or db
                b_res = admin_db.table('platform_settings').select('value').eq('key', f"club_banner_{club['id']}").execute()
                if b_res.data and b_res.data[0].get('value'):
                    club['banner_url'] = b_res.data[0]['value']
            except Exception:
                pass
            
        # 2. Fetch fellow members (active memberships)
        members_resp = db.table('club_memberships').select(
            'id, joined_at, status, profiles!player_id(id, first_name, last_name, dupr, elo, avatar_url)'
        ).eq('club_id', club_id).eq('status', 'active').order('joined_at', desc=True).execute()
        
        # Attach initials to members
        members = []
        for m in (members_resp.data or []):
            prof = m.get('profiles') or {}
            first = prof.get('first_name') or 'P'
            last = prof.get('last_name') or ''
            initials = (first[0] + (last[0] if last else '')).upper()
            m['initials'] = initials
            m['name'] = f"{first} {last}".strip()
            m['avatar_url'] = prof.get('avatar_url') or None
            members.append(m)
        
        # 3. Fetch current user's membership details
        my_mem_resp = db.table('club_memberships').select('*').eq('club_id', club_id).eq('player_id', player_id).execute()
        if my_mem_resp.data:
            my_membership = my_mem_resp.data[0]
            
        # 4. Fetch club events (events where organizer_id = club's admin_id)
        events_resp = db.table('events').select(
            'id, title, event_date, type, location_label, status'
        ).eq('organizer_id', club['admin_id']).in_('status', ['registration_open', 'upcoming']).order('event_date').limit(6).execute()
        events_list = events_resp.data or []

        # 5. Compute club member analytics (Average DUPR & Club Leaderboard)
        dupr_values = []
        for m in members:
            p = m.get('profiles') or {}
            d = p.get('dupr')
            if d is not None:
                try:
                    dupr_values.append(float(d))
                except (ValueError, TypeError):
                    pass
        avg_dupr = round(sum(dupr_values) / len(dupr_values), 2) if dupr_values else None

        # Sort members by DUPR and Elo for internal club leaderboard
        top_members = sorted(
            members,
            key=lambda x: (
                float((x.get('profiles') or {}).get('dupr') or 0),
                int((x.get('profiles') or {}).get('elo') or 0)
            ),
            reverse=True
        )
        
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('player.clubs'))
        
    return render_template(
        'player/club_detail.html',
        club=club,
        members=members,
        top_members=top_members,
        avg_dupr=avg_dupr,
        my_membership=my_membership,
        events=events_list
    )


@player_bp.route('/my-clubs')
@require_role('player')
def my_clubs():
    player_id = session.get('user_id')
    db = get_db()
    check_player_memberships_expiry(db, player_id)
    my_clubs_list = []
    try:
        resp = db.table('club_memberships').select(
            'status, joined_at, clubs(id, name, description, logo_url, membership_type)'
        ).eq('player_id', player_id).neq('status', 'rejected').order('joined_at', desc=True).execute()
        my_clubs_list = resp.data or []
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        
    return render_template('player/my_clubs.html', my_clubs=my_clubs_list)


@player_bp.route('/clubs/<club_id>/join', methods=['POST'])
@require_role('player')
def join_club(club_id):
    player_id = session.get('user_id')
    db = get_db()
    
    try:
        club_resp = db.table('clubs').select('membership_type').eq('id', club_id).single().execute()
        if not club_resp.data:
            flash("Club not found.", "error")
            return redirect(url_for('player.clubs'))
            
        mem_type = club_resp.data['membership_type']
        
        # If paid, redirect to payment page
        if mem_type == 'paid':
            return redirect(url_for('player.club_payment', club_id=club_id))
            
        # If free, join instantly
        db.table('club_memberships').upsert({
            'club_id': club_id,
            'player_id': player_id,
            'status': 'active'
        }, on_conflict='club_id,player_id').execute()
        
        flash("You have successfully joined the club!", "success")
        
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('player.my_clubs'))


@player_bp.route('/clubs/<club_id>/payment', methods=['GET', 'POST'])
@require_role('player')
def club_payment(club_id):
    player_id = session.get('user_id')
    db = get_db()
    
    try:
        club_resp = db.table('clubs').select('id, name, membership_fee').eq('id', club_id).single().execute()
        club = club_resp.data
        if not club:
            flash("Club not found.", "error")
            return redirect(url_for('player.clubs'))
            
        if request.method == 'POST':
            gcash_ref = request.form.get('gcash_ref', '').strip()
            if not gcash_ref:
                flash("GCash Reference Number is required.", "error")
                return redirect(url_for('player.club_payment', club_id=club_id))
                
            import re
            if not re.match(r'^\d{13}$', gcash_ref):
                flash("Invalid GCash Reference Number format. Must be a 13-digit number.", "error")
                return redirect(url_for('player.club_payment', club_id=club_id))
                
            # Check duplicate reference number in club_memberships
            dup_resp = db.table('club_memberships').select('club_id, player_id').eq('gcash_ref', gcash_ref).execute()
            if dup_resp.data:
                is_dup = False
                for row in dup_resp.data:
                    if str(row.get('club_id')) != str(club_id) or str(row.get('player_id')) != str(player_id):
                        is_dup = True
                        break
                if is_dup:
                    flash("This GCash reference number has already been used for another membership.", "error")
                    return redirect(url_for('player.club_payment', club_id=club_id))
                
            receipt_file = request.files.get('receipt')
            receipt_url = None
            if receipt_file and receipt_file.filename:
                from app.upload_utils import validate_and_upload, ALLOWED_DOC_EXTENSIONS, MAX_DOC_SIZE
                receipt_url, upload_err = validate_and_upload(
                    db,
                    receipt_file,
                    bucket='kyc-documents',
                    prefix='club_receipt',
                    owner_id=player_id,
                    allowed_exts=ALLOWED_DOC_EXTENSIONS,
                    max_size=MAX_DOC_SIZE
                )
                if upload_err:
                    flash(f"Warning: Receipt upload failed - {upload_err}", "warning")
                    
            if not receipt_url:
                flash("Receipt screenshot is required for paid memberships.", "error")
                return redirect(url_for('player.club_payment', club_id=club_id))
                
            db.table('club_memberships').upsert({
                'club_id': club_id,
                'player_id': player_id,
                'status': 'pending',
                'gcash_ref': gcash_ref,
                'receipt_url': receipt_url,
                'joined_at': datetime.now(timezone.utc).isoformat()
            }, on_conflict='club_id,player_id').execute()
            
            flash("Payment submitted! Waiting for admin approval.", "success")
            return redirect(url_for('player.my_clubs'))
            
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('player.clubs'))
        
    return render_template('player/club_payment.html', club=club)


@player_bp.route('/clubs/<club_id>/leave', methods=['POST'])
@require_role('player')
def leave_club(club_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        db.table('club_memberships').delete().eq('club_id', club_id).eq('player_id', player_id).execute()
        flash("You have left the club.", "success")
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('player.my_clubs'))
