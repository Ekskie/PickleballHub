from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app.db import get_db, get_admin_db

support_bp = Blueprint('support', __name__, url_prefix='/support')


def _get_support_db():
    """Return admin Supabase client when available, falling back to request-scoped client."""
    try:
        return get_admin_db() or get_db()
    except Exception:
        return get_db()


def get_user_tickets(user_id):
    """Fetch support tickets submitted by the given user, newest first."""
    if not user_id:
        return []
    try:
        db = _get_support_db()
        resp = (
            db.table('tickets')
            .select('*')
            .eq('user_id', user_id)
            .order('created_at', desc=True)
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


@support_bp.route('/submit', methods=['POST'])
@require_role('player', 'owner', 'facilitystaff', 'clubadmin', 'adminstaff', 'superadmin')
def submit_ticket():
    user_id = session.get('user_id')
    if not user_id:
        flash("You must be logged in to submit a ticket.", "error")
        return redirect(request.referrer or url_for('main.index'))

    subject  = request.form.get('subject', '').strip()
    message  = request.form.get('message', '').strip()
    category = (request.form.get('category') or 'general').strip() or 'general'

    if not subject or not message:
        flash("Subject and Message are required.", "error")
        return redirect(request.referrer or url_for('main.index'))

    if len(subject) > 200:
        flash("Subject cannot exceed 200 characters.", "error")
        return redirect(request.referrer or url_for('main.index'))

    if len(message) > 5000:
        flash("Message cannot exceed 5000 characters.", "error")
        return redirect(request.referrer or url_for('main.index'))

    # Prepend category to subject for easy identification in admin view
    full_subject = f"[{category.replace('_', ' ').title()}] {subject}"

    db = _get_support_db()
    try:
        db.table('tickets').insert({
            'user_id': user_id,
            'subject': full_subject,
            'message': message,
            'status': 'open',
        }).execute()

        # Notify adminstaff and superadmin members without failing ticket creation
        try:
            staff_resp = (
                db.table('profiles')
                .select('id')
                .in_('role', ['adminstaff', 'superadmin'])
                .execute()
            )
            staff_rows = staff_resp.data or []
            if staff_rows:
                notifs = [
                    {
                        'user_id': row['id'],
                        'title': f"New Support Ticket: {full_subject[:60]}",
                        'message': message[:160],
                        'type': 'info',
                        'link': '/adminstaff/support',
                    }
                    for row in staff_rows
                    if row.get('id')
                ]
                if notifs:
                    db.table('notifications').insert(notifs).execute()
        except Exception:
            pass

        flash("Your ticket has been submitted. Our support team will get back to you shortly.", "success")
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')

    return redirect(request.referrer or url_for('main.index'))
