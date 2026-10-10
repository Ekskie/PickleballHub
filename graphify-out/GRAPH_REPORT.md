# Graph Report - PickleballHub  (2026-10-10)

## Corpus Check
- 93 files · ~597,488 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: .css 9, .jfif 8, (none) 2)

## Summary
- 688 nodes · 1842 edges · 76 communities (24 shown, 52 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 34 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `60667c74`
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
- reservations.py
- CLAUDE.md
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
- billing/routes.py
- player/routes.py
- create_app
- app/__init__.py
- clubs_routes.py
- validate_and_upload
- db.py
- get_db
- Multi-Role Dashboard Pattern (6 Roles)
- Role-Based Access Control (RBAC)
- notifications Table
- profiles Table (Supabase)
- HTMX Partial Queue Refresh Pattern

## God Nodes (most connected - your core abstractions)
1. `require_role()` - 221 edges
2. `get_db()` - 162 edges
3. `get_admin_db()` - 136 edges
4. `initMessages()` - 30 edges
5. `initCommunity()` - 25 edges
6. `initTutorials()` - 25 edges
7. `validate_and_upload()` - 25 edges
8. `log_audit_action()` - 21 edges
9. `create_app()` - 20 edges
10. `check_court_conflict()` - 17 edges

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

## Communities (76 total, 52 thin omitted)

### Community 0 - "superadmin/routes.py"
Cohesion: 0.09
Nodes (46): log_audit_action(), Log administrative or critical actions to the database for audit trail. Safe to…, clear_landing_cache(), delete_article(), get_article_by_id(), get_articles_db(), get_landing_content(), Returns complete landing page configuration with DB overrides. Cached for 30s… (+38 more)

### Community 1 - "matchmaker_routes.py"
Cohesion: 0.26
Nodes (15): format_date_friendly(), format_time_12h(), get_lobby_display_status(), matchmaker(), matchmaker_create(), matchmaker_delete(), matchmaker_detail(), matchmaker_edit() (+7 more)

### Community 2 - "main/routes.py"
Cohesion: 0.10
Nodes (33): about_us(), api_courts_search(), api_tutorials_delete(), api_tutorials_list(), api_tutorials_save(), api_tutorials_sign_upload(), api_tutorials_upload(), clinics() (+25 more)

### Community 3 - "initMessages"
Cohesion: 0.16
Nodes (28): initMessages(), applyFilter(), closeModal(), dateSep(), esc(), fullTime(), getAvatarGradient(), getLobbyIdSet() (+20 more)

### Community 4 - "clubadmin/routes.py"
Cohesion: 0.09
Nodes (38): get_facility_court_timeline(), Get all courts in facility along with their occupied time blocks on the…, api_courts_by_facility(), club_setup(), community(), dashboard(), log_casual_match(), mark_notifications_read() (+30 more)

### Community 5 - "initCommunity"
Cohesion: 0.16
Nodes (24): initCommunity(), bindFeedEvents(), escapeHTML(), filterPosts(), formatPostContent(), handleDeleteComment(), handleDeletePost(), handleLike() (+16 more)

### Community 6 - "PayMongo Integration Guide"
Cohesion: 0.40
Nodes (6): Centralized Collection Multi-Vendor Pattern, PayMongo Checkout Session API, PayMongo Integration Guide, PayMongo Webhook Handler (payment.paid), GCash Reference Payment Pattern, player/payment.html (GCash Payment UI)

### Community 8 - "reservations.py"
Cohesion: 0.08
Nodes (40): check_court_conflict(), normalize_time_str(), notify_facility_staff_and_owner(), Check if interval [s1, e1) overlaps interval [s2, e2)., Sends in-app notifications to the facility owner and all assigned facility…, Check if a court is already booked or reserved on the given date and time…, Normalize time string to HH:MM:SS for safe lexical and logical comparison., times_overlap() (+32 more)

### Community 9 - "CLAUDE.md"
Cohesion: 0.25
Nodes (6): Architecture, Authentication Flow, Commands, Dependencies, Environment Variables, Project Overview

### Community 10 - "require_role"
Cohesion: 0.07
Nodes (83): change_password(), community(), dashboard(), disputes(), mark_notifications_read(), messages(), notifications(), profile() (+75 more)

### Community 11 - "script.js"
Cohesion: 0.18
Nodes (12): getSelectedRole(), nextSignupStep(), nextSlide(), prevSignupStep(), prevSlide(), resetSliderTimer(), selectRoleGrid(), setOwnerFieldsRequired() (+4 more)

### Community 12 - "initTutorials"
Cohesion: 0.17
Nodes (23): initTutorials(), closeAddModal(), deleteTutorial(), directUploadToSignedUrl(), esc(), extractYoutubeId(), formatFileSize(), getCsrfToken() (+15 more)

### Community 13 - "auth/routes.py"
Cohesion: 0.14
Nodes (24): api_live_dashboard_stats(), demo_player(), forgot_password(), get_live_dashboard_stats(), get_lobby_ids(), login(), logout(), limit (+16 more)

### Community 17 - "vercel.json"
Cohesion: 0.40
Nodes (4): builds, headers, routes, version

### Community 18 - "PayMongo Setup Guide for PickleballHub"
Cohesion: 0.20
Nodes (9): 1. Account Creation and Keys, 2. The Checkout Workflow (Multi-Vendor), 3. Handling Webhooks (Crucial Step), 4. Local Testing (ngrok), code:env (PAYMONGO_PUBLIC_KEY=pk_test_xxxxxxxxxxxxx), code:python (@app.route('/api/webhooks/paymongo', methods=['POST'])), Next Steps for Development, PayMongo Setup Guide for PickleballHub (+1 more)

### Community 19 - "PickleballHub"
Cohesion: 0.12
Nodes (16): logo.png (PickleballHub Logo), Architecture, Authentication Flow, code:block1 (PickleballHub/), code:bash (# Install dependencies), Commands, Dependencies, Environment Variables (+8 more)

### Community 63 - "billing/routes.py"
Cohesion: 0.15
Nodes (18): checkout_page(), _get_logged_in_user(), route, Main subscription and membership dashboard for logged in users., Legitimate GCash payment checkout page for subscriptions., subscription_page(), get_tier_limits(), get_user_tier() (+10 more)

### Community 64 - "player/routes.py"
Cohesion: 0.19
Nodes (16): get_processed_queues(), route, queue(), queue_partial(), Fetch queues for today, process wait times, and auto-complete games 15 mins…, change_password(), compute_player_sports_data(), dashboard() (+8 more)

### Community 65 - "create_app"
Cohesion: 0.17
Nodes (5): create_app(), inject_csrf_token(), inject_platform_settings(), verify_session_integrity(), load_platform_settings()

### Community 66 - "app/__init__.py"
Cohesion: 0.24
Nodes (8): dotenv, flask_limiter, flask_limiter_util, flask_wtf_csrf, httpx, os, supabase, sys

### Community 67 - "clubs_routes.py"
Cohesion: 0.39
Nodes (8): club_detail(), clubs(), join_club(), leave_club(), my_clubs(), route, check_player_memberships_expiry(), Check if any of the player's active memberships has expired and update status.

### Community 68 - "validate_and_upload"
Cohesion: 0.29
Nodes (7): club_payment(), Centralized file upload validation for all storage uploads. Usage: from…, Validate and upload a file to Supabase Storage in one call, with resilient…, Validate a file upload for extension, MIME type, and size. Args: file_obj:…, validate_and_upload(), validate_upload(), uuid

### Community 71 - "db.py"
Cohesion: 0.07
Nodes (42): check_feature_limit(), Checks if a user has permission to perform an action or if they have hit a…, is_jwt_expired(), Thread-safe, request-scoped database helper for Supabase. Provides separation…, Decodes a JWT payload locally to check if it's expired or close to it (5-minute…, _get_dashboard_for_role(), has_role_permission(), Role-based access control decorators for protecting routes. (+34 more)

### Community 82 - "get_db"
Cohesion: 0.10
Nodes (40): get_db(), Get a thread-safe, request-scoped Supabase client. Authenticated with user…, _advance_bracket(), api_courts_by_facility(), approve_event(), bracket_generate(), change_event_status(), create_event() (+32 more)

## Knowledge Gaps
- **49 isolated node(s):** `_spinStyle`, `version`, `builds`, `routes`, `headers` (+44 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 210 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **52 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_admin_db()` connect `require_role` to `superadmin/routes.py`, `create_app`, `app/__init__.py`, `main/routes.py`, `clubadmin/routes.py`, `clubs_routes.py`, `matchmaker_routes.py`, `db.py`, `reservations.py`, `player/routes.py`, `auth/routes.py`, `get_db`, `billing/routes.py`?**
  _High betweenness centrality (0.147) - this node is a cross-community bridge._
- **Why does `require_role()` connect `require_role` to `player/routes.py`, `matchmaker_routes.py`, `superadmin/routes.py`, `clubs_routes.py`, `clubadmin/routes.py`, `validate_and_upload`, `db.py`, `reservations.py`, `get_db`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Why does `get_db()` connect `get_db` to `player/routes.py`, `matchmaker_routes.py`, `superadmin/routes.py`, `clubs_routes.py`, `clubadmin/routes.py`, `validate_and_upload`, `db.py`, `reservations.py`, `require_role`, `auth/routes.py`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `initMessages()` (e.g. with `applyFilter()` and `closeModal()`) actually correct?**
  _`initMessages()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `_spinStyle`, `version`, `builds` to the rest of the system?**
  _49 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `superadmin/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09308510638297872 - nodes in this community are weakly interconnected._
- **Should `main/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09982174688057041 - nodes in this community are weakly interconnected._