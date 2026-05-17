from flask import Blueprint, render_template, request, jsonify, session, g
import os
from supabase import create_client
import random

# Create a new blueprint for public-facing pages
main_bp = Blueprint('main', __name__)

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

@main_bp.route('/')
def index():
    """Render the public landing page."""
    return render_template('landings/landing.html')

@main_bp.route('/clinics')
def clinics():
    """Render the public clinics and tutorials page with real DB tutorials."""
    tutorials = []
    try:
        client = get_db()
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
        client = get_db()
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
    clubs = []
    try:
        client = get_db()
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

            # Fetch 3 active clubs
            club_resp = client.table('clubs').select('id, name, description, logo_url, created_at').eq('status', 'active').limit(10).execute()
            if club_resp.data:
                clubs_pool = club_resp.data
                clubs = clubs_pool if len(clubs_pool) <= 3 else random.sample(clubs_pool, 3)

    except Exception as e:
        print(f'[community landing] DB error: {e}')

    return render_template('landings/community.html', posts=posts, clubs=clubs)


@main_bp.route('/courts')
def courts_listing():
    """Display available courts for browsing and booking."""
    search_query = request.args.get('search', '')
    courts = []
    try:
        client = supabase_admin or supabase
        if client:
            # Fetch all active courts with facility info
            resp = client.table('courts').select(
                'id, name, type, hourly_rate, status, '
                'facility_id, facilities(id, name, location)'
            ).eq('status', 'active').execute()

            if resp.data:
                courts_data = resp.data
                
                # Filter by search query if provided
                if search_query.strip():
                    search_lower = search_query.lower()
                    courts_data = [
                        c for c in courts_data
                        if (search_lower in c.get('name', '').lower() or 
                            search_lower in c.get('facilities', {}).get('name', '').lower() or
                            search_lower in c.get('facilities', {}).get('location', '').lower())
                    ]
                
                # Format courts for display
                for court in courts_data:
                    facility = court.get('facilities') or {}
                    courts.append({
                        'id': court['id'],
                        'name': court.get('name', 'Unknown Court'),
                        'type': court.get('type', 'indoor').capitalize(),
                        'hourly_rate': float(court.get('hourly_rate', 0)),
                        'facility_name': facility.get('name', 'Unknown Facility'),
                        'facility_location': facility.get('location', 'Laguna'),
                        'facility_id': facility.get('id'),
                    })
    except Exception as e:
        print(f'[courts_listing] DB error: {e}')

    return render_template(
        'landings/courts.html',
        courts=courts,
        search_query=search_query,
        courts_count=len(courts)
    )


@main_bp.route('/api/courts/search')
def api_courts_search():
    """API endpoint for court search suggestions (autocomplete)."""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    suggestions = []
    try:
        client = supabase_admin or supabase
        if client:
            query_lower = query.lower()
            
            # Fetch active courts with facility info
            resp = client.table('courts').select(
                'id, name, type, hourly_rate, '
                'facility_id, facilities(id, name, location)'
            ).eq('status', 'active').limit(10).execute()

            if resp.data:
                for court in resp.data:
                    facility = court.get('facilities') or {}
                    court_name = court.get('name', '')
                    facility_name = facility.get('name', '')
                    location = facility.get('location', '')
                    
                    # Check if query matches court name, facility name, or location
                    if (query_lower in court_name.lower() or
                        query_lower in facility_name.lower() or
                        query_lower in location.lower()):
                        
                        suggestions.append({
                            'id': court['id'],
                            'label': f"{court_name} at {facility_name}",
                            'full_name': f"{court_name} ({facility_name}, {location})"
                        })
    except Exception as e:
        print(f'[api_courts_search] DB error: {e}')
    
    return jsonify(suggestions[:5])  # Limit to 5 suggestions
