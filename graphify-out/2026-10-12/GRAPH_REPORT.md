# Graph Report - PickleballHub  (2026-10-12)

## Corpus Check
- 93 files · ~614,664 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: .css 9, .jfif 8, (none) 2)

## Summary
- 702 nodes · 1923 edges · 79 communities (27 shown, 52 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 35 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f88d3e67`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- superadmin/routes.py
- matchmaker_routes.py
- main/routes.py
- initMessages
- clubadmin/routes.py
- initCommunity
- PayMongo Integration Guide
- Single-Elimination Bracket Algorithm
- validate_and_upload
- create_app
- require_role
- script.js
- initTutorials
- auth/routes.py
- club_memberships Table
- KYC Verification Workflow
- vercel.json
- PayMongo Setup Guide for PickleballHub
- PickleballHub
- event_courts Table (Many-to-Many)
- tutorials Table (Supabase)
- platform_settings Table
- landing.html (Public Landing Page)
- events Table (Supabase)
- Flask Framework
- Supabase Python Client
- python-dotenv
- requests Library
- rules/graphify.md
- workflows/graphify.md
- clubs Table
- community_comments Table
- community_posts Table
- court_queues Table
- court_reservations Table
- courts Table (Supabase)
- disputes Table
- event_registrations Table
- facilities Table (Supabase)
- facility_staff Table
- post_likes Table
- tickets Table (Support)
- tournament_matches Table
- Walk-in Guest (Non-registered Player)
- court-hero.jpg (Court Hero Image)
- facilitystaff/walkin.html Template
- login.html Template
- player/dashboard.html Template
- base.html (Shared Layout Template)
- community_feed.html Template
- messages_chat.html Template
- superadmin/dashboard.html Template
- superadmin/reports.html Template (Charts)
- owner/dashboard.html Template
- facilitystaff/schedule.html Template
- clubadmin/leaderboard.html Template
- logo-icon.png (Favicon/Icon)
- background.jpg (App Background)
- bg.png (Background Image)
- signup.html Template
- get_user_tier
- clubadmin/events.py
- dashboard
- schedule.py
- db.py
- courts.py
- decorated_function
- social_routes.py
- staff.py
- trigger_booking_autochat
- get_db
- Multi-Role Dashboard Pattern (6 Roles)
- Role-Based Access Control (RBAC)
- notifications Table
- profiles Table (Supabase)
- HTMX Partial Queue Refresh Pattern

## God Nodes (most connected - your core abstractions)
1. `require_role()` - 225 edges
2. `get_db()` - 164 edges
3. `get_admin_db()` - 141 edges
4. `get_user_tier()` - 30 edges
5. `initMessages()` - 30 edges
6. `log_audit_action()` - 29 edges
7. `initCommunity()` - 25 edges
8. `initTutorials()` - 25 edges
9. `validate_and_upload()` - 25 edges
10. `check_feature_limit()` - 23 edges

## Surprising Connections (you probably didn't know these)
- `Architecture` --references--> `create_app()`  [INFERRED]
  CLAUDE.md → app/__init__.py
- `PickleballHub` --references--> `logo.png (PickleballHub Logo)`  [INFERRED]
  README.md → app/static/images/logo.png
- `GCash Reference Payment Pattern` --references--> `PayMongo Integration Guide`  [INFERRED]
  app/player/routes.py → docs/paymongo_setup_guide.md
- `GCash Reference Payment Pattern` --conceptually_related_to--> `PayMongo Checkout Session API`  [INFERRED]
  app/player/routes.py → docs/paymongo_setup_guide.md
- `Vercel Deployment` --references--> `vercel.json (Deployment Config)`  [EXTRACTED]
  README.md → vercel.json

## Import Cycles
- 3-file cycle: `app/__init__.py -> app/player/__init__.py -> app/player/routes.py -> app/__init__.py`
- 4-file cycle: `app/__init__.py -> app/player/__init__.py -> app/player/matchmaker_routes.py -> app/player/routes.py -> app/__init__.py`
- 4-file cycle: `app/__init__.py -> app/player/__init__.py -> app/player/queue_routes.py -> app/player/routes.py -> app/__init__.py`
- 4-file cycle: `app/__init__.py -> app/player/__init__.py -> app/player/reservations.py -> app/player/routes.py -> app/__init__.py`

## Communities (79 total, 52 thin omitted)

### Community 0 - "superadmin/routes.py"
Cohesion: 0.09
Nodes (48): log_audit_action(), Log administrative or critical actions to the database for audit trail. Safe to…, clear_landing_cache(), delete_article(), get_article_by_id(), get_articles_db(), get_landing_content(), Returns complete landing page configuration with DB overrides. Cached for 30s… (+40 more)

### Community 1 - "matchmaker_routes.py"
Cohesion: 0.23
Nodes (17): format_date_friendly(), format_time_12h(), get_lobby_display_status(), matchmaker(), matchmaker_create(), matchmaker_delete(), matchmaker_detail(), matchmaker_edit() (+9 more)

### Community 2 - "main/routes.py"
Cohesion: 0.08
Nodes (41): about_us(), api_courts_search(), api_tutorials_delete(), api_tutorials_list(), api_tutorials_save(), api_tutorials_sign_upload(), api_tutorials_upload(), clinics() (+33 more)

### Community 3 - "initMessages"
Cohesion: 0.16
Nodes (28): initMessages(), applyFilter(), closeModal(), dateSep(), esc(), fullTime(), getAvatarGradient(), getLobbyIdSet() (+20 more)

### Community 4 - "clubadmin/routes.py"
Cohesion: 0.10
Nodes (35): api_courts_by_facility(), club_setup(), community(), dashboard(), log_casual_match(), mark_notifications_read(), messages(), notifications() (+27 more)

### Community 5 - "initCommunity"
Cohesion: 0.16
Nodes (24): initCommunity(), bindFeedEvents(), escapeHTML(), filterPosts(), formatPostContent(), handleDeleteComment(), handleDeletePost(), handleLike() (+16 more)

### Community 6 - "PayMongo Integration Guide"
Cohesion: 0.40
Nodes (6): Centralized Collection Multi-Vendor Pattern, PayMongo Checkout Session API, PayMongo Integration Guide, PayMongo Webhook Handler (payment.paid), GCash Reference Payment Pattern, player/payment.html (GCash Payment UI)

### Community 8 - "validate_and_upload"
Cohesion: 0.20
Nodes (17): check_feature_limit(), get_tier_limits(), Return the dictionary of limits for the given role and tier., Checks if a user has permission to perform an action or if they have hit a…, add_facility(), clean_description(), delete_facility(), edit_facility() (+9 more)

### Community 9 - "create_app"
Cohesion: 0.09
Nodes (12): create_app(), inject_csrf_token(), inject_current_user(), inject_platform_settings(), verify_session_integrity(), load_platform_settings(), Architecture, Authentication Flow (+4 more)

### Community 10 - "require_role"
Cohesion: 0.06
Nodes (91): change_password(), community(), dashboard(), disputes(), mark_notifications_read(), messages(), notifications(), profile() (+83 more)

### Community 11 - "script.js"
Cohesion: 0.17
Nodes (15): getSelectedRole(), nextSignupStep(), nextSlide(), prevSignupStep(), prevSlide(), resetSliderTimer(), selectRoleGrid(), setOwnerFieldsRequired() (+7 more)

### Community 12 - "initTutorials"
Cohesion: 0.17
Nodes (23): initTutorials(), closeAddModal(), deleteTutorial(), directUploadToSignedUrl(), esc(), extractYoutubeId(), formatFileSize(), getCsrfToken() (+15 more)

### Community 13 - "auth/routes.py"
Cohesion: 0.13
Nodes (25): api_live_dashboard_stats(), demo_player(), forgot_password(), get_live_dashboard_stats(), get_lobby_ids(), _get_plan_info(), login(), logout() (+17 more)

### Community 17 - "vercel.json"
Cohesion: 0.40
Nodes (4): builds, headers, routes, version

### Community 18 - "PayMongo Setup Guide for PickleballHub"
Cohesion: 0.20
Nodes (9): 1. Account Creation and Keys, 2. The Checkout Workflow (Multi-Vendor), 3. Handling Webhooks (Crucial Step), 4. Local Testing (ngrok), code:env (PAYMONGO_PUBLIC_KEY=pk_test_xxxxxxxxxxxxx), code:python (@app.route('/api/webhooks/paymongo', methods=['POST'])), Next Steps for Development, PayMongo Setup Guide for PickleballHub (+1 more)

### Community 19 - "PickleballHub"
Cohesion: 0.12
Nodes (16): logo.png (PickleballHub Logo), Architecture, Authentication Flow, code:block1 (PickleballHub/), code:bash (# Install dependencies), Commands, Dependencies, Environment Variables (+8 more)

### Community 63 - "get_user_tier"
Cohesion: 0.16
Nodes (15): checkout_page(), _get_logged_in_user(), route, Main subscription and membership dashboard for logged in users., Legitimate GCash payment checkout page for subscriptions., subscription_page(), get_user_tier(), app/billing/tiers.py PickleballHub Centralized Subscription & Tier Limits… (+7 more)

### Community 64 - "clubadmin/events.py"
Cohesion: 0.19
Nodes (17): check_court_conflict(), normalize_time_str(), notify_facility_staff_and_owner(), Check if interval [s1, e1) overlaps interval [s2, e2)., Sends in-app notifications to the facility owner and all assigned facility…, Check if a court is already booked or reserved on the given date and time…, Normalize time string to HH:MM:SS for safe lexical and logical comparison., times_overlap() (+9 more)

### Community 65 - "dashboard"
Cohesion: 0.15
Nodes (15): get_processed_queues(), route, queue(), queue_partial(), Fetch queues for today, process wait times, and auto-complete games 15 mins…, change_password(), compute_player_sports_data(), dashboard() (+7 more)

### Community 66 - "schedule.py"
Cohesion: 0.43
Nodes (7): api_schedule(), court_schedule(), _format_time_friendly(), route, Convert '14:00:00' or '14:00' to '2:00 PM'., Normalize and format reservation record for template and JSON consumption., _serialize_reservation()

### Community 67 - "db.py"
Cohesion: 0.16
Nodes (14): Thread-safe, request-scoped database helper for Supabase. Provides separation…, Role-based access control decorators for protecting routes., datetime, dotenv, flask, flask_limiter, flask_limiter_util, flask_wtf_csrf (+6 more)

### Community 68 - "courts.py"
Cohesion: 0.48
Nodes (6): add_court(), courts(), delete_court(), edit_court(), route, toggle_court_status()

### Community 69 - "decorated_function"
Cohesion: 0.33
Nodes (6): _get_dashboard_for_role(), has_role_permission(), Returns True if user_role is in allowed_roles, or if authorized via logical…, Return the dashboard URL for a given role., decorator(), decorated_function()

### Community 70 - "social_routes.py"
Cohesion: 0.43
Nodes (7): community(), delete_notification(), mark_notifications_read(), messages(), notifications(), route, tutorials()

### Community 71 - "staff.py"
Cohesion: 0.53
Nodes (5): add_staff(), edit_staff_assignment(), route, remove_staff_assignment(), staff()

### Community 72 - "trigger_booking_autochat"
Cohesion: 0.50
Nodes (4): Sends an automated message from sender_id to recipient_id. If a 1-to-1…, Triggers automated chats from the facility owner and assigned staff to the…, send_auto_message(), trigger_booking_autochat()

### Community 82 - "get_db"
Cohesion: 0.07
Nodes (59): get_facility_court_timeline(), Get all courts in facility along with their occupied time blocks on the…, approve_member(), export_members_csv(), member_details(), members(), route, reject_member() (+51 more)

## Knowledge Gaps
- **49 isolated node(s):** `_spinStyle`, `version`, `builds`, `routes`, `headers` (+44 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 214 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **52 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_admin_db()` connect `require_role` to `clubadmin/events.py`, `superadmin/routes.py`, `main/routes.py`, `db.py`, `clubadmin/routes.py`, `courts.py`, `schedule.py`, `staff.py`, `validate_and_upload`, `create_app`, `matchmaker_routes.py`, `dashboard`, `auth/routes.py`, `get_db`, `get_user_tier`?**
  _High betweenness centrality (0.141) - this node is a cross-community bridge._
- **Why does `require_role()` connect `require_role` to `clubadmin/events.py`, `matchmaker_routes.py`, `schedule.py`, `db.py`, `clubadmin/routes.py`, `decorated_function`, `courts.py`, `staff.py`, `validate_and_upload`, `dashboard`, `social_routes.py`, `superadmin/routes.py`, `get_db`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Why does `get_db()` connect `get_db` to `clubadmin/events.py`, `matchmaker_routes.py`, `schedule.py`, `db.py`, `clubadmin/routes.py`, `decorated_function`, `courts.py`, `staff.py`, `validate_and_upload`, `dashboard`, `require_role`, `social_routes.py`, `superadmin/routes.py`, `auth/routes.py`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **What connects `_spinStyle`, `version`, `builds` to the rest of the system?**
  _49 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `superadmin/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08897959183673469 - nodes in this community are weakly interconnected._
- **Should `main/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0753045404208195 - nodes in this community are weakly interconnected._
- **Should `clubadmin/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09851551956815115 - nodes in this community are weakly interconnected._