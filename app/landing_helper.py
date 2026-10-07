import json
import os
import sys
import time
from app.settings_helper import get_db_client

_cached_landing = None
_landing_cache_time = 0.0
LANDING_CACHE_TTL = 30.0  # 30 seconds cache

DEFAULT_HERO_SLIDES = [
    {
        "id": 1,
        "title": "PLAY. CONNECT. GROW.",
        "subtitle": "Your hub for pickleball in Laguna.",
        "image_url": "/static/images/pickleball-slider-1.png",
        "alt": "Play. Connect. Grow."
    },
    {
        "id": 2,
        "title": "RESERVE YOUR COURT.",
        "subtitle": "Instant bookings with local GCash checkout.",
        "image_url": "/static/images/Agarao.jfif",
        "alt": "Reserve Court"
    },
    {
        "id": 3,
        "title": "JOIN THE LEAGUE.",
        "subtitle": "Compete in premier tournaments across Laguna.",
        "image_url": "/static/images/court-topdown.png",
        "alt": "Join Tournament"
    }
]

DEFAULT_LEAD_STORIES = [
    {
        "id": 1,
        "category": "Reserve Court",
        "title": "Laguna Court Directory Reaches All-Time Booking Record",
        "description": "The definitive platform for Laguna pickleball. Whether you're a player looking for a match, a club managing brackets, or an owner listing courts—secure your spot instantly with local GCash checkout.",
        "link": "/courts",
        "link_text": "Book a Court",
        "image_url": "/static/images/court-hero.jpg"
    },
    {
        "id": 2,
        "category": "Tournament Cup",
        "title": "Unified Tournament Engine Introduces Automated Match Brackets",
        "description": "Club organizers can now launch tournaments seamlessly. Features automated bracket construction for Singles or Doubles matchups with live queue standings.",
        "link": "/tournaments",
        "link_text": "Find Tournaments",
        "image_url": "/static/images/background.jpg"
    },
    {
        "id": 3,
        "category": "Tutorial",
        "title": "Expert Academy Insights: How Spin & Position Controls the Court",
        "description": "Top DUPR-certified coaches upload training courses. Study court navigation, check local clinic events, or upload gameplay footage to get professional player feedback.",
        "link": "/clinics",
        "link_text": "View Clinics",
        "image_url": "/static/images/bg.png"
    }
]

DEFAULT_BULLETINS = [
    {
        "id": 1,
        "time": "Just In",
        "title": "Network Database registers over 500 active players in Laguna",
        "description": "Community matchmaking matches players of identical skill scores automatically.",
        "link": "/article/4"
    },
    {
        "id": 2,
        "time": "Booking Alert",
        "title": "GCash Integration speeds checkouts under 30 seconds",
        "description": "Eliminating cash delays. Verified facilities enforce instant schedules.",
        "link": "/article/5"
    },
    {
        "id": 3,
        "time": "Tournament",
        "title": "District brackets report 40% growth in participant entries",
        "description": "Singles and Doubles brackets are filling up across local towns.",
        "link": "/article/6"
    }
]

DEFAULT_TESTIMONIALS = [
    {
        "id": 1,
        "rating": 5,
        "quote": "Booking a court in Paete used to take 5 text messages. Now I just make a reservation here and pay via GCash in under 30 seconds.",
        "author": "Mark T.",
        "role": "Player (3.5 DUPR Rating)"
    },
    {
        "id": 2,
        "rating": 5,
        "quote": "We've seen a 40% increase in court utilization since listing our Pakil facility on PickleballHub. The real-time booking has completely eliminated schedule conflicts.",
        "author": "Coach Arnold",
        "role": "Pakil Arena Owner"
    }
]

DEFAULT_FAQS = [
    {
        "id": 1,
        "question": "How do I make a reservation on PickleballHub?",
        "answer": "Simply scroll up to search for courts or click \"Find Courts\" in the menu. Browse the available times, select your slot, and secure it with integrated GCash payments."
    },
    {
        "id": 2,
        "question": "How does player matchmaking work?",
        "answer": "When you sign up, you specify your experience level. You can search the community feed for matches or create public court bookings that other players of similar ratings can join."
    },
    {
        "id": 3,
        "question": "What is the weather refund policy?",
        "answer": "If you make a reservation at an outdoor court and it rains, you can request a booking cancellation. Our system automatically processes refunds or credits to your account."
    }
]

DEFAULT_STATS = [
    {"num": "500+", "label": "Active Players"},
    {"num": "12", "label": "Connected Towns"},
    {"num": "10k+", "label": "Matches Played"},
    {"num": "100%", "label": "Automated Booking"}
]

DEFAULT_ARTICLES = {
    1: {
        "id": 1,
        "title": "Laguna Court Directory Reaches All-Time Booking Record",
        "category": "Reserve Court",
        "author": "Marcus Aurelius, Editor-in-Chief",
        "date": "Thursday, July 9, 2026",
        "read_time": "4 min read",
        "image_filename": "court-hero.jpg",
        "image_url": "/static/images/court-hero.jpg",
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
        "image_url": "/static/images/background.jpg",
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
        "image_url": "/static/images/bg.png",
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
        "image_url": "/static/images/logo.png",
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
        "image_url": "/static/images/gcash_qr.png",
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
        "image_url": "/static/images/court-hero.jpg",
        "content": """
            <p class="lead-text">Competitive interest is hitting record heights. League organizers report a 40% increase in tournament signups for our upcoming district championships.</p>
            <p>Both Singles and Doubles divisions are seeing rapid registration fill-up times. Players are rushing to secure slots and claim a share of the community-sponsored prize pools, promising highly competitive games.</p>
            <h2>Increasing Competitive Interest</h2>
            <p>Organizers attribute the signup surge to the platform's transparent division brackets. By letting players preview registered rosters and matching ELO scores, competitors feel confident entering fair brackets.</p>
            <p>Automated match reminders and digitized scoring ensure tournaments run smoothly without delays, setting a new benchmark for competitive amateur sports events in the region.</p>
        """
    }
}


def clear_landing_cache():
    global _cached_landing, _landing_cache_time
    _cached_landing = None
    _landing_cache_time = 0.0


def get_landing_content(force_refresh=False):
    """
    Returns complete landing page configuration with DB overrides.
    Cached for 30s for zero DB overhead on high-traffic landing visits.
    """
    global _cached_landing, _landing_cache_time
    now = time.time()
    if force_refresh or _cached_landing is None or (now - _landing_cache_time) > LANDING_CACHE_TTL:
        content = {
            # Masthead
            "masthead_location": "LAGUNA, PHILIPPINES",
            
            # Hero slideshow (top header)
            "hero_slides": [dict(s) for s in DEFAULT_HERO_SLIDES],
            
            # Lead stories carousel (main body section)
            "lead_stories": [dict(s) for s in DEFAULT_LEAD_STORIES],
            
            # Sidebar bulletins
            "bulletins": [dict(b) for b in DEFAULT_BULLETINS],
            
            # Value proposition banner
            "value_prop_kicker": "Join Laguna's Fastest-Growing Pickleball Community",
            "value_prop_headline": "The definitive platform for Laguna pickleball.",
            "value_prop_text": "Whether you're a player looking for a match, a club managing brackets, or an owner listing courts—secure your spot instantly with local GCash checkout.",
            "value_prop_cta_text": "Sign Up for Free",
            "value_prop_cta_link": "/auth/signup",
            
            # Section A, B, C headings
            "section_a_divider_1": "Section A",
            "section_a_divider_2": "Court Reports",
            "section_a_divider_3": "Metro Laguna Edition",
            "section_a_title": "Verified Facilities Available",
            "section_a_subtitle": "Read detailed facility reviews and schedule your next match reservation instantly.",
            
            "section_b_divider_1": "Section B",
            "section_b_divider_2": "Tournament Bulletins",
            "section_b_divider_3": "Local Competitions",
            "section_b_title": "Laguna League Tournaments",
            "section_b_subtitle": "Track upcoming events, register brackets, and compete for prize pools.",
            
            "section_c_divider_1": "Section C",
            "section_c_divider_2": "Tutorials",
            "section_c_divider_3": "Training & Clinics",
            "section_c_title": "Clinics & Tutorials",
            "section_c_subtitle": "Enhance your game with custom tutorial articles and embedded instructional videos.",
            
            # Testimonials (Section E)
            "section_e_divider_1": "Section E",
            "section_e_divider_2": "Reader Testimonials",
            "section_e_divider_3": "Platform Feedback",
            "testimonials": [dict(t) for t in DEFAULT_TESTIMONIALS],
            
            # FAQs (Section F)
            "section_f_divider_1": "Section F",
            "section_f_divider_2": "Frequently Asked Questions",
            "section_f_divider_3": "Reader Help Desk",
            "faqs": [dict(f) for f in DEFAULT_FAQS],
            
            # Stats & conversion footer
            "stats": [dict(st) for st in DEFAULT_STATS],
            "footer_cta_kicker": "Special Correspondent · Open Invitation",
            "footer_cta_headline": "Ready to take the court?",
            "footer_cta_text": "Join 500+ players across 12 towns in Laguna today. Book courts, enter tournaments, and track your DUPR rating—all in one platform.",
            "footer_cta_btn_text": "Sign Up for Free",
            "footer_cta_btn_link": "/auth/signup",
        }

        db = get_db_client()
        if db:
            try:
                resp = db.table('platform_settings').select('*').like('key', 'landing_%').execute()
                for row in (resp.data or []):
                    k = row.get('key', '')
                    v = row.get('value', '')
                    
                    # Strip 'landing_' prefix
                    setting_name = k[len('landing_'):]
                    
                    if setting_name in ['hero_slides', 'lead_stories', 'bulletins', 'testimonials', 'faqs', 'stats']:
                        try:
                            parsed = json.loads(v)
                            if isinstance(parsed, list):
                                content[setting_name] = parsed
                        except Exception as pe:
                            print(f"[landing_helper] JSON parse error for {k}: {pe}", file=sys.stderr)
                    elif setting_name in content:
                        content[setting_name] = v
            except Exception as e:
                print(f"[landing_helper] DB read error: {e}", file=sys.stderr)

        _cached_landing = content
        _landing_cache_time = now

    return _cached_landing


def get_articles_db(force_refresh=False):
    """
    Returns full dictionary of articles with DB updates/creations merged.
    """
    articles = {k: dict(v) for k, v in DEFAULT_ARTICLES.items()}
    db = get_db_client()
    if db:
        try:
            resp = db.table('platform_settings').select('*').eq('key', 'landing_articles_data').execute()
            if resp.data and len(resp.data) > 0:
                raw_json = resp.data[0].get('value')
                if raw_json:
                    saved_dict = json.loads(raw_json)
                    for k, v in saved_dict.items():
                        try:
                            int_k = int(k)
                            v['id'] = int_k
                            articles[int_k] = v
                        except Exception:
                            articles[k] = v
        except Exception as e:
            print(f"[landing_helper] Error loading articles from DB: {e}", file=sys.stderr)
    return articles


def get_article_by_id(article_id):
    """
    Fetch a single article by ID.
    """
    articles = get_articles_db()
    try:
        int_id = int(article_id)
        if int_id in articles:
            return articles[int_id]
    except (ValueError, TypeError):
        pass
    
    for k, art in articles.items():
        if str(art.get('id')) == str(article_id):
            return art
    return None


def save_landing_setting(key, value):
    """
    Save a specific landing setting into platform_settings table.
    """
    db = get_db_client()
    if not db:
        raise RuntimeError("Database client not available")
    
    if not key.startswith('landing_'):
        key = f"landing_{key}"
    
    str_val = json.dumps(value) if isinstance(value, (list, dict)) else str(value)
    db.table('platform_settings').upsert({
        'key': key,
        'value': str_val
    }, on_conflict='key').execute()
    clear_landing_cache()


def save_multiple_landing_settings(settings_dict):
    """
    Batch save multiple landing settings.
    """
    db = get_db_client()
    if not db:
        raise RuntimeError("Database client not available")
    
    rows = []
    for k, v in settings_dict.items():
        key = k if k.startswith('landing_') else f"landing_{k}"
        str_val = json.dumps(v) if isinstance(v, (list, dict)) else str(v)
        rows.append({'key': key, 'value': str_val})
        
    for row in rows:
        db.table('platform_settings').upsert(row, on_conflict='key').execute()
        
    clear_landing_cache()


def save_article(article_dict):
    """
    Create or update an article in DB.
    """
    articles = get_articles_db(force_refresh=True)
    art_id = article_dict.get('id')
    if not art_id:
        existing_int_ids = [k for k in articles.keys() if isinstance(k, int)]
        art_id = max(existing_int_ids + [0]) + 1
        article_dict['id'] = art_id
    else:
        try:
            art_id = int(art_id)
            article_dict['id'] = art_id
        except ValueError:
            pass

    articles[art_id] = article_dict

    serialized = {str(k): v for k, v in articles.items()}
    db = get_db_client()
    if not db:
        raise RuntimeError("Database client not available")
    
    db.table('platform_settings').upsert({
        'key': 'landing_articles_data',
        'value': json.dumps(serialized)
    }, on_conflict='key').execute()
    clear_landing_cache()
    return art_id


def delete_article(article_id):
    """
    Delete an article from DB.
    """
    articles = get_articles_db(force_refresh=True)
    found = False
    try:
        int_id = int(article_id)
        if int_id in articles:
            del articles[int_id]
            found = True
    except ValueError:
        pass
        
    if not found and str(article_id) in articles:
        del articles[str(article_id)]

    serialized = {str(k): v for k, v in articles.items()}
    db = get_db_client()
    if not db:
        raise RuntimeError("Database client not available")
    
    db.table('platform_settings').upsert({
        'key': 'landing_articles_data',
        'value': json.dumps(serialized)
    }, on_conflict='key').execute()
    clear_landing_cache()
