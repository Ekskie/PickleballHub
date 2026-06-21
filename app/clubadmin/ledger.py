from flask import render_template, flash, g
from app.decorators import require_role
from app.db import get_db
from app.clubadmin import clubadmin_bp

@clubadmin_bp.route('/ledger')
@require_role('clubadmin')
def ledger():
    db = get_db()
    transactions = []
    
    if g.club:
        try:
            # Fetch all memberships for this club where gcash_ref is not null/empty
            resp = db.table('club_memberships').select(
                'id, status, joined_at, gcash_ref, receipt_url, expires_at, player_id, '
                'profiles!player_id(first_name, last_name, avatar_url, phone)'
            ).eq('club_id', g.club['id']).neq('gcash_ref', None).neq('gcash_ref', '').order('joined_at', desc=True).execute()
            
            transactions = resp.data or []
            
            # Post-process user initials
            for t in transactions:
                prof = t.get('profiles') or {}
                first = (prof.get('first_name') or ' ')[0]
                last = (prof.get('last_name') or ' ')[0]
                prof['initials'] = (first + last).upper().strip() or '?'
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error loading club ledger: {e}")
            flash('An error occurred. Please try again.', 'error')
            
    return render_template('clubadmin/ledger.html', transactions=transactions)
