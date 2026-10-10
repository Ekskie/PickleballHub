# Graph Report - PickleballHub  (2026-10-10)

## Corpus Check
- 90 files · ~584,606 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: .css 9, .jfif 8, (none) 2)

## Summary
- 669 nodes · 1774 edges · 78 communities (26 shown, 52 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 34 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e380d9a2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- superadmin/routes.py
- owner/routes.py
- main/routes.py
- initMessages
- clubadmin/routes.py
- initCommunity
- PayMongo Integration Guide
- Single-Elimination Bracket Algorithm
- reservations.py
- create_app
- require_role
- script.js
- initTutorials
- billing/routes.py
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
- social_routes.py
- player/routes.py
- schedule.py
- db.py
- CLAUDE.md
- decorated_function
- queue_routes.py
- trigger_booking_autochat
- validate_and_upload
- get_db
- Multi-Role Dashboard Pattern (6 Roles)
- Role-Based Access Control (RBAC)
- notifications Table
- profiles Table (Supabase)
- HTMX Partial Queue Refresh Pattern

## God Nodes (most connected - your core abstractions)
1. `require_role()` - 216 edges
2. `get_db()` - 163 edges
3. `get_admin_db()` - 123 edges
4. `initMessages()` - 30 edges
5. `initCommunity()` - 25 edges
6. `validate_and_upload()` - 25 edges
7. `initTutorials()` - 23 edges
8. `log_audit_action()` - 21 edges
9. `create_app()` - 20 edges
10. `upload_avatar()` - 15 edges

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

## Communities (78 total, 52 thin omitted)

### Community 0 - "superadmin/routes.py"
Cohesion: 0.08
Nodes (51): log_audit_action(), Log administrative or critical actions to the database for audit trail. Safe to…, inject_platform_settings(), clear_landing_cache(), delete_article(), get_article_by_id(), get_articles_db(), get_landing_content() (+43 more)

### Community 1 - "owner/routes.py"
Cohesion: 0.27
Nodes (12): Uploads an avatar file to Supabase storage and returns public URL, or None.…, upload_avatar(), change_password(), community(), dashboard(), mark_notifications_read(), messages(), notifications() (+4 more)

### Community 2 - "main/routes.py"
Cohesion: 0.10
Nodes (33): about_us(), api_courts_search(), api_tutorials_delete(), api_tutorials_list(), api_tutorials_save(), api_tutorials_sign_upload(), api_tutorials_upload(), clinics() (+25 more)

### Community 3 - "initMessages"
Cohesion: 0.16
Nodes (28): initMessages(), applyFilter(), closeModal(), dateSep(), esc(), fullTime(), getAvatarGradient(), getLobbyIdSet() (+20 more)

### Community 4 - "clubadmin/routes.py"
Cohesion: 0.07
Nodes (48): api_live_dashboard_stats(), demo_player(), forgot_password(), get_live_dashboard_stats(), get_lobby_ids(), login(), logout(), limit (+40 more)

### Community 5 - "initCommunity"
Cohesion: 0.16
Nodes (24): initCommunity(), bindFeedEvents(), escapeHTML(), filterPosts(), formatPostContent(), handleDeleteComment(), handleDeletePost(), handleLike() (+16 more)

### Community 6 - "PayMongo Integration Guide"
Cohesion: 0.40
Nodes (6): Centralized Collection Multi-Vendor Pattern, PayMongo Checkout Session API, PayMongo Integration Guide, PayMongo Webhook Handler (payment.paid), GCash Reference Payment Pattern, player/payment.html (GCash Payment UI)

### Community 8 - "reservations.py"
Cohesion: 0.18
Nodes (19): api_facility_month_availability(), api_facility_occupancy(), api_my_bookings(), api_reservation_courts(), api_reservation_slots(), api_upgrade_pro(), book_reservation(), cancel_reservation() (+11 more)

### Community 9 - "create_app"
Cohesion: 0.15
Nodes (4): create_app(), inject_csrf_token(), inject_current_user(), verify_session_integrity()

### Community 10 - "require_role"
Cohesion: 0.06
Nodes (89): change_password(), community(), dashboard(), disputes(), mark_notifications_read(), messages(), notifications(), profile() (+81 more)

### Community 11 - "script.js"
Cohesion: 0.18
Nodes (12): getSelectedRole(), nextSignupStep(), nextSlide(), prevSignupStep(), prevSlide(), resetSliderTimer(), selectRoleGrid(), setOwnerFieldsRequired() (+4 more)

### Community 12 - "initTutorials"
Cohesion: 0.18
Nodes (21): initTutorials(), closeAddModal(), deleteTutorial(), directUploadToSignedUrl(), esc(), extractYoutubeId(), formatFileSize(), getCsrfToken() (+13 more)

### Community 13 - "billing/routes.py"
Cohesion: 0.17
Nodes (17): checkout_page(), _get_logged_in_user(), route, Main subscription and membership dashboard for logged in users., Legitimate GCash payment checkout page for subscriptions., subscription_page(), check_feature_limit(), get_tier_limits() (+9 more)

### Community 17 - "vercel.json"
Cohesion: 0.40
Nodes (4): builds, headers, routes, version

### Community 18 - "PayMongo Setup Guide for PickleballHub"
Cohesion: 0.20
Nodes (9): 1. Account Creation and Keys, 2. The Checkout Workflow (Multi-Vendor), 3. Handling Webhooks (Crucial Step), 4. Local Testing (ngrok), code:env (PAYMONGO_PUBLIC_KEY=pk_test_xxxxxxxxxxxxx), code:python (@app.route('/api/webhooks/paymongo', methods=['POST'])), Next Steps for Development, PayMongo Setup Guide for PickleballHub (+1 more)

### Community 19 - "PickleballHub"
Cohesion: 0.12
Nodes (16): logo.png (PickleballHub Logo), Architecture, Authentication Flow, code:block1 (PickleballHub/), code:bash (# Install dependencies), Commands, Dependencies, Environment Variables (+8 more)

### Community 63 - "social_routes.py"
Cohesion: 0.43
Nodes (7): community(), delete_notification(), mark_notifications_read(), messages(), notifications(), route, tutorials()

### Community 64 - "player/routes.py"
Cohesion: 0.31
Nodes (10): change_password(), compute_player_sports_data(), dashboard(), delete_account(), format_date_friendly(), format_time_12h(), limit, route (+2 more)

### Community 65 - "schedule.py"
Cohesion: 0.39
Nodes (7): api_schedule(), court_schedule(), _format_time_friendly(), route, Convert '14:00:00' or '14:00' to '2:00 PM'., Normalize and format reservation record for template and JSON consumption., _serialize_reservation()

### Community 66 - "db.py"
Cohesion: 0.18
Nodes (11): Thread-safe, request-scoped database helper for Supabase. Provides separation…, Role-based access control decorators for protecting routes., datetime, dotenv, flask, flask_limiter, flask_limiter_util, flask_wtf_csrf (+3 more)

### Community 67 - "CLAUDE.md"
Cohesion: 0.25
Nodes (6): Architecture, Authentication Flow, Commands, Dependencies, Environment Variables, Project Overview

### Community 68 - "decorated_function"
Cohesion: 0.33
Nodes (6): _get_dashboard_for_role(), has_role_permission(), Returns True if user_role is in allowed_roles, or if authorized via logical…, Return the dashboard URL for a given role., decorator(), decorated_function()

### Community 69 - "queue_routes.py"
Cohesion: 0.53
Nodes (5): get_processed_queues(), route, queue(), queue_partial(), Fetch queues for today, process wait times, and auto-complete games 15 mins…

### Community 70 - "trigger_booking_autochat"
Cohesion: 0.50
Nodes (4): Sends an automated message from sender_id to recipient_id. If a 1-to-1…, Triggers automated chats from the facility owner and assigned staff to the…, send_auto_message(), trigger_booking_autochat()

### Community 71 - "validate_and_upload"
Cohesion: 0.11
Nodes (27): add_facility(), clean_description(), delete_facility(), edit_facility(), extract_amenities(), facilities(), kyc_upload(), route (+19 more)

### Community 82 - "get_db"
Cohesion: 0.07
Nodes (57): change_event_status(), create_event(), delete_event(), edit_event(), event_check_in(), event_participants(), events(), facility_payment() (+49 more)

## Knowledge Gaps
- **49 isolated node(s):** `_spinStyle`, `version`, `builds`, `routes`, `headers` (+44 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 204 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **52 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `require_role()` connect `require_role` to `player/routes.py`, `owner/routes.py`, `db.py`, `schedule.py`, `clubadmin/routes.py`, `decorated_function`, `queue_routes.py`, `validate_and_upload`, `reservations.py`, `superadmin/routes.py`, `get_db`, `social_routes.py`?**
  _High betweenness centrality (0.141) - this node is a cross-community bridge._
- **Why does `get_admin_db()` connect `require_role` to `superadmin/routes.py`, `owner/routes.py`, `db.py`, `main/routes.py`, `clubadmin/routes.py`, `schedule.py`, `player/routes.py`, `validate_and_upload`, `reservations.py`, `create_app`, `billing/routes.py`, `get_db`?**
  _High betweenness centrality (0.133) - this node is a cross-community bridge._
- **Why does `get_db()` connect `get_db` to `player/routes.py`, `owner/routes.py`, `db.py`, `schedule.py`, `clubadmin/routes.py`, `decorated_function`, `queue_routes.py`, `validate_and_upload`, `reservations.py`, `superadmin/routes.py`, `require_role`, `social_routes.py`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `initMessages()` (e.g. with `applyFilter()` and `closeModal()`) actually correct?**
  _`initMessages()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `_spinStyle`, `version`, `builds` to the rest of the system?**
  _49 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `superadmin/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08176100628930817 - nodes in this community are weakly interconnected._
- **Should `main/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09982174688057041 - nodes in this community are weakly interconnected._