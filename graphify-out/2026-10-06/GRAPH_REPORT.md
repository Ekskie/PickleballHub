# Graph Report - PickleballHub  (2026-09-27)

## Corpus Check
- 86 files · ~565,836 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: .css 9, .jfif 8, (none) 2)

## Summary
- 621 nodes · 1619 edges · 72 communities (20 shown, 52 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 31 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `aa990f79`
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
- superadmin/routes.py
- owner/routes.py
- script.js
- initTutorials
- create_app
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
- db.py
- auth/routes.py
- get_db
- Multi-Role Dashboard Pattern (6 Roles)
- Role-Based Access Control (RBAC)
- notifications Table
- profiles Table (Supabase)
- HTMX Partial Queue Refresh Pattern

## God Nodes (most connected - your core abstractions)
1. `require_role()` - 209 edges
2. `get_db()` - 159 edges
3. `get_admin_db()` - 114 edges
4. `initMessages()` - 30 edges
5. `initCommunity()` - 25 edges
6. `create_app()` - 19 edges
7. `validate_and_upload()` - 19 edges
8. `upload_avatar()` - 15 edges
9. `get_initial_rating()` - 15 edges
10. `get_user_tier()` - 13 edges

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
Cohesion: 0.09
Nodes (61): change_password(), community(), dashboard(), disputes(), mark_notifications_read(), messages(), notifications(), profile() (+53 more)

### Community 1 - "matchmaker_routes.py"
Cohesion: 0.26
Nodes (15): format_date_friendly(), format_time_12h(), get_lobby_display_status(), matchmaker(), matchmaker_create(), matchmaker_delete(), matchmaker_detail(), matchmaker_edit() (+7 more)

### Community 2 - "main/routes.py"
Cohesion: 0.16
Nodes (21): about_us(), api_courts_search(), clinics(), community(), courts_listing(), _extract_yt_id(), get_db(), index() (+13 more)

### Community 3 - "initMessages"
Cohesion: 0.16
Nodes (28): initMessages(), applyFilter(), closeModal(), dateSep(), esc(), fullTime(), getAvatarGradient(), getLobbyIdSet() (+20 more)

### Community 4 - "clubadmin/routes.py"
Cohesion: 0.14
Nodes (26): api_courts_by_facility(), club_setup(), community(), dashboard(), log_casual_match(), mark_notifications_read(), messages(), notifications() (+18 more)

### Community 5 - "initCommunity"
Cohesion: 0.16
Nodes (24): initCommunity(), bindFeedEvents(), escapeHTML(), filterPosts(), formatPostContent(), handleDeleteComment(), handleDeletePost(), handleLike() (+16 more)

### Community 6 - "PayMongo Integration Guide"
Cohesion: 0.40
Nodes (6): Centralized Collection Multi-Vendor Pattern, PayMongo Checkout Session API, PayMongo Integration Guide, PayMongo Webhook Handler (payment.paid), GCash Reference Payment Pattern, player/payment.html (GCash Payment UI)

### Community 8 - "reservations.py"
Cohesion: 0.18
Nodes (19): api_facility_month_availability(), api_facility_occupancy(), api_my_bookings(), api_reservation_courts(), api_reservation_slots(), api_upgrade_pro(), book_reservation(), cancel_reservation() (+11 more)

### Community 9 - "superadmin/routes.py"
Cohesion: 0.19
Nodes (20): log_audit_action(), Log administrative or critical actions to the database for audit trail. Safe to…, clear_settings_cache(), add_adminstaff(), audit_logs(), community(), dashboard(), facilities() (+12 more)

### Community 10 - "owner/routes.py"
Cohesion: 0.16
Nodes (18): Sends an automated message from sender_id to recipient_id. If a 1-to-1…, Triggers automated chats from the facility owner and assigned staff to the…, send_auto_message(), trigger_booking_autochat(), approve_payment(), decline_payment(), payment_ledger(), route (+10 more)

### Community 11 - "script.js"
Cohesion: 0.18
Nodes (12): getSelectedRole(), nextSignupStep(), nextSlide(), prevSignupStep(), prevSlide(), resetSliderTimer(), selectRoleGrid(), setOwnerFieldsRequired() (+4 more)

### Community 12 - "initTutorials"
Cohesion: 0.28
Nodes (11): initTutorials(), deleteTutorial(), editTutorial(), esc(), levelClass(), levelIcon(), loadTutorials(), openWatch() (+3 more)

### Community 13 - "create_app"
Cohesion: 0.06
Nodes (30): check_feature_limit(), get_tier_limits(), get_user_tier(), app/billing/tiers.py PickleballHub Centralized Subscription & Tier Limits…, Returns the active subscription tier string ('free', 'pro', 'elite') for a…, Return the dictionary of limits for the given role and tier., Checks if a user has permission to perform an action or if they have hit a…, Decorator to protect routes that require a specific minimum subscription tier.… (+22 more)

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
Cohesion: 0.11
Nodes (27): Uploads an avatar file to Supabase storage and returns public URL, or None.…, upload_avatar(), club_detail(), club_payment(), clubs(), join_club(), leave_club(), my_clubs() (+19 more)

### Community 66 - "db.py"
Cohesion: 0.06
Nodes (46): is_jwt_expired(), Thread-safe, request-scoped database helper for Supabase. Provides separation…, Decodes a JWT payload locally to check if it's expired or close to it (5-minute…, _get_dashboard_for_role(), has_role_permission(), Role-based access control decorators for protecting routes., Returns True if user_role is in allowed_roles, or if authorized via logical…, Return the dashboard URL for a given role. (+38 more)

### Community 71 - "auth/routes.py"
Cohesion: 0.07
Nodes (49): api_live_dashboard_stats(), demo_player(), forgot_password(), get_live_dashboard_stats(), get_lobby_ids(), login(), logout(), limit (+41 more)

### Community 82 - "get_db"
Cohesion: 0.10
Nodes (45): change_event_status(), create_event(), delete_event(), edit_event(), event_check_in(), event_participants(), events(), facility_payment() (+37 more)

## Knowledge Gaps
- **49 isolated node(s):** `_spinStyle`, `version`, `builds`, `routes`, `headers` (+44 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 187 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **52 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `require_role()` connect `require_role` to `player/routes.py`, `matchmaker_routes.py`, `db.py`, `clubadmin/routes.py`, `auth/routes.py`, `reservations.py`, `superadmin/routes.py`, `owner/routes.py`, `create_app`, `get_db`?**
  _High betweenness centrality (0.144) - this node is a cross-community bridge._
- **Why does `get_admin_db()` connect `require_role` to `player/routes.py`, `matchmaker_routes.py`, `db.py`, `clubadmin/routes.py`, `auth/routes.py`, `reservations.py`, `superadmin/routes.py`, `owner/routes.py`, `create_app`, `get_db`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Why does `get_db()` connect `get_db` to `require_role`, `player/routes.py`, `db.py`, `matchmaker_routes.py`, `clubadmin/routes.py`, `auth/routes.py`, `reservations.py`, `superadmin/routes.py`, `owner/routes.py`, `create_app`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `initMessages()` (e.g. with `applyFilter()` and `closeModal()`) actually correct?**
  _`initMessages()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `_spinStyle`, `version`, `builds` to the rest of the system?**
  _49 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `require_role` be split into smaller, more focused modules?**
  _Cohesion score 0.09137529137529138 - nodes in this community are weakly interconnected._
- **Should `clubadmin/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._