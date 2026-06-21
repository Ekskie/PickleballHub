from flask import render_template, request, session, jsonify
from app.decorators import require_role
from app.db import get_db
from app.player import player_bp

@player_bp.route('/community')
@require_role('player')
def community():
    return render_template('player/community.html')


@player_bp.route('/messages')
@require_role('player')
def messages():
    return render_template('player/messages.html')


@player_bp.route('/notifications')
@require_role('player')
def notifications():
    player_id = session.get('user_id')
    db = get_db()
    notifs = []
    
    try:
        resp = db.table('notifications').select('*').eq('user_id', player_id).order('created_at', desc=True).execute()
        notifs = resp.data or []
    except Exception:
        pass
        
    return render_template('player/notifications.html', notifications=notifs)


@player_bp.route('/notifications/mark_read', methods=['POST'])
@require_role('player')
def mark_notifications_read():
    player_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').update({'is_read': True}).eq('user_id', player_id).eq('is_read', False).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@player_bp.route('/notifications/delete/<notif_id>', methods=['POST'])
@require_role('player')
def delete_notification(notif_id):
    player_id = session.get('user_id')
    db = get_db()
    try:
        db.table('notifications').delete().eq('id', notif_id).eq('user_id', player_id).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@player_bp.route('/tutorials')
@require_role('player')
def tutorials():
    return render_template('player/tutorials.html')
