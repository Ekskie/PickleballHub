from flask import render_template, flash, g
from app.decorators import require_role
from app.db import get_db, get_admin_db
from app.clubadmin import clubadmin_bp

@clubadmin_bp.route('/ledger')
@require_role('clubadmin')
def ledger():
    db = get_admin_db() or get_db()
    transactions = []
    stats = {
        'total_collected': 0.0,
        'verified_count': 0,
        'pending_count': 0,
        'expired_count': 0,
        'fee': 0.0
    }
    
    if g.club:
        try:
            fee = float(g.club.get('membership_fee') or 0)
            stats['fee'] = fee
            
            # Fetch all memberships for this club where gcash_ref is not null/empty or status is active/pending
            resp = db.table('club_memberships').select(
                'id, status, joined_at, gcash_ref, receipt_url, expires_at, player_id, '
                'profiles!player_id(first_name, last_name, avatar_url, phone, email)'
            ).eq('club_id', g.club['id']).order('joined_at', desc=True).execute()
            
            all_memberships = resp.data or []
            # Filter to those with gcash_ref or active/pending payments
            transactions = [t for t in all_memberships if t.get('gcash_ref') or t.get('status') in ['active', 'pending']]
            
            # Post-process user initials
            for t in transactions:
                prof = t.get('profiles') or {}
                first = (prof.get('first_name') or ' ')[0]
                last = (prof.get('last_name') or ' ')[0]
                prof['initials'] = (first + last).upper().strip() or '?'

            stats['total_collected'] = sum(fee for t in transactions if t.get('status') == 'active')
            stats['verified_count'] = sum(1 for t in transactions if t.get('status') == 'active')
            stats['pending_count'] = sum(1 for t in transactions if t.get('status') == 'pending')
            stats['expired_count'] = sum(1 for t in transactions if t.get('status') == 'expired')

        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error loading club ledger: {e}")
            flash('An error occurred. Please try again.', 'error')
            
    return render_template('clubadmin/ledger.html', transactions=transactions, stats=stats)
