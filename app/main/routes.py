from flask import Blueprint, render_template
from app import supabase_admin, supabase
import random

# Create a new blueprint for public-facing pages
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Render the public landing page."""
    return render_template('landings/landing.html')

@main_bp.route('/clinics')
def clinics():
    """Render the public clinics and tutorials page with real DB tutorials."""
    tutorials = []
    try:
        client = supabase_admin or supabase
        if client:
            resp = client.table('tutorials').select(
                'id, title, description, youtube_url, level'
            ).execute()

            if resp.data:
                pool   = resp.data
                sample = pool if len(pool) <= 2 else random.sample(pool, 2)

                for t in sample:
                    url  = t.get('youtube_url', '')
                    vid  = _extract_yt_id(url)
                    tutorials.append({
                        'title':       t['title'],
                        'description': t.get('description') or '',
                        'level':       t.get('level', 'Beginner'),
                        'youtube_url': url,
                        'embed_url':   f'https://www.youtube.com/embed/{vid}?autoplay=1&rel=0' if vid else '',
                        'thumb_url':   f'https://img.youtube.com/vi/{vid}/hqdefault.jpg' if vid else '',
                    })
    except Exception as e:
        print(f'[clinics landing] DB error: {e}')

    return render_template('landings/clinics.html', tutorials=tutorials)


def _extract_yt_id(url):
    """Extract a YouTube video ID from a full or short URL."""
    try:
        from urllib.parse import urlparse, parse_qs
        u = urlparse(url)
        if u.hostname in ('youtu.be',):
            return u.path.lstrip('/')
        qs = parse_qs(u.query)
        return qs.get('v', [None])[0]
    except Exception:
        return None



@main_bp.route('/tournaments')
def tournaments():
    """Render the public tournaments page with real DB tournaments."""
    events = []
    try:
        client = supabase_admin or supabase
        if client:
            resp = client.table('events').select(
                'id, title, type, format, prize_pool, image_url, event_date, start_time, end_time, location_label, entry_fee, status, max_players, description, '
                'facilities(name), profiles!organizer_id(first_name, last_name)'
            ).eq('type', 'tournament').order('event_date', desc=False).execute()

            if resp.data:
                events = resp.data
    except Exception as e:
        print(f'[tournaments landing] DB error: {e}')

    return render_template('landings/tournaments.html', events=events)

@main_bp.route('/community')
def community():
    """Render the public community page with real posts from the DB."""
    posts = []
    try:
        client = supabase_admin or supabase
        if client:
            # Fetch recent posts with author profile info
            resp = client.table('community_posts').select(
                'id, content, created_at, image_url, '
                'author:profiles!community_posts_author_id_fkey(first_name, last_name, role)'
            ).order('created_at', desc=True).limit(50).execute()

            if resp.data:
                # Pick up to 5 random posts for variety
                sample = resp.data if len(resp.data) <= 5 else random.sample(resp.data, 5)

                # Get like counts for sampled posts
                post_ids = [p['id'] for p in sample]
                likes_resp = client.table('post_likes').select(
                    'post_id'
                ).in_('post_id', post_ids).execute()

                like_map = {}
                for like in (likes_resp.data or []):
                    like_map[like['post_id']] = like_map.get(like['post_id'], 0) + 1

                # Get comment counts
                comments_resp = client.table('community_comments').select(
                    'post_id'
                ).in_('post_id', post_ids).execute()

                comment_map = {}
                for c in (comments_resp.data or []):
                    comment_map[c['post_id']] = comment_map.get(c['post_id'], 0) + 1

                for post in sample:
                    author = post.get('author') or {}
                    first  = (author.get('first_name') or '').strip()
                    last   = (author.get('last_name')  or '').strip()
                    role   = (author.get('role') or 'player').capitalize()
                    posts.append({
                        'id':          post['id'],
                        'content':     post['content'],
                        'created_at':  post['created_at'],
                        'image_url':   post.get('image_url') or '',
                        'author_name': f"{first} {last}".strip() or 'Community Member',
                        'author_init': ((first[:1] + last[:1]).upper()) or 'CM',
                        'author_role': role,
                        'likes':       like_map.get(post['id'], 0),
                        'comments':    comment_map.get(post['id'], 0),
                    })
    except Exception as e:
        print(f'[community landing] DB error: {e}')

    return render_template('landings/community.html', posts=posts)