# Graph Report - PickleballHub  (2026-06-22)

## Corpus Check
- 78 files · ~250,679 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 862 nodes · 1300 edges · 106 communities (60 shown, 46 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 23 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `eba1fc2e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 106|Community 106]]

## God Nodes (most connected - your core abstractions)
1. `community()` - 55 edges
2. `get_admin_db()` - 50 edges
3. `get_db()` - 45 edges
4. `get_db()` - 34 edges
5. `get_db()` - 31 edges
6. `tutorials()` - 29 edges
7. `get_db()` - 29 edges
8. `require_role()` - 28 edges
9. `update_match_ratings()` - 19 edges
10. `upload_avatar()` - 17 edges

## Surprising Connections (you probably didn't know these)
- `PickleballHub` --references--> `logo.png (PickleballHub Logo)`  [INFERRED]
  README.md → app/static/images/logo.png
- `GCash Reference Payment Pattern` --conceptually_related_to--> `PayMongo Checkout Session API`  [INFERRED]
  app/player/routes.py → docs/paymongo_setup_guide.md
- `Supabase Auth & Database` --references--> `Supabase Global Client`  [INFERRED]
  README.md → app/__init__.py
- `Supabase Auth & Database` --references--> `Supabase Admin Client (bypasses RLS)`  [INFERRED]
  README.md → app/__init__.py
- `Flask Blueprint Pattern` --references--> `auth Blueprint`  [INFERRED]
  README.md → app/auth/routes.py

## Communities (106 total, 46 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (41): allConversations, capitalise(), chatBackBtn, chatHeader, chatHeaderAvatar, chatHeaderName, chatHeaderRole, chatInputWrap (+33 more)

### Community 1 - "Community 1"
Cohesion: 0.10
Nodes (35): api_reservation_courts(), book_reservation(), cancel_reservation(), club_detail(), club_payment(), clubs(), confirm_payment(), delete_notification() (+27 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (53): allPosts, bindFeedEvents(), closeBanner, closeShare, closeShareModal(), copiedToast, currentAvatarEl, escapeHTML() (+45 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (39): add_court(), add_facility(), add_staff(), _advance_bracket(), api_courts_by_facility(), bracket_generate(), change_event_status(), courts() (+31 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (56): adjust_profile_stats(), elo_to_dupr(), ensure_initial_history(), get_initial_rating(), init_player_rating(), Lazy initialization of a player's profile Elo/DUPR if columns are null., Create a baseline history record if the player has no rating history logs., Linearly map Elo rating to DUPR scale (2.00 to 8.00). (+48 more)

### Community 5 - "Community 5"
Cohesion: 0.13
Nodes (28): addBtn, addForm, addModal, allTutorials, closeModalBtn, closeWatch, closeWatchModal(), countLabel (+20 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (27): court_queues Table, court_reservations Table, courts Table (Supabase), event_registrations Table, facilities Table (Supabase), facility_staff Table, Facilitystaff Dashboard (Live Court Status), Walk-in Registration Route (+19 more)

### Community 7 - "Community 7"
Cohesion: 0.20
Nodes (10): _advance_bracket Helper (Clubadmin), bracket_generate Route (Clubadmin), Club Leaderboard Route, match_score Route (Clubadmin), tournament_matches Table, _advance_bracket Helper, bracket_generate Route, match_score Route (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.20
Nodes (11): auth Blueprint, logo.png (PickleballHub Logo), create_app Factory, main Blueprint (Public Pages), Flask Blueprint Pattern, Flask Web Application, PickleballHub, Session-Based Authentication (+3 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (46): Sends an automated message from sender_id to recipient_id.     If a 1-to-1 conve, Triggers automated chats from the facility owner and assigned staff to the playe, send_auto_message(), trigger_booking_autochat(), get_admin_db(), Get an admin/service-role scoped Supabase client that bypasses Row Level Securit, Get an admin/service-role scoped Supabase client that bypasses Row Level Securit, Uploads an avatar file to Supabase storage and returns public URL, or None. (+38 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (20): create_app(), clear_settings_cache(), get_db_client(), load_platform_settings(), Returns a Supabase client for querying platform_settings.     Prefers the reques, api_courts_search(), clinics(), courts_listing() (+12 more)

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (35): forgot_password Route, resend_verification Route, forgot_password(), get_db(), login(), logout(), Return the correct dashboard redirect for a given role string.     Unknown/lega, Resend the email verification link to the given address. (+27 more)

### Community 13 - "Community 13"
Cohesion: 0.29
Nodes (12): create_comment(), create_like(), create_post(), get_or_create_club(), get_or_create_club_membership(), get_or_create_court(), get_or_create_event(), get_or_create_event_court() (+4 more)

### Community 14 - "Community 14"
Cohesion: 0.18
Nodes (11): approve_member Route, Flask g for Request-scoped Club Data, load_club before_request (g.club), Club Members Management, club_memberships Table, clubs Table, community_comments Table, community_posts Table (+3 more)

### Community 15 - "Community 15"
Cohesion: 0.25
Nodes (8): Facility Verifications (Adminstaff), club_setup Route (Onboarding), Owner Courts CRUD, Owner Facilities CRUD, KYC Document Upload (Owner), Supabase Storage (Images & KYC Docs), KYC Verification Workflow, update_kyc_status (Superadmin)

### Community 17 - "Community 17"
Cohesion: 0.20
Nodes (8): Architecture, Authentication Flow, code:block1 (PickleballHub/), code:bash (# Install dependencies), Commands, Dependencies, Environment Variables, Project Overview

### Community 18 - "Community 18"
Cohesion: 0.20
Nodes (9): 1. Account Creation and Keys, 2. The Checkout Workflow (Multi-Vendor), 3. Handling Webhooks (Crucial Step), 4. Local Testing (ngrok), code:env (PAYMONGO_PUBLIC_KEY=pk_test_xxxxxxxxxxxxx), code:python (@app.route('/api/webhooks/paymongo', methods=['POST'])), Next Steps for Development, PayMongo Setup Guide for PickleballHub (+1 more)

### Community 19 - "Community 19"
Cohesion: 0.20
Nodes (9): Architecture, Authentication Flow, code:block1 (PickleballHub/), code:bash (# Install dependencies), Commands, Dependencies, Environment Variables, PickleballHub (+1 more)

### Community 20 - "Community 20"
Cohesion: 0.40
Nodes (4): builds, headers, routes, version

### Community 21 - "Community 21"
Cohesion: 0.67
Nodes (3): create_event Route (Clubadmin), facility_payment Route (Court Rental Fee), event_courts Table (Many-to-Many)

### Community 22 - "Community 22"
Cohesion: 0.67
Nodes (3): tutorials Table (Supabase), clinics Route, _extract_yt_id (YouTube URL Parser)

### Community 65 - "Community 65"
Cohesion: 0.10
Nodes (21): HTMX Partial Queue Refresh Pattern, get_processed_queues Helper, PH_TZ (Philippine Timezone UTC+8), Queue Monitoring Route, dashboard(), get_processed_queues(), queue(), queue_partial() (+13 more)

### Community 66 - "Community 66"
Cohesion: 0.29
Nodes (7): _get_dashboard_for_role(), has_role_permission(), Role-based access control decorators for protecting routes., Returns True if user_role is in allowed_roles, or if authorized via logical secu, Returns True if user_role is in allowed_roles, or if the user's role     has a h, Return the dashboard URL for a given role., Return the dashboard URL for a given role.

### Community 67 - "Community 67"
Cohesion: 0.18
Nodes (11): api_reservation_slots(), Return booked start_time values for a court on a given date., Return booked start_time values for a court on a given date., Return booked start_time values for a court on a given date., Return booked start_time values for a court on a given date., Return booked start_time values for a court on a given date., Return booked start_time values for a court on a given date., Return booked start_time values for a court on a given date. (+3 more)

### Community 69 - "Community 69"
Cohesion: 0.25
Nodes (8): api_facility_occupancy(), Return all active courts and their bookings for a facility on a given date., Return all active courts and their bookings for a facility on a given date., Return all active courts and their bookings for a facility on a given date., Return all active courts and their bookings for a facility on a given date., Return all active courts and their bookings for a facility on a given date., Return all active courts and their bookings for a facility on a given date., Return all active courts and their bookings for a facility on a given date.

### Community 71 - "Community 71"
Cohesion: 0.06
Nodes (20): generate_safe_filename(), Centralized file upload validation for all storage uploads.  Usage:     from app, Validate and upload a file to Supabase Storage in one call.      Args:         d, Validate a file upload for extension, MIME type, and size.      Args:         fi, Generate a safe, unique filename that never uses client-provided names.      Arg, validate_and_upload(), validate_upload(), add_facility() (+12 more)

### Community 82 - "Community 82"
Cohesion: 0.08
Nodes (35): Adminstaff Dashboard (Support KPIs), Disputes Management, resolve_ticket Route, dashboard(), disputes(), get_db(), mark_notifications_read(), notifications() (+27 more)

### Community 88 - "Community 88"
Cohesion: 0.36
Nodes (9): adminstaff Blueprint, clubadmin Blueprint, _get_dashboard_for_role, require_role Decorator, facilitystaff Blueprint, Multi-Role Dashboard Pattern (6 Roles), owner Blueprint, player Blueprint (+1 more)

### Community 89 - "Community 89"
Cohesion: 0.13
Nodes (3): _advance_bracket(), match_score(), Check current round completion and auto-generate next round or declare champion.

### Community 90 - "Community 90"
Cohesion: 0.25
Nodes (8): login Route, logout Route, _redirect_by_role, Role-Dashboard Routing Map, signup Route, Role-Based Access Control (RBAC), login.html Template, signup.html Template

### Community 91 - "Community 91"
Cohesion: 0.29
Nodes (7): notifications Table, Queue 'You are up next!' Notification, update_queue Route (Facilitystaff), player dashboard Route, unregister_event + Waitlist Promotion, Waitlist Auto-Promotion Logic, player/dashboard.html Template

### Community 92 - "Community 92"
Cohesion: 0.47
Nodes (6): inject_current_user Context Processor, profiles Table (Supabase), Supabase Admin Client (bypasses RLS), Supabase Global Client, Supabase Auth & Database, add_adminstaff Route

### Community 97 - "Community 97"
Cohesion: 0.67
Nodes (3): get_lobby_display_status(), matchmaker(), matchmaker_detail()

### Community 98 - "Community 98"
Cohesion: 0.47
Nodes (5): get_db(), is_jwt_expired(), Thread-safe, request-scoped database helper for Supabase. Provides separation be, Decodes a JWT payload locally to check if it's expired or close to it (5-minute, Get a thread-safe, request-scoped Supabase client.     Authenticated with user a

### Community 99 - "Community 99"
Cohesion: 0.60
Nodes (4): get_processed_queues(), queue(), queue_partial(), Fetch queues for today, process wait times, and auto-complete games 15 mins past

### Community 103 - "Community 103"
Cohesion: 0.22
Nodes (4): Decorator to protect routes by role.     Usage: @require_role('superadmin', 'own, Decorator to protect routes by role, supporting role hierarchies.     Usage: @re, Decorator to protect routes by role, supporting role hierarchies.     Usage: @re, require_role()

## Knowledge Gaps
- **128 isolated node(s):** `version`, `builds`, `routes`, `headers`, `style` (+123 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **46 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `tutorials()` connect `Community 5` to `Community 0`, `Community 1`, `Community 82`?**
  _High betweenness centrality (0.141) - this node is a cross-community bridge._
- **Why does `get_processed_queues Helper` connect `Community 65` to `Community 1`, `Community 6`, `Community 9`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Why does `get_db()` connect `Community 98` to `Community 1`, `Community 3`, `Community 4`, `Community 9`, `Community 10`, `Community 11`, `Community 66`, `Community 70`, `Community 71`, `Community 82`, `Community 89`, `Community 93`, `Community 96`, `Community 99`, `Community 100`, `Community 102`, `Community 103`, `Community 105`, `Community 106`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **What connects `version`, `builds`, `routes` to the rest of the system?**
  _257 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05357142857142857 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.09716599190283401 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.08080808080808081 - nodes in this community are weakly interconnected._