# Graph Report - PickleballHub  (2026-10-06)

## Corpus Check
- 87 files · ~571,041 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: .css 9, .jfif 8, (none) 2)

## Summary
- 641 nodes · 1673 edges · 75 communities (23 shown, 52 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 34 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4791f4b2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- require_role
- matchmaker_routes.py
- main/routes.py
- initMessages
- clubadmin/routes.py
- initCommunity
- PayMongo Integration Guide
- Single-Elimination Bracket Algorithm
- reservations.py
- create_app
- owner/routes.py
- script.js
- initTutorials
- tiers.py
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
- courts.py
- player/routes.py
- schedule.py
- db.py
- CLAUDE.md
- auth/routes.py
- get_db
- Multi-Role Dashboard Pattern (6 Roles)
- Role-Based Access Control (RBAC)
- notifications Table
- profiles Table (Supabase)
- HTMX Partial Queue Refresh Pattern

## God Nodes (most connected - your core abstractions)
1. `require_role()` - 211 edges
2. `get_db()` - 159 edges
3. `get_admin_db()` - 119 edges
4. `initMessages()` - 30 edges
5. `initCommunity()` - 25 edges
6. `initTutorials()` - 22 edges
7. `validate_and_upload()` - 21 edges
8. `create_app()` - 19 edges
9. `log_audit_action()` - 16 edges
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

## Communities (75 total, 52 thin omitted)

### Community 0 - "require_role"
Cohesion: 0.08
Nodes (74): change_password(), community(), dashboard(), disputes(), mark_notifications_read(), messages(), notifications(), profile() (+66 more)

### Community 1 - "matchmaker_routes.py"
Cohesion: 0.26
Nodes (15): format_date_friendly(), format_time_12h(), get_lobby_display_status(), matchmaker(), matchmaker_create(), matchmaker_delete(), matchmaker_detail(), matchmaker_edit() (+7 more)

### Community 2 - "main/routes.py"
Cohesion: 0.11
Nodes (29): about_us(), api_courts_search(), api_tutorials_delete(), api_tutorials_list(), api_tutorials_save(), api_tutorials_upload(), clinics(), community() (+21 more)

### Community 3 - "initMessages"
Cohesion: 0.16
Nodes (28): initMessages(), applyFilter(), closeModal(), dateSep(), esc(), fullTime(), getAvatarGradient(), getLobbyIdSet() (+20 more)

### Community 4 - "clubadmin/routes.py"
Cohesion: 0.10
Nodes (36): api_courts_by_facility(), club_setup(), community(), dashboard(), log_casual_match(), mark_notifications_read(), messages(), notifications() (+28 more)

### Community 5 - "initCommunity"
Cohesion: 0.16
Nodes (24): initCommunity(), bindFeedEvents(), escapeHTML(), filterPosts(), formatPostContent(), handleDeleteComment(), handleDeletePost(), handleLike() (+16 more)

### Community 6 - "PayMongo Integration Guide"
Cohesion: 0.40
Nodes (6): Centralized Collection Multi-Vendor Pattern, PayMongo Checkout Session API, PayMongo Integration Guide, PayMongo Webhook Handler (payment.paid), GCash Reference Payment Pattern, player/payment.html (GCash Payment UI)

### Community 8 - "reservations.py"
Cohesion: 0.09
Nodes (33): checkout_page(), _get_logged_in_user(), route, Main subscription and membership dashboard for logged in users., Legitimate GCash payment checkout page for subscriptions., subscription_page(), api_facility_month_availability(), api_facility_occupancy() (+25 more)

### Community 9 - "create_app"
Cohesion: 0.14
Nodes (7): create_app(), inject_csrf_token(), inject_platform_settings(), verify_session_integrity(), get_db_client(), load_platform_settings(), Returns a Supabase client for querying platform_settings. Prefers the request-…

### Community 10 - "owner/routes.py"
Cohesion: 0.15
Nodes (19): Sends an automated message from sender_id to recipient_id. If a 1-to-1…, Triggers automated chats from the facility owner and assigned staff to the…, send_auto_message(), trigger_booking_autochat(), approve_payment(), decline_payment(), payment_ledger(), route (+11 more)

### Community 11 - "script.js"
Cohesion: 0.18
Nodes (12): getSelectedRole(), nextSignupStep(), nextSlide(), prevSignupStep(), prevSlide(), resetSliderTimer(), selectRoleGrid(), setOwnerFieldsRequired() (+4 more)

### Community 12 - "initTutorials"
Cohesion: 0.19
Nodes (20): initTutorials(), closeAddModal(), deleteTutorial(), esc(), extractYoutubeId(), formatFileSize(), getCsrfToken(), getLevelMeta() (+12 more)

### Community 13 - "tiers.py"
Cohesion: 0.22
Nodes (11): get_tier_limits(), get_user_tier(), app/billing/tiers.py PickleballHub Centralized Subscription & Tier Limits…, Returns the active subscription tier string ('free', 'pro', 'elite') for a…, Return the dictionary of limits for the given role and tier., Decorator to protect routes that require a specific minimum subscription tier.…, require_tier(), decorator() (+3 more)

### Community 17 - "vercel.json"
Cohesion: 0.40
Nodes (4): builds, headers, routes, version

### Community 18 - "PayMongo Setup Guide for PickleballHub"
Cohesion: 0.20
Nodes (9): 1. Account Creation and Keys, 2. The Checkout Workflow (Multi-Vendor), 3. Handling Webhooks (Crucial Step), 4. Local Testing (ngrok), code:env (PAYMONGO_PUBLIC_KEY=pk_test_xxxxxxxxxxxxx), code:python (@app.route('/api/webhooks/paymongo', methods=['POST'])), Next Steps for Development, PayMongo Setup Guide for PickleballHub (+1 more)

### Community 19 - "PickleballHub"
Cohesion: 0.12
Nodes (16): logo.png (PickleballHub Logo), Architecture, Authentication Flow, code:block1 (PickleballHub/), code:bash (# Install dependencies), Commands, Dependencies, Environment Variables (+8 more)

### Community 63 - "courts.py"
Cohesion: 0.36
Nodes (8): check_feature_limit(), Checks if a user has permission to perform an action or if they have hit a…, add_court(), courts(), delete_court(), edit_court(), route, toggle_court_status()

### Community 64 - "player/routes.py"
Cohesion: 0.11
Nodes (27): Uploads an avatar file to Supabase storage and returns public URL, or None.…, upload_avatar(), club_detail(), club_payment(), clubs(), join_club(), leave_club(), my_clubs() (+19 more)

### Community 65 - "schedule.py"
Cohesion: 0.39
Nodes (7): api_schedule(), court_schedule(), _format_time_friendly(), route, Convert '14:00:00' or '14:00' to '2:00 PM'., Normalize and format reservation record for template and JSON consumption., _serialize_reservation()

### Community 66 - "db.py"
Cohesion: 0.16
Nodes (13): is_jwt_expired(), Thread-safe, request-scoped database helper for Supabase. Provides separation…, Decodes a JWT payload locally to check if it's expired or close to it (5-minute…, route, submit_ticket(), dotenv, flask_limiter, flask_limiter_util (+5 more)

### Community 67 - "CLAUDE.md"
Cohesion: 0.25
Nodes (6): Architecture, Authentication Flow, Commands, Dependencies, Environment Variables, Project Overview

### Community 71 - "auth/routes.py"
Cohesion: 0.09
Nodes (36): api_live_dashboard_stats(), demo_player(), forgot_password(), get_live_dashboard_stats(), get_lobby_ids(), login(), logout(), limit (+28 more)

### Community 82 - "get_db"
Cohesion: 0.06
Nodes (66): change_event_status(), create_event(), delete_event(), edit_event(), event_check_in(), event_participants(), events(), facility_payment() (+58 more)

## Knowledge Gaps
- **49 isolated node(s):** `_spinStyle`, `version`, `builds`, `routes`, `headers` (+44 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 192 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **52 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `require_role()` connect `require_role` to `player/routes.py`, `schedule.py`, `matchmaker_routes.py`, `clubadmin/routes.py`, `auth/routes.py`, `reservations.py`, `owner/routes.py`, `get_db`, `courts.py`?**
  _High betweenness centrality (0.138) - this node is a cross-community bridge._
- **Why does `get_admin_db()` connect `require_role` to `player/routes.py`, `schedule.py`, `db.py`, `main/routes.py`, `clubadmin/routes.py`, `matchmaker_routes.py`, `auth/routes.py`, `reservations.py`, `create_app`, `owner/routes.py`, `tiers.py`, `get_db`, `courts.py`?**
  _High betweenness centrality (0.132) - this node is a cross-community bridge._
- **Why does `get_db()` connect `get_db` to `require_role`, `schedule.py`, `db.py`, `player/routes.py`, `clubadmin/routes.py`, `matchmaker_routes.py`, `auth/routes.py`, `reservations.py`, `owner/routes.py`, `courts.py`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `initMessages()` (e.g. with `applyFilter()` and `closeModal()`) actually correct?**
  _`initMessages()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `_spinStyle`, `version`, `builds` to the rest of the system?**
  _49 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `require_role` be split into smaller, more focused modules?**
  _Cohesion score 0.07822135670236936 - nodes in this community are weakly interconnected._
- **Should `main/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11494252873563218 - nodes in this community are weakly interconnected._