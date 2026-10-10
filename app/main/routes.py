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
    """Render the public landing page with courts, events, and tutorials."""
    courts = []
    events = []
    tutorials = []
    try:
        client = get_db()
        if client:
            # 1. Fetch active courts with facility info (limit to 3)
            courts_resp = client.table('courts').select(
                'id, name, type, hourly_rate, status, '
                'facility_id, facilities(id, name, location, image_url, description)'
            ).eq('status', 'active').limit(3).execute()
            if courts_resp.data:
                for c in courts_resp.data:
                    fac = c.get('facilities') or {}
                    courts.append({
                        'id': c['id'],
                        'name': c.get('name', 'Court'),
                        'type': c.get('type', 'indoor').capitalize(),
                        'hourly_rate': float(c.get('hourly_rate', 0)),
                        'facility_name': fac.get('name', 'Facility'),
                        'facility_location': fac.get('location', 'Laguna'),
                        'facility_image_url': fac.get('image_url') or '',
                        'facility_description': fac.get('description') or '',
                    })

            # 2. Fetch tournaments (limit to 3)
            events_resp = client.table('events').select(
                'id, title, type, format, prize_pool, image_url, event_date, entry_fee, description, '
                'facilities(name)'
            ).eq('type', 'tournament').order('event_date', desc=False).limit(3).execute()
            if events_resp.data:
                events = events_resp.data

            # 3. Fetch tutorials (limit to 3 public)
            try:
                t_resp = client.table('tutorials').select(
                    'id, title, description, youtube_url, video_url, video_type, thumbnail_url, level, visibility'
                ).limit(6).execute()
            except Exception:
                t_resp = client.table('tutorials').select(
                    'id, title, description, youtube_url, video_url, video_type, thumbnail_url, level'
                ).limit(6).execute()

            if t_resp.data:
                for t in t_resp.data:
                    if t.get('visibility') == 'club_members':
                        continue
                    if len(tutorials) >= 3:
                        break
                    url = t.get('youtube_url') or t.get('video_url') or ''
                    vid = _extract_yt_id(url)
                    is_upload = (t.get('video_type') == 'upload') or (not vid and bool(t.get('video_url')))
                    thumb = t.get('thumbnail_url') or (f'https://img.youtube.com/vi/{vid}/hqdefault.jpg' if vid else '/static/images/hero-action.png')
                    embed = (t.get('video_url') or url) if is_upload else (f'https://www.youtube.com/embed/{vid}?rel=0' if vid else '')
                    tutorials.append({
                        'title': t['title'],
                        'description': t.get('description') or '',
                        'level': t.get('level', 'Beginner'),
                        'youtube_url': url,
                        'video_url': t.get('video_url') or url,
                        'video_type': 'upload' if is_upload else 'youtube',
                        'embed_url': embed,
                        'thumb_url': thumb,
                    })
    except Exception as e:
        print(f'[landing index] DB error: {e}')

    return render_template(
        'landings/landing.html',
        featured_courts=courts,
        upcoming_tournaments=events,
        featured_tutorials=tutorials
    )

@main_bp.route('/clinics')
def clinics():
    """Render the public clinics and tutorials page with real DB tutorials."""
    tutorials = []
    try:
        client = get_db()
        if client:
            try:
                resp = client.table('tutorials').select(
                    'id, title, description, youtube_url, video_url, video_type, thumbnail_url, level, visibility'
                ).execute()
            except Exception:
                resp = client.table('tutorials').select(
                    'id, title, description, youtube_url, video_url, video_type, thumbnail_url, level'
                ).execute()

            if resp.data:
                pool = [t for t in resp.data if t.get('visibility') != 'club_members']
                sample = pool if len(pool) <= 2 else random.sample(pool, 2)

                for t in sample:
                    url = t.get('youtube_url') or t.get('video_url') or ''
                    vid = _extract_yt_id(url)
                    is_upload = (t.get('video_type') == 'upload') or (not vid and bool(t.get('video_url')))
                    thumb = t.get('thumbnail_url') or (f'https://img.youtube.com/vi/{vid}/hqdefault.jpg' if vid else '/static/images/hero-action.png')
                    embed = (t.get('video_url') or url) if is_upload else (f'https://www.youtube.com/embed/{vid}?autoplay=1&rel=0' if vid else '')
                    tutorials.append({
                        'title':       t['title'],
                        'description': t.get('description') or '',
                        'level':       t.get('level', 'Beginner'),
                        'youtube_url': url,
                        'video_url':   t.get('video_url') or url,
                        'video_type':  'upload' if is_upload else 'youtube',
                        'embed_url':   embed,
                        'thumb_url':   thumb,
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
    """Display facilities with grouped expandable courts for browsing and booking."""
    search_query = request.args.get('search', '')
    selected_facility = request.args.get('facility', '')
    facilities_dict = {}
    
    try:
        client = get_db()
        if client:
            # Fetch all active courts with facility info
            resp = client.table('courts').select(
                'id, name, type, hourly_rate, status, '
                'facility_id, facilities(id, name, location, latitude, longitude, kyc_status, image_url, description)'
            ).eq('status', 'active').execute()

            if resp.data:
                for court in resp.data:
                    facility = court.get('facilities') or {}
                    f_id = str(facility.get('id') or court.get('facility_id') or 'unknown')
                    fac_name = facility.get('name', 'Unknown Facility')
                    
                    if f_id not in facilities_dict:
                        facilities_dict[f_id] = {
                            'id': f_id,
                            'name': fac_name,
                            'location': facility.get('location', 'Laguna'),
                            'image_url': facility.get('image_url'),
                            'description': facility.get('description'),
                            'latitude': float(facility.get('latitude')) if facility.get('latitude') is not None else None,
                            'longitude': float(facility.get('longitude')) if facility.get('longitude') is not None else None,
                            'courts': []
                        }
                    
                    facilities_dict[f_id]['courts'].append({
                        'id': court['id'],
                        'name': court.get('name', 'Court'),
                        'type': court.get('type', 'indoor').capitalize(),
                        'hourly_rate': float(court.get('hourly_rate', 0)),
                        'facility_id': f_id,
                        'facility_name': fac_name,
                        'facility_location': facility.get('location', 'Laguna')
                    })
                    
        facilities = list(facilities_dict.values())
        facilities_list = sorted(list({f['name'] for f in facilities if f.get('name')}))

        # Filter by selected facility if provided
        if selected_facility.strip():
            facilities = [f for f in facilities if f['name'].lower() == selected_facility.lower()]

        # Filter by search query if provided
        if search_query.strip():
            search_lower = search_query.lower()
            filtered_facilities = []
            for fac in facilities:
                match_fac = (search_lower in fac['name'].lower() or search_lower in fac['location'].lower())
                matching_courts = [c for c in fac['courts'] if search_lower in c['name'].lower() or match_fac]
                if match_fac or matching_courts:
                    fac_copy = dict(fac)
                    if matching_courts:
                        fac_copy['courts'] = matching_courts
                    filtered_facilities.append(fac_copy)
            facilities = filtered_facilities

    except Exception as e:
        print(f'[courts_listing] DB error: {e}')
        facilities = []

    total_courts_count = sum(len(f['courts']) for f in facilities)

    # Flat list for Leaflet map compatibility
    flat_courts = []
    for f in facilities:
        for c in f['courts']:
            flat_courts.append({
                'id': c['id'],
                'name': c['name'],
                'type': c['type'],
                'hourly_rate': c['hourly_rate'],
                'facility_id': f['id'],
                'facility_name': f['name'],
                'facility_location': f['location'],
                'facility_latitude': f['latitude'],
                'facility_longitude': f['longitude'],
                'facility_image_url': f['image_url'],
                'facility_description': f['description']
            })

    return render_template(
        'landings/courts.html',
        facilities=facilities,
        courts=flat_courts,
        facilities_list=facilities_list,
        selected_facility=selected_facility,
        search_query=search_query,
        facilities_count=len(facilities),
        courts_count=total_courts_count
    )


@main_bp.route('/api/courts/search')
def api_courts_search():
    """API endpoint for court search suggestions (autocomplete)."""
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    suggestions = []
    try:
        client = get_db()
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


@main_bp.route('/article/<article_id>')
def view_article(article_id):
    """Render a full-width journalist article page with dynamic CMS content."""
    from app.landing_helper import get_article_by_id, get_articles_db
    
    article = get_article_by_id(article_id)
    if not article:
        return render_template('errors/404.html'), 404

    # Fetch recent featured bulletins / related stories
    all_articles = get_articles_db()
    related = [a for k, a in all_articles.items() if str(a.get('id')) != str(article.get('id'))][:4]

    return render_template('landings/article.html', article=article, related_articles=related)


@main_bp.route('/terms-of-service')
def terms_of_service():
    return render_template('landings/terms_of_service.html')


@main_bp.route('/privacy-policy')
def privacy_policy():
    return render_template('landings/privacy_policy.html')


@main_bp.route('/about-us')
def about_us():
    return render_template('landings/about_us.html')


# ════════════════════════════════════════════════════════════════════════════════
# TUTORIALS REST API (Cross-role video upload, listing, saving, and deletion)
# ════════════════════════════════════════════════════════════════════════════════

ALLOWED_TUTORIAL_ROLES = {'superadmin', 'adminstaff', 'clubadmin', 'owner', 'facilitystaff'}

ROLE_HIERARCHY = {
    'superadmin': 100,
    'adminstaff': 80,
    'owner': 60,
    'clubadmin': 40,
    'facilitystaff': 20,
    'player': 10,
}


@main_bp.route('/api/tutorials/list', methods=['GET'])
def api_tutorials_list():
    """Fetch all published tutorials with uploader profile details, filtered by visibility and club membership."""
    user_id = session.get('user_id')
    user_role = (session.get('role') or '').strip().lower()

    try:
        from app.db import get_admin_db
        db = get_admin_db()

        # Find club of user if clubadmin, plus any active club memberships
        user_club = None
        active_club_ids = set()

        if user_id:
            if user_role == 'clubadmin':
                try:
                    c_res = db.table('clubs').select('id, name').eq('admin_id', user_id).limit(1).execute()
                    if c_res.data:
                        user_club = c_res.data[0]
                        active_club_ids.add(user_club['id'])
                except Exception as ce:
                    current_app.logger.warning(f"[api_tutorials_list] Club lookup warning: {ce}")

            try:
                m_res = db.table('club_memberships').select('club_id').eq('player_id', user_id).eq('status', 'active').execute()
                for m in (m_res.data or []):
                    if m.get('club_id'):
                        active_club_ids.add(m['club_id'])
            except Exception as me:
                current_app.logger.warning(f"[api_tutorials_list] Memberships lookup warning: {me}")

        # Fetch tutorials with visibility, club_id and club details
        try:
            resp = db.table('tutorials').select(
                'id, title, description, youtube_url, video_url, video_type, thumbnail_url, duration, level, uploaded_by, created_at, '
                'visibility, club_id, '
                'clubs(id, name), '
                'profiles(first_name, last_name, role, avatar_url)'
            ).order('created_at', desc=True).execute()
            tutorials = resp.data or []
        except Exception as select_err:
            err_str = str(select_err).lower()
            if 'visibility' in err_str or 'club_id' in err_str or '42703' in err_str or 'pgrst204' in err_str or 'clubs' in err_str:
                resp = db.table('tutorials').select(
                    'id, title, description, youtube_url, video_url, video_type, thumbnail_url, duration, level, uploaded_by, created_at, '
                    'profiles(first_name, last_name, role, avatar_url)'
                ).order('created_at', desc=True).execute()
                tutorials = resp.data or []
            else:
                raise select_err

        is_elevated_role = user_role in ['superadmin', 'adminstaff', 'owner']
        filtered_tutorials = []

        for t in tutorials:
            vis = (t.get('visibility') or 'public').strip().lower()
            tut_club_id = t.get('club_id')
            uploader_id = t.get('uploaded_by')

            # Attach flattened club_name if present
            if t.get('clubs') and isinstance(t['clubs'], dict):
                t['club_name'] = t['clubs'].get('name')
            elif not t.get('club_name') and user_club and tut_club_id == user_club.get('id'):
                t['club_name'] = user_club.get('name')

            # Public tutorials visible to everyone
            if vis == 'public':
                filtered_tutorials.append(t)
                continue

            # Club-exclusive tutorials:
            # 1. Platform managers (superadmin, adminstaff, owner) can see all
            if is_elevated_role:
                filtered_tutorials.append(t)
                continue

            # 2. Author can see their own
            if user_id and uploader_id and uploader_id == user_id:
                filtered_tutorials.append(t)
                continue

            # 3. Active members of that club
            if tut_club_id and tut_club_id in active_club_ids:
                filtered_tutorials.append(t)
                continue

        return jsonify({
            'success': True,
            'tutorials': filtered_tutorials,
            'user_club': user_club
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/tutorials/sign-upload', methods=['POST'])
def api_tutorials_sign_upload():
    """
    Generate presigned upload URL for direct client-to-Supabase Storage upload.
    This completely bypasses Vercel's 4.5 MB request body limit and serverless timeouts.
    """
    user_id = session.get('user_id')
    user_role = (session.get('role') or '').strip().lower()

    if not user_id:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    if user_role not in ALLOWED_TUTORIAL_ROLES:
        return jsonify({'success': False, 'error': f'Role "{user_role}" is not authorized to upload tutorials.'}), 403

    data = request.get_json(silent=True) or {}
    filename = (data.get('filename') or '').strip()
    file_type = (data.get('content_type') or 'video/mp4').strip().lower()
    file_size = int(data.get('file_size') or 0)
    upload_kind = (data.get('upload_kind') or 'video').strip().lower()

    from app.upload_utils import (
        ALLOWED_VIDEO_EXTENSIONS,
        MAX_VIDEO_SIZE,
        ALLOWED_IMAGE_EXTENSIONS,
        MAX_IMAGE_SIZE,
        generate_safe_filename
    )
    from app.db import get_admin_db
    db = get_admin_db()

    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if upload_kind == 'thumbnail':
        bucket = 'community-images'
        prefix = 'tut_thumb'
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({'success': False, 'error': f'Invalid image format. Allowed: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}'}), 400
        if file_size > MAX_IMAGE_SIZE:
            return jsonify({'success': False, 'error': 'Image exceeds maximum 5MB size limit.'}), 400
    else:
        bucket = 'tutorial-videos'
        prefix = 'tut_vid'
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            return jsonify({'success': False, 'error': f'Invalid video format. Allowed: {", ".join(ALLOWED_VIDEO_EXTENSIONS)}'}), 400
        if file_size > MAX_VIDEO_SIZE:
            return jsonify({'success': False, 'error': 'Video exceeds maximum 50MB size limit.'}), 400

    safe_path = generate_safe_filename(prefix, user_id, ext)
    try:
        sign_res = db.storage.from_(bucket).create_signed_upload_url(safe_path)
        signed_url = sign_res.get('signed_url') or sign_res.get('signedUrl')
        token = sign_res.get('token')
        public_url = db.storage.from_(bucket).get_public_url(safe_path)

        return jsonify({
            'success': True,
            'signed_url': signed_url,
            'token': token,
            'public_url': public_url,
            'path': safe_path,
            'bucket': bucket,
            'content_type': file_type
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to generate direct upload URL: {e}'}), 500


@main_bp.route('/api/tutorials/upload', methods=['POST'])
def api_tutorials_upload():
    """
    Handle video and optional thumbnail uploads for tutorial creation.
    Accessible to authorized roles: superadmin, adminstaff, clubadmin, owner, facilitystaff.
    """
    user_id = session.get('user_id')
    user_role = (session.get('role') or '').strip().lower()

    if not user_id:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    if user_role not in ALLOWED_TUTORIAL_ROLES:
        return jsonify({'success': False, 'error': f'Role "{user_role}" is not authorized to upload tutorials.'}), 403

    video_file = request.files.get('video')
    if not video_file or not video_file.filename:
        return jsonify({'success': False, 'error': 'No video file provided.'}), 400

    from app.upload_utils import (
        validate_and_upload,
        ALLOWED_VIDEO_EXTENSIONS,
        MAX_VIDEO_SIZE,
        ALLOWED_IMAGE_EXTENSIONS,
        MAX_IMAGE_SIZE
    )
    from app.db import get_admin_db
    db = get_admin_db()

    video_url, video_err = validate_and_upload(
        db,
        video_file,
        bucket='tutorial-videos',
        prefix='tut_vid',
        owner_id=user_id,
        allowed_exts=ALLOWED_VIDEO_EXTENSIONS,
        max_size=MAX_VIDEO_SIZE
    )

    if video_err:
        return jsonify({'success': False, 'error': f'Video upload error: {video_err}'}), 400

    # Optional custom thumbnail image
    thumb_url = None
    thumb_file = request.files.get('thumbnail')
    if thumb_file and thumb_file.filename:
        t_url, t_err = validate_and_upload(
            db,
            thumb_file,
            bucket='community-images',
            prefix='tut_thumb',
            owner_id=user_id,
            allowed_exts=ALLOWED_IMAGE_EXTENSIONS,
            max_size=MAX_IMAGE_SIZE
        )
        if not t_err:
            thumb_url = t_url

    return jsonify({
        'success': True,
        'video_url': video_url,
        'thumbnail_url': thumb_url,
        'video_type': 'upload',
        'file_name': video_file.filename
    })


@main_bp.route('/api/tutorials/save', methods=['POST'])
def api_tutorials_save():
    """
    Create or update a tutorial record.
    Supports both YouTube URL and direct video file uploads.
    Includes debouncing against duplicate inserts and role hierarchy verification on edits.
    """
    user_id = session.get('user_id')
    user_role = (session.get('role') or '').strip().lower()

    if not user_id:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    if user_role not in ALLOWED_TUTORIAL_ROLES:
        return jsonify({'success': False, 'error': f'Role "{user_role}" is not authorized to publish tutorials.'}), 403

    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request body.'}), 400

    t_id = (data.get('id') or '').strip()
    title = (data.get('title') or '').strip()
    desc = (data.get('description') or '').strip()
    level = (data.get('level') or 'Beginner').strip()
    video_type = (data.get('video_type') or 'youtube').strip().lower()
    video_url = (data.get('video_url') or '').strip()
    youtube_url = (data.get('youtube_url') or '').strip()
    thumbnail_url = (data.get('thumbnail_url') or '').strip()
    duration = (data.get('duration') or '').strip()
    visibility = (data.get('visibility') or 'public').strip().lower()
    if visibility not in ['public', 'club_members']:
        visibility = 'public'

    if not title:
        return jsonify({'success': False, 'error': 'Tutorial title is required.'}), 400

    if video_type == 'upload':
        if not video_url:
            return jsonify({'success': False, 'error': 'Uploaded video URL is required.'}), 400
        # For backward compatibility with schemas where youtube_url is NOT NULL
        if not youtube_url:
            youtube_url = video_url
    else:
        video_type = 'youtube'
        if not youtube_url:
            return jsonify({'success': False, 'error': 'YouTube URL is required.'}), 400
        if not video_url:
            video_url = youtube_url

    from app.db import get_admin_db, log_audit_action
    db = get_admin_db()

    # Determine club_id and visibility permissions
    club_id = None
    if user_role == 'clubadmin':
        try:
            club_res = db.table('clubs').select('id, name').eq('admin_id', user_id).limit(1).execute()
            if club_res.data:
                club_id = club_res.data[0]['id']
        except Exception as ce:
            current_app.logger.warning(f"[api_tutorials_save] Club lookup warning: {ce}")

        if visibility == 'club_members' and not club_id:
            return jsonify({
                'success': False,
                'error': 'You must set up and activate your club before publishing club-exclusive tutorials.'
            }), 400
    else:
        # Non-clubadmins default to public
        visibility = 'public'

    payload = {
        'title': title,
        'description': desc,
        'level': level if level in ['Beginner', 'Intermediate', 'Advanced'] else 'Beginner',
        'video_type': video_type,
        'video_url': video_url,
        'youtube_url': youtube_url,
        'thumbnail_url': thumbnail_url or None,
        'duration': duration or None,
        'visibility': visibility,
        'club_id': club_id,
    }

    try:
        if t_id:
            # Editing an existing tutorial
            try:
                existing = db.table('tutorials').select('id, uploaded_by, title, club_id, visibility').eq('id', t_id).single().execute()
            except Exception:
                existing = db.table('tutorials').select('id, uploaded_by, title').eq('id', t_id).single().execute()
            if not existing.data:
                return jsonify({'success': False, 'error': 'Tutorial not found.'}), 404

            uploader_id = existing.data.get('uploaded_by')
            is_author = bool(uploader_id and uploader_id == user_id)
            user_rank = ROLE_HIERARCHY.get(user_role, 0)

            can_edit = False
            if user_role == 'superadmin':
                can_edit = True
            elif is_author:
                can_edit = True
            elif uploader_id:
                uploader_prof = db.table('profiles').select('role').eq('id', uploader_id).single().execute()
                uploader_role = ((uploader_prof.data or {}).get('role') or 'player').strip().lower()
                uploader_rank = ROLE_HIERARCHY.get(uploader_role, 0)
                if user_rank > uploader_rank:
                    can_edit = True
            elif user_role in ['superadmin', 'adminstaff']:
                can_edit = True

            if not can_edit:
                return jsonify({'success': False, 'error': 'You do not have permission to edit this tutorial.'}), 403

            # If editor is not a clubadmin, preserve existing club_id and visibility if not explicitly modified
            if user_role != 'clubadmin' and existing.data.get('club_id'):
                payload['club_id'] = existing.data.get('club_id')
                if existing.data.get('visibility'):
                    payload['visibility'] = existing.data.get('visibility')

            try:
                resp = db.table('tutorials').update(payload).eq('id', t_id).execute()
            except Exception as upd_err:
                err_str = str(upd_err).lower()
                if 'visibility' in err_str or 'club_id' in err_str or '42703' in err_str or 'pgrst204' in err_str:
                    fallback_payload = {k: v for k, v in payload.items() if k not in ('visibility', 'club_id')}
                    resp = db.table('tutorials').update(fallback_payload).eq('id', t_id).execute()
                else:
                    raise upd_err

            updated_item = resp.data[0] if resp.data else payload

            log_audit_action(
                action='UPDATE_TUTORIAL',
                target='tutorials',
                details={'id': t_id, 'title': title, 'level': level, 'video_type': video_type, 'visibility': visibility, 'club_id': club_id}
            )
            return jsonify({'success': True, 'message': 'Tutorial updated successfully.', 'tutorial': updated_item})
        else:
            # ── Creation Debouncing: prevent duplicate inserts within 15 seconds ──
            recent_dupes = db.table('tutorials').select('id, title, video_url, created_at').eq('uploaded_by', user_id).eq('title', title).order('created_at', desc=True).limit(1).execute()
            if recent_dupes.data:
                latest = recent_dupes.data[0]
                from datetime import datetime, timezone
                try:
                    created_str = latest.get('created_at') or ''
                    created_dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                    now_dt = datetime.now(timezone.utc)
                    if (now_dt - created_dt).total_seconds() < 15 and (latest.get('video_url') == video_url):
                        return jsonify({
                            'success': True,
                            'message': 'Tutorial published successfully.',
                            'tutorial': latest,
                            'duplicate_prevented': True
                        })
                except Exception:
                    pass

            # Creating a new tutorial
            payload['uploaded_by'] = user_id
            try:
                resp = db.table('tutorials').insert(payload).execute()
            except Exception as ins_err:
                err_str = str(ins_err).lower()
                if 'visibility' in err_str or 'club_id' in err_str or '42703' in err_str or 'pgrst204' in err_str:
                    fallback_payload = {k: v for k, v in payload.items() if k not in ('visibility', 'club_id')}
                    resp = db.table('tutorials').insert(fallback_payload).execute()
                else:
                    raise ins_err

            new_item = resp.data[0] if resp.data else payload

            log_audit_action(
                action='CREATE_TUTORIAL',
                target='tutorials',
                details={'id': new_item.get('id'), 'title': title, 'level': level, 'video_type': video_type, 'visibility': visibility, 'club_id': club_id}
            )
            return jsonify({'success': True, 'message': 'Tutorial created successfully.', 'tutorial': new_item})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Database operation failed: {e}'}), 500


@main_bp.route('/api/tutorials/delete/<id>', methods=['POST', 'DELETE'])
def api_tutorials_delete(id):
    """
    Delete a tutorial.
    Permitted for:
      - The tutorial uploader (regardless of rank)
      - Any user with a strictly higher role rank than the uploader (e.g. ClubAdmin > FacilityStaff, Owner > ClubAdmin)
      - Superadmin (global platform master)
      - Superadmin / AdminStaff for system starter tutorials (uploaded_by IS NULL)
    """
    user_id = session.get('user_id')
    user_role = (session.get('role') or '').strip().lower()

    if not user_id:
        return jsonify({'success': False, 'error': 'Authentication required.'}), 401

    if user_role not in ALLOWED_TUTORIAL_ROLES:
        return jsonify({'success': False, 'error': 'Unauthorized.'}), 403

    from app.db import get_admin_db, log_audit_action
    db = get_admin_db()

    try:
        existing = db.table('tutorials').select('id, uploaded_by, title, video_url, video_type').eq('id', id).single().execute()
        if not existing.data:
            return jsonify({'success': False, 'error': 'Tutorial not found.'}), 404

        uploader_id = existing.data.get('uploaded_by')
        is_author = bool(uploader_id and uploader_id == user_id)
        user_rank = ROLE_HIERARCHY.get(user_role, 0)

        can_delete = False
        if user_role == 'superadmin':
            can_delete = True
        elif is_author:
            can_delete = True
        elif uploader_id:
            uploader_prof = db.table('profiles').select('role').eq('id', uploader_id).single().execute()
            uploader_role = ((uploader_prof.data or {}).get('role') or 'player').strip().lower()
            uploader_rank = ROLE_HIERARCHY.get(uploader_role, 0)
            if user_rank > uploader_rank:
                can_delete = True
        elif user_role in ['superadmin', 'adminstaff']:
            can_delete = True

        if not can_delete:
            return jsonify({'success': False, 'error': 'You do not have permission to delete this tutorial.'}), 403

        # Clean up storage object if video was uploaded directly
        vid_url = existing.data.get('video_url') or ''
        vid_type = existing.data.get('video_type')
        if vid_type == 'upload' and 'tutorial-videos' in vid_url:
            try:
                file_name = vid_url.split('/tutorial-videos/')[-1].split('?')[0]
                if file_name:
                    db.storage.from_('tutorial-videos').remove([file_name])
            except Exception as stor_err:
                current_app.logger.warning(f"[api_tutorials_delete] Storage cleanup warning: {stor_err}")

        db.table('tutorials').delete().eq('id', id).execute()

        log_audit_action(
            action='DELETE_TUTORIAL',
            target='tutorials',
            details={'id': id, 'title': existing.data.get('title'), 'deleted_by_role': user_role}
        )
        return jsonify({'success': True, 'message': 'Tutorial deleted successfully.'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Deletion failed: {e}'}), 500

