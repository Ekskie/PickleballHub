# Graph Report - PickleballHub  (2026-09-26)

## Corpus Check
- 81 files · ~547,098 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: .css 9, .jfif 8, (none) 2)

## Summary
- 593 nodes · 1528 edges · 72 communities (20 shown, 52 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 29 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `aa990f79`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- require_role
- matchmaker_routes.py
- db.py
- initMessages
- clubadmin/routes.py
- initCommunity
- PayMongo Integration Guide
- Single-Elimination Bracket Algorithm
- reservations.py
- social_routes.py
- auth/routes.py
- script.js
- initTutorials
- CLAUDE.md
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
- player/routes.py
- decorators.py
- facilities.py
- get_db
- Multi-Role Dashboard Pattern (6 Roles)
- Role-Based Access Control (RBAC)
- notifications Table
- profiles Table (Supabase)
- HTMX Partial Queue Refresh Pattern

## God Nodes (most connected - your core abstractions)
1. `require_role()` - 208 edges
2. `get_db()` - 159 edges
3. `get_admin_db()` - 108 edges
4. `initMessages()` - 30 edges
5. `initCommunity()` - 25 edges
6. `create_app()` - 16 edges
7. `upload_avatar()` - 15 edges
8. `get_initial_rating()` - 15 edges
9. `validate_and_upload()` - 14 edges
10. `log_audit_action()` - 13 edges

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

## Communities (72 total, 52 thin omitted)

### Community 0 - "require_role"
Cohesion: 0.08
Nodes (67): change_password(), community(), dashboard(), disputes(), mark_notifications_read(), messages(), notifications(), profile() (+59 more)

### Community 1 - "matchmaker_routes.py"
Cohesion: 0.23
Nodes (17): format_date_friendly(), format_time_12h(), get_lobby_display_status(), matchmaker(), matchmaker_create(), matchmaker_delete(), matchmaker_detail(), matchmaker_edit() (+9 more)

### Community 2 - "db.py"
Cohesion: 0.06
Nodes (42): is_jwt_expired(), Thread-safe, request-scoped database helper for Supabase. Provides separation…, Decodes a JWT payload locally to check if it's expired or close to it (5-minute…, create_app(), inject_csrf_token(), inject_current_user(), inject_platform_settings(), verify_session_integrity() (+34 more)

### Community 3 - "initMessages"
Cohesion: 0.16
Nodes (28): initMessages(), applyFilter(), closeModal(), dateSep(), esc(), fullTime(), getAvatarGradient(), getLobbyIdSet() (+20 more)

### Community 4 - "clubadmin/routes.py"
Cohesion: 0.11
Nodes (32): api_courts_by_facility(), club_setup(), community(), dashboard(), log_casual_match(), mark_notifications_read(), messages(), notifications() (+24 more)

### Community 5 - "initCommunity"
Cohesion: 0.16
Nodes (24): initCommunity(), bindFeedEvents(), escapeHTML(), filterPosts(), formatPostContent(), handleDeleteComment(), handleDeletePost(), handleLike() (+16 more)

### Community 6 - "PayMongo Integration Guide"
Cohesion: 0.40
Nodes (6): Centralized Collection Multi-Vendor Pattern, PayMongo Checkout Session API, PayMongo Integration Guide, PayMongo Webhook Handler (payment.paid), GCash Reference Payment Pattern, player/payment.html (GCash Payment UI)

### Community 8 - "reservations.py"
Cohesion: 0.21
Nodes (17): api_facility_month_availability(), api_facility_occupancy(), api_my_bookings(), api_reservation_courts(), api_reservation_slots(), book_reservation(), cancel_reservation(), confirm_payment() (+9 more)

### Community 9 - "social_routes.py"
Cohesion: 0.21
Nodes (12): leaderboard(), leaderboard_challenge(), player_chat(), player_details(), route, community(), delete_notification(), mark_notifications_read() (+4 more)

### Community 10 - "auth/routes.py"
Cohesion: 0.14
Nodes (25): api_live_dashboard_stats(), demo_player(), forgot_password(), get_live_dashboard_stats(), get_lobby_ids(), login(), logout(), limit (+17 more)

### Community 11 - "script.js"
Cohesion: 0.21
Nodes (6): nextSlide(), prevSlide(), resetSliderTimer(), setSlide(), showSlide(), startSliderTimer()

### Community 12 - "initTutorials"
Cohesion: 0.28
Nodes (11): initTutorials(), deleteTutorial(), editTutorial(), esc(), levelClass(), levelIcon(), loadTutorials(), openWatch() (+3 more)

### Community 13 - "CLAUDE.md"
Cohesion: 0.25
Nodes (6): Architecture, Authentication Flow, Commands, Dependencies, Environment Variables, Project Overview

### Community 17 - "vercel.json"
Cohesion: 0.40
Nodes (4): builds, headers, routes, version

### Community 18 - "PayMongo Setup Guide for PickleballHub"
Cohesion: 0.20
Nodes (9): 1. Account Creation and Keys, 2. The Checkout Workflow (Multi-Vendor), 3. Handling Webhooks (Crucial Step), 4. Local Testing (ngrok), code:env (PAYMONGO_PUBLIC_KEY=pk_test_xxxxxxxxxxxxx), code:python (@app.route('/api/webhooks/paymongo', methods=['POST'])), Next Steps for Development, PayMongo Setup Guide for PickleballHub (+1 more)

### Community 19 - "PickleballHub"
Cohesion: 0.12
Nodes (16): logo.png (PickleballHub Logo), Architecture, Authentication Flow, code:block1 (PickleballHub/), code:bash (# Install dependencies), Commands, Dependencies, Environment Variables (+8 more)

### Community 64 - "player/routes.py"
Cohesion: 0.17
Nodes (18): Uploads an avatar file to Supabase storage and returns public URL, or None.…, upload_avatar(), get_processed_queues(), route, queue(), queue_partial(), Fetch queues for today, process wait times, and auto-complete games 15 mins…, change_password() (+10 more)

### Community 66 - "decorators.py"
Cohesion: 0.07
Nodes (39): Sends an automated message from sender_id to recipient_id. If a 1-to-1…, Triggers automated chats from the facility owner and assigned staff to the…, send_auto_message(), trigger_booking_autochat(), ledger(), route, _get_dashboard_for_role(), has_role_permission() (+31 more)

### Community 71 - "facilities.py"
Cohesion: 0.10
Nodes (30): add_facility(), clean_description(), delete_facility(), edit_facility(), extract_amenities(), facilities(), kyc_upload(), route (+22 more)

### Community 82 - "get_db"
Cohesion: 0.09
Nodes (53): change_event_status(), create_event(), delete_event(), edit_event(), event_check_in(), event_participants(), events(), facility_payment() (+45 more)

## Knowledge Gaps
- **49 isolated node(s):** `_spinStyle`, `version`, `builds`, `routes`, `headers` (+44 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 182 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **52 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `require_role()` connect `require_role` to `player/routes.py`, `matchmaker_routes.py`, `decorators.py`, `clubadmin/routes.py`, `facilities.py`, `reservations.py`, `social_routes.py`, `get_db`?**
  _High betweenness centrality (0.154) - this node is a cross-community bridge._
- **Why does `get_db()` connect `get_db` to `require_role`, `matchmaker_routes.py`, `db.py`, `decorators.py`, `clubadmin/routes.py`, `player/routes.py`, `facilities.py`, `reservations.py`, `social_routes.py`, `auth/routes.py`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **Why does `get_admin_db()` connect `require_role` to `player/routes.py`, `matchmaker_routes.py`, `db.py`, `decorators.py`, `clubadmin/routes.py`, `facilities.py`, `reservations.py`, `auth/routes.py`, `get_db`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `initMessages()` (e.g. with `applyFilter()` and `closeModal()`) actually correct?**
  _`initMessages()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `_spinStyle`, `version`, `builds` to the rest of the system?**
  _49 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `require_role` be split into smaller, more focused modules?**
  _Cohesion score 0.08447488584474885 - nodes in this community are weakly interconnected._
- **Should `db.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05723905723905724 - nodes in this community are weakly interconnected._