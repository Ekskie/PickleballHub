from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app.decorators import require_role
from app.db import get_db

support_bp = Blueprint('support', __name__, url_prefix='/support')

@support_bp.route('/submit', methods=['POST'])
@require_role('player', 'owner', 'facilitystaff', 'clubadmin', 'adminstaff', 'superadmin')
def submit_ticket():
    user_id = session.get('user_id')
    if not user_id:
        flash("You must be logged in to submit a ticket.", "error")
        return redirect(request.referrer or url_for('main.index'))

    subject  = request.form.get('subject', '').strip()
    message  = request.form.get('message', '').strip()
    category = request.form.get('category', 'general').strip()

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

    db = get_db()
    try:
        db.table('tickets').insert({
            'user_id': user_id,
            'subject': full_subject,
            'message': message,
            'status': 'open',
        }).execute()
        flash("Your ticket has been submitted. Our support team will get back to you shortly.", "success")
    except Exception as e:
        flash('An error occurred. Please try again.', 'error')

    return redirect(request.referrer or url_for('main.index'))
