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

            # 3. Fetch tutorials (limit to 3)
            t_resp = client.table('tutorials').select(
                'id, title, description, youtube_url, level'
            ).limit(3).execute()
            if t_resp.data:
                for t in t_resp.data:
                    url = t.get('youtube_url', '')
                    vid = _extract_yt_id(url)
                    tutorials.append({
                        'title': t['title'],
                        'description': t.get('description') or '',
                        'level': t.get('level', 'Beginner'),
                        'youtube_url': url,
                        'embed_url': f'https://www.youtube.com/embed/{vid}?rel=0' if vid else '',
                        'thumb_url': f'https://img.youtube.com/vi/{vid}/hqdefault.jpg' if vid else '',
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


@main_bp.route('/article/<int:article_id>')
def view_article(article_id):
    """Render a full-width journalist article page."""
    articles_db = {
        1: {
            "id": 1,
            "title": "Laguna Court Directory Reaches All-Time Booking Record",
            "category": "Reserve Court",
            "author": "Marcus Aurelius, Editor-in-Chief",
            "date": "Thursday, July 9, 2026",
            "read_time": "4 min read",
            "image_filename": "court-hero.jpg",
            "content": """
                <p class="lead-text">In a dramatic development for local recreational sports, the PickleballHub scheduling directory has reported an unprecedented booking spike across several municipalities in Laguna.</p>
                <p>According to peak-hour reservation logs, court rentals in Paete, Pakil, and Pangil have grown by over 120% quarter-over-quarter. Both indoor hall venues and scenic outdoor grounds are seeing heavy double-booking schedules, driving the need for automated slot reservations.</p>
                <h2>Local Hubs Report Surge in Registrations</h2>
                <p>Facility managers are noting that pickleball has rapidly transitioned from a niche sport into a central community hobby. "We are seeing entire families sign up for morning play, and competitive clubs renting court zones for evening league qualifiers," says Coach Arnold, a prominent player coordinator in Pakil.</p>
                <p>The centralized booking model has eliminated the friction of local scheduling. Instead of trading manual phone texts or facing calendar conflicts at arrival, players now browse open court availability in real-time, matching slots directly with their calendar availability.</p>
                <div class="article-pullquote">
                    <p>"Centralized digital booking has completely eliminated scheduling disputes, allowing our facilities to serve twice the volume of active court play."</p>
                </div>
                <h2>GCash Simplifies Transaction Speed</h2>
                <p>A major contributor to the reservation volume is the native checkout option. By integrating direct GCash mobile wallet checkouts, reservation confirmations are cleared within 30 seconds. This has allowed municipal courts to run completely self-sufficient gates, freeing up facility staff from manual collections and verifying entries instantly via mobile notifications.</p>
                <p>As the network expands, more towns in Laguna are preparing to list their facilities, promising a unified digital playing corridor for court players regionwide.</p>
            """
        },
        2: {
            "id": 2,
            "title": "Unified Tournament Engine Introduces Automated Match Brackets",
            "category": "Tournament Cup",
            "author": "Sandra Park, Tournament Director",
            "date": "Wednesday, July 8, 2026",
            "read_time": "5 min read",
            "image_filename": "background.jpg",
            "content": """
                <p class="lead-text">Coordinating bracket tournaments across districts has historically been a scheduling nightmare. Today, PickleballHub launched its unified Tournament Engine, automating tournament brackets and player queues.</p>
                <p>The new software module enables club administrators to build custom tournaments (Singles, Doubles, or Mixed brackets) with automated seeding, DUPR rating checks, and dynamic match queues. Organizer dashboards now construct single-elimination or round-robin brackets instantly, removing manual spreadsheet work.</p>
                <h2>Automating Local Brackets &amp; Seeding</h2>
                <p>Seeding matchups has always been a point of contention among local leagues. To solve this, the engine imports a player's official matchmaking ELO score to rank seeds. By grouping players into balanced skill flights (Beginner, Intermediate, Advanced, and Pro), tournaments guarantee competitive match play while preventing unranked mismatches.</p>
                <p>"The bracket software saved us six hours of manual alignment during the Paete District Open last weekend," notes Sandra Park, Tournament Director. "As matches conclude, players input scores directly on their dashboard, which instantly updates the bracket and moves the next seed into the active queue."</p>
                <div class="article-pullquote">
                    <p>"By using live ELO points for brackets, every match is balanced, leading to closer games and higher tournament entries."</p>
                </div>
                <h2>Live Queue Standings on Mobile</h2>
                <p>Spectators and players can track bracket advancement directly on their mobile devices. The live queue keeps waiting players notified when a court becomes open and automatically assigns next-up matches. This real-time visibility prevents players from missing call times and speeds up tournament execution by over 30%.</p>
                <p>Local sports associations in Laguna are already registering upcoming events on the platform, establishing a shared league schedule that connects players across municipal boundaries.</p>
            """
        },
        3: {
            "id": 3,
            "title": "Expert Academy Insights: How Spin &amp; Position Controls the Court",
            "category": "Academy Training",
            "author": "Coach Arnold, Head Instructor",
            "date": "Tuesday, July 7, 2026",
            "read_time": "3 min read",
            "image_filename": "bg.png",
            "content": """
                <p class="lead-text">Pickleball is often described as a chess match played at high speed. While power serves look impressive, players who master spin and kitchen line positioning consistently control the court.</p>
                <p>In our latest Academy installment, Coach Arnold breaks down the mechanics of the soft game, highlighting why the dink shot remains the most lethal weapon in competitive play. Players who learn to neutralize power drives by dropshotting into the kitchen can force opponents into high-risk errors.</p>
                <h2>The Art of the Kitchen Dink</h2>
                <p>The kitchen (non-volley zone) is the most critical area on the court. Winning rallies requires getting to the kitchen line as quickly as possible. Once there, the objective shifts from striking power drives to placing low, spinning dinks that force the opponent to strike the ball upward.</p>
                <p>"Newer players make the mistake of attempting power drives from the baseline," Coach Arnold explains. "Advanced play is about patience. You dink softly until your opponent leaves a ball high enough for a smash."</p>
                <div class="article-pullquote">
                    <p>"Patience beats power in the kitchen. The player who dinks with better spin and lower clearance will force the error."</p>
                </div>
                <h2>Paddle Angle and Spin Mechanics</h2>
                <p>Controlling spin requires subtle adjustments to the paddle face. For under-spin (slice), open the paddle face and brush under the ball. For top-spin, close the face slightly and swing low-to-high. Practicing these drills turns defensive drop shots into offensive dinks that slide away from opponents upon landing.</p>
                <p>The PickleballHub Academy is now accepting video uploads from registered players. Basic members can post gameplay clips to the community feed, allowing certified coaches to provide personalized technique critiques and ELO boost tips.</p>
            """
        },
        4: {
            "id": 4,
            "title": "Network Database Registers Over 500 Active Players in Laguna",
            "category": "Just In",
            "author": "Dev Team Bulletin",
            "date": "Thursday, July 9, 2026",
            "read_time": "3 min read",
            "image_filename": "logo.png",
            "content": """
                <p class="lead-text">PickleballHub is thrilled to announce that our active player directory has crossed the 500-member milestone. This represents a massive sports community expanding across Laguna's municipalities.</p>
                <p>Our centralized database connects players of all skill backgrounds, matching singles and doubles games through rating ELO metrics. The growth demonstrates the strong demand for a unified sports scheduler and social networking tool in local towns.</p>
                <h2>Connecting Local Athletes</h2>
                <p>Our matchmaking engine allows players to create open match lobbies. When a player books a court, they can designate it as a "Public Match" and set a skill bracket (e.g. 3.0 to 4.0 ELO). Other players matching this rating receive automated notifications and can join the slot, splitting court rental fees via GCash.</p>
                <p>This social matching prevents players from showing up alone and helps newcomers integrate into local groups seamlessly. As registrations continue to climb, we are preparing to roll out player forums, group chats, and town leaderboards.</p>
            """
        },
        5: {
            "id": 5,
            "title": "GCash Integration Speeds Checkouts Under 30 Seconds",
            "category": "Booking Alert",
            "author": "Billing Operations Team",
            "date": "Thursday, July 9, 2026",
            "read_time": "2 min read",
            "image_filename": "gcash_qr.png",
            "content": """
                <p class="lead-text">Say goodbye to manual bank transfers and verification wait times. PickleballHub's GCash mobile wallet checkout integration is now fully live, letting players secure court slots in under 30 seconds.</p>
                <p>By automating transaction clearing, the reservation system issues booking receipts instantly, verifying court slot availability in real-time. This eliminates double-bookings and provides court operators with transparent ledger bookkeeping.</p>
                <h2>Automating Transaction Ledgers</h2>
                <p>Previously, facility staff had to reconcile cash boxes and manual GCash screenshot uploads, leading to booking errors and delayed confirmations. With direct API integration, the system handles booking checks automatically. If a payment completes, the court scheduler locks the hour and notifies both player and facility staff instantly.</p>
                <p>This automated flow keeps schedules clear and ensures that booking cancellation refunds are credited back to player accounts without manual administrative overhead.</p>
            """
        },
        6: {
            "id": 6,
            "title": "District Brackets Report 40% Growth in Participant Entries",
            "category": "Tournament Bulletin",
            "author": "League Organizer Team",
            "date": "Wednesday, July 8, 2026",
            "read_time": "3 min read",
            "image_filename": "court-hero.jpg",
            "content": """
                <p class="lead-text">Competitive interest is hitting record heights. League organizers report a 40% increase in tournament signups for our upcoming district championships.</p>
                <p>Both Singles and Doubles divisions are seeing rapid registration fill-up times. Players are rushing to secure slots and claim a share of the community-sponsored prize pools, promising highly competitive games.</p>
                <h2>Increasing Competitive Interest</h2>
                <p>Organizers attribute the signup surge to the platform's transparent division brackets. By letting players preview registered rosters and matching ELO scores, competitors feel confident entering fair brackets.</p>
                <p>Automated match reminders and digitized scoring ensure tournaments run smoothly without delays, setting a new benchmark for competitive amateur sports events in the region.</p>
            """
        }
    }

    article = articles_db.get(article_id)
    if not article:
        return render_template('errors/404.html'), 404

    return render_template('landings/article.html', article=article)


@main_bp.route('/terms-of-service')
def terms_of_service():
    return render_template('landings/terms_of_service.html')


@main_bp.route('/privacy-policy')
def privacy_policy():
    return render_template('landings/privacy_policy.html')


@main_bp.route('/about-us')
def about_us():
    return render_template('landings/about_us.html')
