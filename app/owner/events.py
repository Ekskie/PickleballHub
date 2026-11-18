import time
import random
import json
from datetime import datetime
from flask import request, redirect, url_for, session, render_template, flash, jsonify, current_app
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.owner import owner_bp
from app.owner.routes import PH_TZ
from app.booking_utils import safe_time_hours

# ── Events (on owner's courts) ─────────────────────────────────────────────────
@owner_bp.route('/events')
@require_role('owner')
def events():
    owner_id = session.get('user_id')
    db = get_db()
    events_list = []
    try:
        # Get facilities owned by this owner
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]

        if fac_ids:
            ev_resp = db.table('events').select(
                'id, title, type, format, event_date, start_time, end_time, max_players, status, location_label, organizer_id, '
                'gcash_ref, rejection_reason, facility_id, facilities(name), profiles!organizer_id(first_name, last_name, email, phone)'
            ).in_('facility_id', fac_ids).order('event_date', desc=False).execute()
            events_list = ev_resp.data or []

            # Attach registration count & booked courts (optimized batch queries)
            if events_list:
                ev_ids = [ev['id'] for ev in events_list]
                reg_resp = db.table('event_registrations').select('event_id').in_('event_id', ev_ids).eq('status', 'registered').execute()
                reg_data = reg_resp.data or []
                
                from collections import Counter
                reg_counts = Counter(r['event_id'] for r in reg_data)
                
                court_resp = db.table('event_courts').select('event_id, court_id, courts(name, hourly_rate)').in_('event_id', ev_ids).execute()
                courts_by_ev = {}
                for c in (court_resp.data or []):
                    eid = c['event_id']
                    if eid not in courts_by_ev:
                        courts_by_ev[eid] = []
                    if c.get('courts'):
                        courts_by_ev[eid].append(c['courts'])

                for ev in events_list:
                    ev['registered_count'] = reg_counts[ev['id']]
                    ev['courts'] = courts_by_ev.get(ev['id'], [])
                    try:
                        sh = safe_time_hours(ev.get('start_time'))
                        eh = safe_time_hours(ev.get('end_time'))
                        hrs = max(0.5, eh - sh) if eh > sh else 1.0
                    except Exception:
                        hrs = 1.0
                    tot_rate = sum(float(c.get('hourly_rate') or 0) for c in ev['courts'])
                    ev['total_court_fee'] = tot_rate * hrs
                    ev['duration_hours'] = round(hrs, 1)

    except Exception as e:
        current_app.logger.error(f"Error loading events for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    pending_count = sum(1 for e in events_list if e.get('status') == 'pending_approval')
    total_events = len(events_list)
    active_count = sum(1 for e in events_list if e.get('status') in ['registration_open', 'upcoming'])
    total_players = sum(e.get('registered_count', 0) for e in events_list)
    kpis = {
        'total_events': total_events,
        'active_count': active_count,
        'pending_count': pending_count,
        'total_players': total_players
    }
    return render_template('owner/events.html', events=events_list, pending_count=pending_count, kpis=kpis)


# ── Owner Event Approval & Rejection ──────────────────────────────────────────
@owner_bp.route('/events/<event_id>/approve', methods=['POST'])
@require_role('owner')
def approve_event(event_id):
    owner_id = session.get('user_id')
    db = get_admin_db()
    try:
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        if not fac_ids:
            flash("Unauthorized.", "error")
            return redirect(url_for('owner.events'))

        ev_resp = db.table('events').select('*, facilities(name)').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        event = ev_resp.data
        if not event:
            flash("Event not found or unauthorized.", "error")
            return redirect(url_for('owner.events'))

        # Verify court conflicts one more time before approval
        from app.booking_utils import check_court_conflict
        court_resp = db.table('event_courts').select('court_id, courts(name)').eq('event_id', event_id).execute()
        for c in (court_resp.data or []):
            cid = c['court_id']
            has_conf, conf_detail = check_court_conflict(db, cid, event['event_date'], event['start_time'], event['end_time'], exclude_event_id=event_id)
            if has_conf:
                c_label = conf_detail.get('label') or conf_detail.get('title') or 'Scheduled booking'
                flash(f"Cannot approve: Court '{c.get('courts', {}).get('name', 'Court')}' conflicts with {c_label} ({conf_detail['start_time']}-{conf_detail['end_time']}).", "error")
                return redirect(url_for('owner.events'))

        # Update event status to registration_open
        now_iso = datetime.now(PH_TZ).isoformat()
        db.table('events').update({
            'status': 'registration_open',
            'approved_by': owner_id,
            'approved_at': now_iso
        }).eq('id', event_id).execute()

        # Send notification to organizer
        facility_name = event.get('facilities', {}).get('name') or "Facility"
        db.table('notifications').insert({
            'user_id': event['organizer_id'],
            'title': f"Event Approved: {event['title']}",
            'message': f"Your event '{event['title']}' has been approved by {facility_name}! Player registrations are now open.",
            'type': 'success',
            'link': url_for('clubadmin.events')
        }).execute()

        # Send status update chat to organizer
        try:
            from app.chats import notify_event_status_chat
            notify_event_status_chat(db, event_id, 'approved', owner_id)
        except Exception as chat_err:
            current_app.logger.warning(f"Error sending approval chat: {chat_err}")

        flash(f'Event "{event["title"]}" approved! Courts are confirmed and registrations are now open.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error approving event {event_id}: {e}")
        flash('An error occurred while approving event.', 'error')

    return redirect(url_for('owner.events'))


@owner_bp.route('/events/<event_id>/reject', methods=['POST'])
@require_role('owner')
def reject_event(event_id):
    owner_id = session.get('user_id')
    db = get_admin_db()
    reason = request.form.get('rejection_reason', '').strip() or 'Facility unavailable during requested time'
    try:
        fac_resp = db.table('facilities').select('id, name').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        if not fac_ids:
            flash("Unauthorized.", "error")
            return redirect(url_for('owner.events'))

        ev_resp = db.table('events').select('*, facilities(name)').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        event = ev_resp.data
        if not event:
            flash("Event not found or unauthorized.", "error")
            return redirect(url_for('owner.events'))

        db.table('events').update({
            'status': 'rejected',
            'rejection_reason': reason
        }).eq('id', event_id).execute()

        # Send notification to organizer
        facility_name = event.get('facilities', {}).get('name') or "Facility"
        db.table('notifications').insert({
            'user_id': event['organizer_id'],
            'title': f"Event Booking Declined: {event['title']}",
            'message': f"Your event court booking for '{event['title']}' was declined by {facility_name}. Reason: {reason}",
            'type': 'error',
            'link': url_for('clubadmin.events')
        }).execute()

        # Send status update chat to organizer
        try:
            from app.chats import notify_event_status_chat
            notify_event_status_chat(db, event_id, 'rejected', owner_id, reason=reason)
        except Exception as chat_err:
            current_app.logger.warning(f"Error sending rejection chat: {chat_err}")

        flash(f'Event "{event["title"]}" booking request was declined.', 'info')
    except Exception as e:
        current_app.logger.error(f"Error rejecting event {event_id}: {e}")
        flash('An error occurred while declining event.', 'error')

    return redirect(url_for('owner.events'))


@owner_bp.route('/events/<event_id>/participants')
@require_role('owner')
def event_participants(event_id):
    owner_id = session.get('user_id')
    db = get_db()
    event_details = None
    participants = []
    try:
        # Verify event belongs to one of owner's facilities
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        
        if fac_ids:
            ev_resp = db.table('events').select('id, title, event_date, entry_fee, prize_pool').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
            event_details = ev_resp.data
            
            if event_details:
                # Fetch participants with joined profiles (email is fetched directly from database)
                reg_resp = db.table('event_registrations').select(
                    'id, status, registered_at, player_id, check_in_status, checked_in_at, profiles!player_id(first_name, last_name, phone, avatar_url, email)'
                ).eq('event_id', event_id).execute()
                participants = reg_resp.data or []
            else:
                flash("Event not found or unauthorized.", "error")
                return redirect(url_for('owner.events'))
                
    except Exception as e:
        current_app.logger.error(f"Error fetching participants for event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return render_template('owner/event_participants.html', event=event_details, participants=participants)

@owner_bp.route('/events/<event_id>/registrations/<reg_id>/checkin', methods=['POST'])
@require_role('owner')
def event_check_in(event_id, reg_id):
    owner_id = session.get('user_id')
    db = get_admin_db()
    
    status = request.form.get('status', 'pending')
    if status not in ['pending', 'checked_in', 'no_show']:
        status = 'pending'
        
    checked_in_at = datetime.now(PH_TZ).isoformat() if status == 'checked_in' else None
    
    try:
        # Verify event belongs to one of owner's facilities
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        
        if not fac_ids:
            flash("Unauthorized.", "error")
            return redirect(url_for('owner.events'))
            
        ev_resp = db.table('events').select('id').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        if not ev_resp.data:
            flash("Event not found or unauthorized.", "error")
            return redirect(url_for('owner.events'))
            
        db.table('event_registrations').update({
            'check_in_status': status,
            'checked_in_at': checked_in_at
        }).eq('id', reg_id).eq('event_id', event_id).execute()
        
        flash("Participant attendance updated.", "success")
    except Exception as e:
        current_app.logger.error(f"Error checking in participant {reg_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.event_participants', event_id=event_id))

@owner_bp.route('/tournaments/<event_id>/manage')
@require_role('owner')
def tournament_manage(event_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    try:
        # Verify ownership
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        if not fac_ids:
            flash("Unauthorized.", "error")
            return redirect(url_for('owner.events'))
            
        ev_resp = db.table('events').select('*').eq('id', event_id).in_('facility_id', fac_ids).eq('type', 'tournament').single().execute()
        event = ev_resp.data
        if not event:
            flash("Tournament not found.", "error")
            return redirect(url_for('owner.events'))
            
        # Get all tournaments for dropdown
        all_t_resp = db.table('events').select('id, title').in_('facility_id', fac_ids).eq('type', 'tournament').execute()
        all_tournaments = all_t_resp.data or []
        
        # Get participants (both registered users and walk-ins)
        reg_resp = db.table('event_registrations').select(
            'id, player_id, is_walkin, guest_name, skill_level, estimated_elo, status, registered_at, profiles!player_id(first_name, last_name, avatar_url, elo, dupr, proficiency)'
        ).eq('event_id', event_id).eq('status', 'registered').order('registered_at').execute()
        participants = reg_resp.data or []
        
        # Get matches
        matches_resp = db.table('tournament_matches').select(
            'id, round_number, match_number, player1_id, player2_id, winner_id, player1_score, player2_score, status, played_at, court_id, court_name, referee_name, '
            'player1_guest_name, player2_guest_name, winner_guest_name, player1_reg_id, player2_reg_id, winner_reg_id, '
            'player1:profiles!player1_id(id, first_name, last_name, avatar_url), '
            'player2:profiles!player2_id(id, first_name, last_name, avatar_url), '
            'winner:profiles!winner_id(id, first_name, last_name, avatar_url)'
        ).eq('event_id', event_id).order('round_number').order('match_number').execute()
        matches = matches_resp.data or []
        
        # Get booked courts for this event
        court_resp = db.table('event_courts').select(
            'court_id, courts(id, name)'
        ).eq('event_id', event_id).execute()
        booked_courts = court_resp.data or []
        
        has_bracket = len(matches) > 0
        can_reset = has_bracket and not any(m.get('player1_score') is not None for m in matches)
        
        return render_template('owner/tournament_manage.html', 
                               event=event, 
                               all_tournaments=all_tournaments,
                               participants=participants,
                               matches=matches,
                               has_bracket=has_bracket,
                               can_reset=can_reset,
                               booked_courts=booked_courts)
                               
    except Exception as e:
        current_app.logger.error(f"Error managing tournament {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('owner.events'))

def generate_seed_order(n):
    """Generate official single-elimination tournament seed pairing order for bracket size n (power of 2)."""
    order = [1, 2]
    while len(order) < n:
        next_order = []
        target = len(order) * 2 + 1
        for s in order:
            next_order.append(s)
            next_order.append(target - s)
        order = next_order
    return order

@owner_bp.route('/tournaments/<event_id>/bracket/reset', methods=['POST'])
@require_role('owner')
def bracket_reset(event_id):
    owner_id = session.get('user_id')
    db = get_admin_db() or get_db()
    try:
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        db.table('events').select('id').eq('id', event_id).in_('facility_id', fac_ids).single().execute()

        comp_chk = db.table('tournament_matches').select('id, player1_score').eq('event_id', event_id).execute()
        matches = comp_chk.data or []
        if any(m.get('player1_score') is not None for m in matches):
            flash("Cannot reset bracket because one or more matches have already been scored.", "warning")
            return redirect(url_for('owner.tournament_manage', event_id=event_id))

        db.table('tournament_matches').delete().eq('event_id', event_id).execute()
        db.table('events').update({'status': 'registration_open'}).eq('id', event_id).execute()
        flash("Bracket has been reset. You can now adjust players and re-generate.", "success")
    except Exception as e:
        current_app.logger.error(f"Error resetting bracket for owner: {e}")
        flash('Failed to reset bracket.', 'error')

    return redirect(url_for('owner.tournament_manage', event_id=event_id))

@owner_bp.route('/tournaments/<event_id>/bracket/generate', methods=['POST'])
@require_role('owner')
def bracket_generate(event_id):
    owner_id = session.get('user_id')
    db = get_admin_db() or get_db()
    seed_mode = request.form.get('seed_mode', 'fair')
    
    try:
        # Verify ownership
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        db.table('events').select('id').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        
        # Get participants (both registered users and walk-ins)
        reg_resp = db.table('event_registrations').select(
            'id, player_id, is_walkin, guest_name, skill_level, estimated_elo, profiles!player_id(first_name, last_name, elo, dupr, proficiency)'
        ).eq('event_id', event_id).eq('status', 'registered').execute()
        raw_regs = reg_resp.data or []
        
        if len(raw_regs) < 2:
            flash("At least 2 players are required to generate a tournament bracket.", "warning")
            return redirect(url_for('owner.tournament_manage', event_id=event_id))
            
        from app.ratings import get_initial_rating
        players = []
        for r in raw_regs:
            prof = r.get('profiles')
            if r.get('is_walkin') or not r.get('player_id'):
                p_name = (r.get('guest_name') or 'Guest Walk-in').strip()
                p_elo = r.get('estimated_elo') or get_initial_rating(r.get('skill_level'))[0]
                players.append({
                    'player_id': None,
                    'guest_name': p_name,
                    'reg_id': r['id'],
                    'elo': p_elo,
                    'is_walkin': True
                })
            else:
                p_first = prof.get('first_name') if prof else ''
                p_last = prof.get('last_name') if prof else ''
                p_name = f"{p_first} {p_last}".strip() or 'Player'
                p_elo = prof.get('elo') if prof and prof.get('elo') is not None else get_initial_rating(prof.get('proficiency') if prof else 'beginner')[0]
                players.append({
                    'player_id': r['player_id'],
                    'guest_name': None,
                    'reg_id': r['id'],
                    'elo': p_elo,
                    'is_walkin': False
                })

        # Calculate next power of 2 bracket size
        N = len(players)
        P = 2
        while P < N:
            P *= 2

        if seed_mode == 'fair':
            players.sort(key=lambda p: -p['elo'])
            seed_order = generate_seed_order(P)
            seed_map = {}
            for idx, p in enumerate(players):
                seed_map[idx + 1] = p
            for s in range(N + 1, P + 1):
                seed_map[s] = None
        else:
            random.shuffle(players)
            seed_order = generate_seed_order(P)
            seed_map = {}
            for idx, p in enumerate(players):
                seed_map[idx + 1] = p
            for s in range(N + 1, P + 1):
                seed_map[s] = None

        matches_to_insert = []
        match_num = 1
        for i in range(0, P, 2):
            s1 = seed_order[i]
            s2 = seed_order[i + 1]
            p1 = seed_map[s1]
            p2 = seed_map[s2]

            if not p1 and p2:
                p1, p2 = p2, p1

            if not p1 and not p2:
                continue

            is_bye = (p2 is None)
            matches_to_insert.append({
                'event_id': event_id,
                'round_number': 1,
                'match_number': match_num,
                'player1_id': p1['player_id'] if p1 else None,
                'player1_guest_name': p1['guest_name'] if p1 else None,
                'player1_reg_id': p1['reg_id'] if p1 else None,
                'player2_id': p2['player_id'] if p2 else None,
                'player2_guest_name': p2['guest_name'] if p2 else None,
                'player2_reg_id': p2['reg_id'] if p2 else None,
                'status': 'completed' if is_bye else 'pending',
                'winner_id': p1['player_id'] if is_bye else None,
                'winner_guest_name': p1['guest_name'] if is_bye else None,
                'winner_reg_id': p1['reg_id'] if is_bye else None
            })
            match_num += 1
            
        if matches_to_insert:
            db.table('tournament_matches').insert(matches_to_insert).execute()
            try:
                db.table('events').update({'status': 'in_progress'}).eq('id', event_id).execute()
            except Exception:
                pass
            
        flash(f"Bracket generated successfully ({'Fair Seeding by ELO' if seed_mode == 'fair' else 'Random Draw'})!", "success")
        
    except Exception as e:
        current_app.logger.error(f"Error generating tournament bracket {event_id}: {e}")
        flash('An error occurred while generating the bracket.', 'error')
        
    return redirect(url_for('owner.tournament_manage', event_id=event_id))

def _advance_bracket(db, event_id):
    """Check current round completion and auto-generate next round or declare champion."""
    try:
        all_m = db.table('tournament_matches').select(
            'id, round_number, status, winner_id, winner_guest_name, winner_reg_id'
        ).eq('event_id', event_id).order('round_number').execute()
        matches = all_m.data or []
        if not matches:
            return

        max_round = max(m['round_number'] for m in matches)
        round_matches = [m for m in matches if m['round_number'] == max_round]

        if any(m['status'] != 'completed' for m in round_matches):
            return  # Round not finished yet

        winners = []
        for m in round_matches:
            winners.append({
                'id': m.get('winner_id'),
                'guest_name': m.get('winner_guest_name'),
                'reg_id': m.get('winner_reg_id')
            })

        if len(winners) == 1:
            # 🏆 Champion decided
            db.table('events').update({'status': 'completed'}).eq('id', event_id).execute()
            if winners[0]['id']:
                try:
                    db.table('notifications').insert({
                        'user_id': winners[0]['id'],
                        'title': '🏆 Tournament Champion!',
                        'message': 'Congratulations! You have won the tournament!',
                        'type': 'success'
                    }).execute()
                except Exception:
                    pass
            return

        # Pair winners → next round
        next_round = max_round + 1
        match_num = 1
        next_matches = []
        for i in range(0, len(winners), 2):
            w1 = winners[i]
            w2 = winners[i + 1] if i + 1 < len(winners) else None
            is_bye = (w2 is None)
            next_matches.append({
                'event_id': event_id,
                'round_number': next_round,
                'match_number': match_num,
                'player1_id': w1['id'],
                'player1_guest_name': w1['guest_name'],
                'player1_reg_id': w1['reg_id'],
                'player2_id': w2['id'] if w2 else None,
                'player2_guest_name': w2['guest_name'] if w2 else None,
                'player2_reg_id': w2['reg_id'] if w2 else None,
                'status': 'completed' if is_bye else 'pending',
                'winner_id': w1['id'] if is_bye else None,
                'winner_guest_name': w1['guest_name'] if is_bye else None,
                'winner_reg_id': w1['reg_id'] if is_bye else None
            })
            match_num += 1

        if next_matches:
            db.table('tournament_matches').insert(next_matches).execute()
            if len(next_matches) == 1 and next_matches[0]['status'] == 'completed':
                _advance_bracket(db, event_id)
    except Exception as e:
        current_app.logger.error(f"Owner bracket advancement error: {e}")


@owner_bp.route('/tournaments/<event_id>/matches/<match_id>/score', methods=['POST'])
@require_role('owner')
def match_score(event_id, match_id):
    owner_id = session.get('user_id')
    db = get_admin_db() or get_db()

    p1_score = request.form.get('player1_score', type=int)
    p2_score = request.form.get('player2_score', type=int)
    winner_side = request.form.get('winner_side') # 'player1' or 'player2'
    winner_id_param = request.form.get('winner_id')

    try:
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        db.table('events').select('id').eq('id', event_id).in_('facility_id', fac_ids).single().execute()

        # Get match before updating to pass to ratings logic
        m_resp = db.table('tournament_matches').select('*').eq('id', match_id).single().execute()
        prev_match = m_resp.data
        if not prev_match:
            flash("Match not found.", "error")
            return redirect(url_for('owner.tournament_manage', event_id=event_id))

        is_p1_winner = False
        if winner_side == 'player1' or winner_id_param == 'player1' or (winner_id_param and winner_id_param == prev_match.get('player1_id')):
            is_p1_winner = True
        elif winner_side == 'player2' or winner_id_param == 'player2' or (winner_id_param and winner_id_param == prev_match.get('player2_id')):
            is_p1_winner = False
        else:
            is_p1_winner = (p1_score or 0) >= (p2_score or 0)

        winner_id = prev_match.get('player1_id') if is_p1_winner else prev_match.get('player2_id')
        winner_guest_name = prev_match.get('player1_guest_name') if is_p1_winner else prev_match.get('player2_guest_name')
        winner_reg_id = prev_match.get('player1_reg_id') if is_p1_winner else prev_match.get('player2_reg_id')

        db.table('tournament_matches').update({
            'player1_score': p1_score,
            'player2_score': p2_score,
            'winner_id': winner_id,
            'winner_guest_name': winner_guest_name,
            'winner_reg_id': winner_reg_id,
            'status': 'completed',
            'played_at': datetime.now(PH_TZ).isoformat()
        }).eq('id', match_id).eq('event_id', event_id).execute()

        # Calculate and update player ratings
        from app.ratings import update_match_ratings
        update_match_ratings(db, match_id, prev_match=prev_match)

        _advance_bracket(db, event_id)
        flash("Score recorded! Bracket and ratings updated.", "success")

    except Exception as e:
        current_app.logger.error(f"Error submitting match score: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.tournament_manage', event_id=event_id))

@owner_bp.route('/tournaments/<event_id>/matches/<match_id>/assign', methods=['POST'])
@require_role('owner')
def match_assign(event_id, match_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    court_id = request.form.get('court_id') or None
    court_name = request.form.get('court_name') or None
    referee_name = request.form.get('referee_name') or None
    
    if court_id and not court_name:
        try:
            c_resp = db.table('courts').select('name').eq('id', court_id).single().execute()
            if c_resp.data:
                court_name = c_resp.data['name']
        except Exception as ce:
            current_app.logger.error(f"Failed to resolve court name for owner: {ce}")

    try:
        # Verify ownership
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        db.table('events').select('id').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        
        db.table('tournament_matches').update({
            'court_id': court_id,
            'court_name': court_name,
            'referee_name': referee_name
        }).eq('id', match_id).eq('event_id', event_id).execute()
        
        flash("Match assignment updated.", "success")
    except Exception as e:
        current_app.logger.error(f"Error assigning match: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.tournament_manage', event_id=event_id))

# ── Create Event ───────────────────────────────────────────────────────────────
@owner_bp.route('/events/create', methods=['GET'])
@require_role('owner')
def create_event_page():
    owner_id = session.get('user_id')
    db = get_db()
    facilities_list = []
    try:
        fac_resp = db.table('facilities').select('id, name, location').eq('owner_id', owner_id).eq('status', 'active').execute()
        facilities_list = fac_resp.data or []
    except Exception as e:
        current_app.logger.error(f"Error loading create event page for owner {owner_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
    return render_template('owner/create_event.html', facilities=facilities_list)


@owner_bp.route('/events/create', methods=['POST'])
@require_role('owner')
def create_event():
    owner_id      = session.get('user_id')
    facility_id   = request.form.get('facility_id')
    court_ids     = request.form.getlist('court_ids')
    title         = request.form.get('title', '').strip()
    event_type    = request.form.get('type', 'social')
    description   = request.form.get('description', '').strip()
    event_date    = request.form.get('event_date')
    start_time    = request.form.get('start_time')
    end_time      = request.form.get('end_time')
    max_players   = request.form.get('max_players', 16)
    entry_fee     = request.form.get('entry_fee', 0)
    location_label = request.form.get('location_label', '').strip()
    
    event_format  = request.form.get('format', 'Doubles').strip()
    prize_pool    = request.form.get('prize_pool', 0)
    reg_type      = request.form.get('registration_type', 'paid')

    # Parse granular schedule_slots JSON
    schedule_slots_raw = request.form.get('schedule_slots')
    schedule_slots = []
    if schedule_slots_raw:
        try:
            parsed = json.loads(schedule_slots_raw)
            for item in parsed:
                slots = sorted(list(set(int(x) for x in item.get('slots', []))))
                if slots:
                    schedule_slots.append({
                        'court_id': item.get('court_id'),
                        'court_name': item.get('court_name', ''),
                        'slots': slots
                    })
        except Exception as e:
            current_app.logger.warning(f"Could not parse schedule_slots: {e}")
            schedule_slots = []

    if schedule_slots:
        court_ids = [s['court_id'] for s in schedule_slots if s.get('court_id')]
        all_hours = [h for s in schedule_slots for h in s.get('slots', [])]
        if all_hours:
            min_h = min(all_hours)
            max_h = max(all_hours) + 1
            start_time = f"{min_h:02d}:00"
            end_time = f"{max_h:02d}:00"
    
    if reg_type == 'free':
        entry_fee = 0

    if not all([title, facility_id, event_date, start_time, end_time]):
        flash('Please fill all required fields.', 'error')
        return redirect(url_for('owner.create_event_page'))

    db = get_db()
    
    # Check court conflicts before inserting
    if facility_id and schedule_slots:
        from app.booking_utils import check_court_conflict, group_slots_to_ranges
        for item in schedule_slots:
            cid = item['court_id']
            ranges = group_slots_to_ranges(item.get('slots', []))
            for r in ranges:
                r_start, r_end = r.split('-')
                has_conf, conf_detail = check_court_conflict(db, cid, event_date, r_start, r_end)
                if has_conf:
                    time_range = conf_detail.get('time_range_12h') or f"{conf_detail.get('start_time')} – {conf_detail.get('end_time')}"
                    court_lbl = conf_detail.get('court_name') or item.get('court_name') or 'court'
                    flash(f"Court conflict detected on {court_lbl}: {conf_detail['label']} is scheduled from {time_range}. Please adjust your selected slots.", 'error')
                    return redirect(url_for('owner.create_event_page'))
    elif facility_id and court_ids:
        from app.booking_utils import check_court_conflict
        for cid in court_ids:
            has_conf, conf_detail = check_court_conflict(db, cid, event_date, start_time, end_time)
            if has_conf:
                time_range = conf_detail.get('time_range_12h') or f"{conf_detail.get('start_time')} – {conf_detail.get('end_time')}"
                flash(f"Court conflict detected: {conf_detail['label']} is scheduled from {time_range}. Please select different courts or times.", 'error')
                return redirect(url_for('owner.create_event_page'))
    
    # Handle Image Upload
    image_file = request.files.get('image')
    image_url = None
    if image_file and image_file.filename:
        try:
            filename = f"events/{owner_id}_{int(time.time())}.{image_file.filename.split('.')[-1]}"
            file_bytes = image_file.read()
            db.storage.from_('community-images').upload(
                file=file_bytes,
                path=filename,
                file_options={"content-type": image_file.content_type}
            )
            image_url = db.storage.from_('community-images').get_public_url(filename)
        except Exception as e:
            current_app.logger.error(f"Image upload error: {e}")
            flash(f'Warning: Image could not be uploaded.', 'error')

    from app.booking_utils import inject_schedule_slots_into_desc
    stored_desc = inject_schedule_slots_into_desc(description, schedule_slots) if schedule_slots else description

    insert_payload = {
        'organizer_id': owner_id,
        'facility_id': facility_id,
        'title': title,
        'type': event_type,
        'format': event_format,
        'description': stored_desc,
        'event_date': event_date,
        'start_time': start_time,
        'end_time': end_time,
        'max_players': int(max_players),
        'entry_fee': float(entry_fee),
        'prize_pool': float(prize_pool) if prize_pool else 0,
        'location_label': location_label,
        'image_url': image_url,
        'status': 'registration_open',
    }
    if schedule_slots:
        insert_payload['schedule_slots'] = schedule_slots

    try:
        try:
            ev_resp = db.table('events').insert(insert_payload).execute()
        except Exception as insert_err:
            if 'schedule_slots' in insert_payload and ('column' in str(insert_err).lower() or '42703' in str(insert_err)):
                insert_payload.pop('schedule_slots', None)
                ev_resp = db.table('events').insert(insert_payload).execute()
            else:
                raise insert_err

        if ev_resp.data and court_ids:
            event_id = ev_resp.data[0]['id']
            court_rows = [{'event_id': event_id, 'court_id': cid} for cid in court_ids]
            db.table('event_courts').insert(court_rows).execute()

        flash(f'Event "{title}" created successfully!', 'success')
    except Exception as e:
        current_app.logger.error(f"Error creating event: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.events'))

@owner_bp.route('/events/<event_id>/edit', methods=['GET', 'POST'])
@require_role('owner')
def edit_event(event_id):
    owner_id = session.get('user_id')
    db = get_db()
    
    try:
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        if not fac_ids:
            flash("Unauthorized or event not found.", "error")
            return redirect(url_for('owner.events'))
            
        ev_resp = db.table('events').select('*').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        event = ev_resp.data
        if not event:
            flash("Event not found.", "error")
            return redirect(url_for('owner.events'))
            
        if request.method == 'GET':
            from app.booking_utils import extract_schedule_slots, clean_event_description
            fac_full_resp = db.table('facilities').select('id, name, location').eq('owner_id', owner_id).eq('status', 'active').execute()
            facilities_list = fac_full_resp.data or []
            selected_court_ids = []
            try:
                ec_resp = db.table('event_courts').select('court_id').eq('event_id', event_id).execute()
                selected_court_ids = [r['court_id'] for r in (ec_resp.data or [])]
            except Exception as e:
                current_app.logger.warning(f"Could not load event_courts: {e}")
                
            schedule_slots = extract_schedule_slots(event)
            event_clean = dict(event)
            event_clean['description'] = clean_event_description(event.get('description'))
            
            return render_template(
                'owner/edit_event.html',
                event=event_clean,
                facilities=facilities_list,
                selected_court_ids=selected_court_ids,
                event_schedule_slots=json.dumps(schedule_slots or [])
            )
            
        # POST logic
        facility_id   = request.form.get('facility_id')
        title         = request.form.get('title', '').strip()
        event_type    = request.form.get('type', 'social')
        description   = request.form.get('description', '').strip()
        event_date    = request.form.get('event_date')
        start_time    = request.form.get('start_time')
        end_time      = request.form.get('end_time')
        max_players   = request.form.get('max_players', 16)
        entry_fee     = request.form.get('entry_fee', 0)
        location_label = request.form.get('location_label', '').strip()
        event_format  = request.form.get('format', 'Doubles').strip()
        prize_pool    = request.form.get('prize_pool', 0)
        reg_type      = request.form.get('registration_type', 'paid')

        # Parse schedule_slots
        schedule_slots_raw = request.form.get('schedule_slots')
        schedule_slots = []
        if schedule_slots_raw:
            try:
                parsed = json.loads(schedule_slots_raw)
                for item in parsed:
                    slots = sorted(list(set(int(x) for x in item.get('slots', []))))
                    if slots:
                        schedule_slots.append({
                            'court_id': item.get('court_id'),
                            'court_name': item.get('court_name', ''),
                            'slots': slots
                        })
            except Exception as e:
                current_app.logger.warning(f"Could not parse schedule_slots: {e}")
                schedule_slots = []

        if schedule_slots:
            court_ids = [s['court_id'] for s in schedule_slots if s.get('court_id')]
            all_hours = [h for s in schedule_slots for h in s.get('slots', [])]
            if all_hours:
                min_h = min(all_hours)
                max_h = max(all_hours) + 1
                start_time = f"{min_h:02d}:00"
                end_time = f"{max_h:02d}:00"
        else:
            court_ids = request.form.getlist('court_ids')
        
        if reg_type == 'free':
            entry_fee = 0
            
        if not all([title, facility_id, event_date, start_time, end_time]):
            flash('Please fill all required fields.', 'error')
            return redirect(url_for('owner.edit_event', event_id=event_id))

        # Check court conflicts before updating
        if facility_id and schedule_slots:
            from app.booking_utils import check_court_conflict, group_slots_to_ranges
            for item in schedule_slots:
                cid = item['court_id']
                ranges = group_slots_to_ranges(item.get('slots', []))
                for r in ranges:
                    r_start, r_end = r.split('-')
                    has_conf, conf_detail = check_court_conflict(db, cid, event_date, r_start, r_end, exclude_event_id=event_id)
                    if has_conf:
                        time_range = conf_detail.get('time_range_12h') or f"{conf_detail.get('start_time')} – {conf_detail.get('end_time')}"
                        court_lbl = conf_detail.get('court_name') or item.get('court_name') or 'court'
                        flash(f"Court conflict detected on {court_lbl}: {conf_detail['label']} is scheduled from {time_range}. Please adjust your selected slots.", 'error')
                        return redirect(url_for('owner.edit_event', event_id=event_id))
        elif facility_id and court_ids:
            from app.booking_utils import check_court_conflict
            for cid in court_ids:
                has_conf, conf_detail = check_court_conflict(db, cid, event_date, start_time, end_time, exclude_event_id=event_id)
                if has_conf:
                    time_range = conf_detail.get('time_range_12h') or f"{conf_detail.get('start_time')} – {conf_detail.get('end_time')}"
                    flash(f"Court conflict detected: {conf_detail['label']} is scheduled from {time_range}. Please select different courts or times.", 'error')
                    return redirect(url_for('owner.edit_event', event_id=event_id))

        from app.booking_utils import inject_schedule_slots_into_desc
        stored_desc = inject_schedule_slots_into_desc(description, schedule_slots) if schedule_slots else description

        update_data = {
            'facility_id': facility_id,
            'title': title,
            'type': event_type,
            'format': event_format,
            'description': stored_desc,
            'event_date': event_date,
            'start_time': start_time,
            'end_time': end_time,
            'max_players': int(max_players),
            'entry_fee': float(entry_fee),
            'prize_pool': float(prize_pool) if prize_pool else 0,
            'location_label': location_label,
        }
        if schedule_slots:
            update_data['schedule_slots'] = schedule_slots
        
        # Handle Image Upload
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            try:
                filename = f"events/{owner_id}_{int(time.time())}.{image_file.filename.split('.')[-1]}"
                file_bytes = image_file.read()
                db.storage.from_('community-images').upload(
                    file=file_bytes,
                    path=filename,
                    file_options={"content-type": image_file.content_type}
                )
                update_data['image_url'] = db.storage.from_('community-images').get_public_url(filename)
            except Exception as e:
                current_app.logger.error(f"Image edit upload error: {e}")
                flash(f'Warning: Image could not be uploaded.', 'warning')
                
        try:
            db.table('events').update(update_data).eq('id', event_id).execute()
        except Exception as update_err:
            if 'schedule_slots' in update_data and ('column' in str(update_err).lower() or '42703' in str(update_err)):
                update_data.pop('schedule_slots', None)
                db.table('events').update(update_data).eq('id', event_id).execute()
            else:
                raise update_err
        
        # Also update courts if needed
        if court_ids:
            # delete existing courts and re-insert
            db.table('event_courts').delete().eq('event_id', event_id).execute()
            court_rows = [{'event_id': event_id, 'court_id': cid} for cid in court_ids]
            db.table('event_courts').insert(court_rows).execute()
            
        flash('Event updated successfully!', 'success')
        return redirect(url_for('owner.event_participants', event_id=event_id))
        
    except Exception as e:
        current_app.logger.error(f"Error editing event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('owner.events'))

@owner_bp.route('/events/<event_id>/delete', methods=['POST'])
@require_role('owner')
def delete_event(event_id):
    owner_id = session.get('user_id')
    db = get_db()
    try:
        fac_resp = db.table('facilities').select('id').eq('owner_id', owner_id).execute()
        fac_ids = [f['id'] for f in (fac_resp.data or [])]
        if not fac_ids:
            flash("Unauthorized.", "error")
            return redirect(url_for('owner.events'))
            
        # Check if event exists and belongs to owner
        ev_resp = db.table('events').select('title').eq('id', event_id).in_('facility_id', fac_ids).single().execute()
        if not ev_resp.data:
            flash("Event not found or unauthorized.", "error")
            return redirect(url_for('owner.events'))
            
        title = ev_resp.data['title']
        
        # Notify registered players before deleting (batch insert)
        reg_resp = db.table('event_registrations').select('player_id').eq('event_id', event_id).execute()
        if reg_resp.data:
            notifs = [
                {
                    'user_id': r['player_id'],
                    'title': f'Event Cancelled: {title}',
                    'message': f'The event "{title}" you registered for has been cancelled and removed.',
                    'type': 'system'
                } for r in reg_resp.data
            ]
            db.table('notifications').insert(notifs).execute()
            
        # Delete event (registrations deleted automatically due to cascade)
        db.table('events').delete().eq('id', event_id).execute()
        flash(f'Event "{title}" deleted successfully.', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error deleting event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')
        
    return redirect(url_for('owner.events'))


# ── API: Courts by Facility & Timeline (for JS fetch in create_event) ─────────
@owner_bp.route('/api/courts_by_facility/<facility_id>')
@require_role('owner')
def api_courts_by_facility(facility_id):
    owner_id = session.get('user_id')
    db = get_db()
    date = request.args.get('date')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    exclude_event_id = request.args.get('exclude_event_id')
    try:
        if date:
            from app.booking_utils import get_facility_court_timeline
            data = get_facility_court_timeline(
                db, facility_id, date, 
                start_time=start_time, 
                end_time=end_time, 
                exclude_event_id=exclude_event_id
            )
            return jsonify(data)
        else:
            resp = db.table('courts').select('id, name, type, hourly_rate').eq('facility_id', facility_id).eq('owner_id', owner_id).eq('status', 'active').execute()
            return jsonify(resp.data or [])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@owner_bp.route('/api/facility_month_availability')
@require_role('owner')
def api_facility_month_availability():
    facility_id = request.args.get('facility_id')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    exclude_event_id = request.args.get('exclude_event_id')
    if not facility_id or not year or not month:
        return jsonify({'error': 'Missing parameters'}), 400

    from app.booking_utils import get_facility_month_availability_data
    db = get_db()
    data = get_facility_month_availability_data(db, facility_id, year, month, exclude_event_id=exclude_event_id)
    return jsonify(data)


# ── Event Status Lifecycle ────────────────────────────────────────────────────
@owner_bp.route('/events/<event_id>/status', methods=['POST'])
@require_role('owner')
def change_event_status(event_id):
    owner_id = session.get('user_id')
    new_status = request.form.get('status', '').strip()
    allowed = ['upcoming', 'registration_open', 'full', 'in_progress', 'completed', 'cancelled']
    if new_status not in allowed:
        flash("Invalid status.", "error")
        return redirect(url_for('owner.events'))

    db = get_db()
    try:
        ev_resp = db.table('events').select('id, title, organizer_id').eq('id', event_id).single().execute()
        ev = ev_resp.data
        if not ev or ev['organizer_id'] != owner_id:
            flash("Access denied.", "error")
            return redirect(url_for('owner.events'))

        db.table('events').update({'status': new_status}).eq('id', event_id).execute()
        flash(f"Event status changed to '{new_status.replace('_', ' ').title()}'.", "success")

        # Optimized batch insert for cancellations
        if new_status == 'cancelled':
            reg_resp = db.table('event_registrations').select('player_id').eq('event_id', event_id).eq('status', 'registered').execute()
            notifs = [
                {
                    'user_id': reg['player_id'],
                    'title': f'Event Cancelled: {ev["title"]}',
                    'message': f'"{ev["title"]}" has been cancelled by the organizer.',
                    'type': 'warning'
                } for reg in (reg_resp.data or [])
            ]
            if notifs:
                db.table('notifications').insert(notifs).execute()
    except Exception as e:
        current_app.logger.error(f"Error changing status for event {event_id}: {e}")
        flash('An error occurred. Please try again.', 'error')

    return redirect(url_for('owner.events'))
