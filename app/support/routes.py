from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app import supabase_admin, supabase

from flask import g
import os
from supabase import create_client

_cached_db = None

def get_db():
    global _cached_db
    if _cached_db is None:
        import os
        import httpx
        from supabase import create_client, ClientOptions
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY')
        if url and key:
            http_client = httpx.Client(http2=False, limits=httpx.Limits(keepalive_expiry=10.0), timeout=30.0)
            options = ClientOptions(httpx_client=http_client)
            _cached_db = create_client(url, key, options=options)
    return _cached_db

support_bp = Blueprint('support', __name__, url_prefix='/support')

@support_bp.route('/submit', methods=['POST'])
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
        flash(f"Error submitting ticket: {e}", "error")

    return redirect(request.referrer or url_for('main.index'))

