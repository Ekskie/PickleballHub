# Graph Report - PickleballHub  (2026-10-14)

## Corpus Check
- 95 files · ~625,160 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: .css 9, .jfif 8, (none) 2)

## Summary
- 721 nodes · 1990 edges · 69 communities (17 shown, 52 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 35 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5e227c4a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- superadmin/routes.py
- clubadmin/routes.py
- main/routes.py
- initMessages
- get_db
- initCommunity
- PayMongo Integration Guide
- Single-Elimination Bracket Algorithm
- create_app
- require_role
- script.js
- initTutorials
- get_user_tier
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
- reservations.py
- db.py
- Multi-Role Dashboard Pattern (6 Roles)
- Role-Based Access Control (RBAC)
- notifications Table
- profiles Table (Supabase)
- HTMX Partial Queue Refresh Pattern

## God Nodes (most connected - your core abstractions)
1. `require_role()` - 230 edges
2. `get_db()` - 168 edges
3. `get_admin_db()` - 141 edges
4. `get_user_tier()` - 30 edges
5. `log_audit_action()` - 30 edges
6. `initMessages()` - 30 edges
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

## Communities (69 total, 52 thin omitted)

### Community 0 - "superadmin/routes.py"
Cohesion: 0.06
Nodes (63): clear_tier_pricing_cache(), Invalidates the in-memory tier pricing cache., Saves new pricing into platform_settings under 'subscription_pricing' key and…, Resets pricing to system defaults by deleting 'subscription_pricing' from…, reset_tier_pricing(), save_tier_pricing(), log_audit_action(), Log administrative or critical actions to the database for audit trail. Safe to… (+55 more)

### Community 1 - "clubadmin/routes.py"
Cohesion: 0.09
Nodes (38): api_courts_by_facility(), club_setup(), community(), dashboard(), log_casual_match(), mark_notifications_read(), messages(), notifications() (+30 more)

### Community 2 - "main/routes.py"
Cohesion: 0.10
Nodes (35): about_us(), api_courts_search(), api_tutorials_delete(), api_tutorials_list(), api_tutorials_save(), api_tutorials_sign_upload(), api_tutorials_upload(), clinics() (+27 more)

### Community 3 - "initMessages"
Cohesion: 0.16
Nodes (28): initMessages(), applyFilter(), closeModal(), dateSep(), esc(), fullTime(), getAvatarGradient(), getLobbyIdSet() (+20 more)

### Community 4 - "get_db"
Cohesion: 0.07
Nodes (61): approve_member(), export_members_csv(), member_details(), members(), route, reject_member(), remove_member(), _advance_bracket() (+53 more)

### Community 5 - "initCommunity"
Cohesion: 0.16
Nodes (24): initCommunity(), bindFeedEvents(), escapeHTML(), filterPosts(), formatPostContent(), handleDeleteComment(), handleDeletePost(), handleLike() (+16 more)

### Community 6 - "PayMongo Integration Guide"
Cohesion: 0.40
Nodes (6): Centralized Collection Multi-Vendor Pattern, PayMongo Checkout Session API, PayMongo Integration Guide, PayMongo Webhook Handler (payment.paid), GCash Reference Payment Pattern, player/payment.html (GCash Payment UI)

### Community 9 - "create_app"
Cohesion: 0.10
Nodes (10): create_app(), inject_csrf_token(), inject_current_user(), verify_session_integrity(), Architecture, Authentication Flow, Commands, Dependencies (+2 more)

### Community 10 - "require_role"
Cohesion: 0.07
Nodes (83): change_password(), community(), dashboard(), disputes(), mark_notifications_read(), messages(), notifications(), profile() (+75 more)

### Community 11 - "script.js"
Cohesion: 0.17
Nodes (15): getSelectedRole(), nextSignupStep(), nextSlide(), prevSignupStep(), prevSlide(), resetSliderTimer(), selectRoleGrid(), setOwnerFieldsRequired() (+7 more)

### Community 12 - "initTutorials"
Cohesion: 0.17
Nodes (23): initTutorials(), closeAddModal(), deleteTutorial(), directUploadToSignedUrl(), esc(), extractYoutubeId(), formatFileSize(), getCsrfToken() (+15 more)

### Community 13 - "get_user_tier"
Cohesion: 0.05
Nodes (69): api_live_dashboard_stats(), demo_player(), forgot_password(), get_live_dashboard_stats(), get_lobby_ids(), _get_plan_info(), login(), logout() (+61 more)

### Community 17 - "vercel.json"
Cohesion: 0.40
Nodes (4): builds, headers, routes, version

### Community 18 - "PayMongo Setup Guide for PickleballHub"
Cohesion: 0.20
Nodes (9): 1. Account Creation and Keys, 2. The Checkout Workflow (Multi-Vendor), 3. Handling Webhooks (Crucial Step), 4. Local Testing (ngrok), code:env (PAYMONGO_PUBLIC_KEY=pk_test_xxxxxxxxxxxxx), code:python (@app.route('/api/webhooks/paymongo', methods=['POST'])), Next Steps for Development, PayMongo Setup Guide for PickleballHub (+1 more)

### Community 19 - "PickleballHub"
Cohesion: 0.12
Nodes (16): logo.png (PickleballHub Logo), Architecture, Authentication Flow, code:block1 (PickleballHub/), code:bash (# Install dependencies), Commands, Dependencies, Environment Variables (+8 more)

### Community 64 - "reservations.py"
Cohesion: 0.09
Nodes (39): check_court_conflict(), get_facility_court_timeline(), normalize_time_str(), notify_facility_staff_and_owner(), Get all courts in facility along with their occupied time blocks on the…, Check if interval [s1, e1) overlaps interval [s2, e2)., Sends in-app notifications to the facility owner and all assigned facility…, Check if a court is already booked or reserved on the given date and time… (+31 more)

### Community 67 - "db.py"
Cohesion: 0.05
Nodes (61): is_jwt_expired(), Thread-safe, request-scoped database helper for Supabase. Provides separation…, Decodes a JWT payload locally to check if it's expired or close to it (5-minute…, _get_dashboard_for_role(), has_role_permission(), Role-based access control decorators for protecting routes., Returns True if user_role is in allowed_roles, or if authorized via logical…, Return the dashboard URL for a given role. (+53 more)

## Knowledge Gaps
- **49 isolated node(s):** `_spinStyle`, `version`, `builds`, `routes`, `headers` (+44 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 222 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **52 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `require_role()` connect `require_role` to `reservations.py`, `clubadmin/routes.py`, `superadmin/routes.py`, `db.py`, `get_db`, `get_user_tier`?**
  _High betweenness centrality (0.144) - this node is a cross-community bridge._
- **Why does `get_admin_db()` connect `require_role` to `reservations.py`, `clubadmin/routes.py`, `superadmin/routes.py`, `db.py`, `get_db`, `main/routes.py`, `create_app`, `get_user_tier`?**
  _High betweenness centrality (0.138) - this node is a cross-community bridge._
- **Why does `get_db()` connect `get_db` to `reservations.py`, `clubadmin/routes.py`, `superadmin/routes.py`, `db.py`, `require_role`, `get_user_tier`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **What connects `_spinStyle`, `version`, `builds` to the rest of the system?**
  _49 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `superadmin/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06277436347673397 - nodes in this community are weakly interconnected._
- **Should `clubadmin/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09291521486643438 - nodes in this community are weakly interconnected._
- **Should `main/routes.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09523809523809523 - nodes in this community are weakly interconnected._