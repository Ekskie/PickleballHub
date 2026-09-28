"""
app/billing/tiers.py
PickleballHub Centralized Subscription & Tier Limits Engine.
Defines monetization rules, role-based limits, paywall checks, and route decorators.
"""

from functools import wraps
from datetime import datetime, timezone, timedelta
from flask import session, flash, redirect, url_for, g, current_app, request
from app.db import get_admin_db

# Philippine Standard Time (UTC+8)
PH_TZ = timezone(timedelta(hours=8))

# ─────────────────────────────────────────────────────────────────────────────
# 1. TIER DEFINITIONS AND OPERATIONAL LIMITS CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
TIER_CONFIG = {
    # ── Facility Owners (B2B SaaS) ──
    'owner': {
        'free': {
            'label': 'Starter Operator',
            'price_monthly': 0,
            'price_annual': 0,
            'max_facilities': 1,
            'max_courts_per_facility': 2,
            'booking_commission_pct': 0.08,  # 8% platform fee
            'advance_booking_days': 7,
            'max_staff': 0,
            'peak_pricing_allowed': False,
            'csv_export_allowed': False,
            'featured_badge': False,
            'featured_top_pin': False,
        },
        'pro': {
            'label': 'Pro Facility Pass',
            'price_monthly': 1299,
            'price_annual': 1049,  # ₱12,588/yr
            'max_facilities': 3,
            'max_courts_per_facility': 8,
            'booking_commission_pct': 0.03,  # Low 3% platform fee
            'advance_booking_days': 30,
            'max_staff': 3,
            'peak_pricing_allowed': True,
            'csv_export_allowed': True,
            'featured_badge': True,  # "Verified Partner" badge
            'featured_top_pin': False,
        },
        'elite': {
            'label': 'Elite Enterprise',
            'price_monthly': 2999,
            'price_annual': 2399,  # ₱28,788/yr
            'max_facilities': 999,
            'max_courts_per_facility': 999,
            'booking_commission_pct': 0.00,  # 0% fee (keep 100%)
            'advance_booking_days': 90,
            'max_staff': 999,
            'peak_pricing_allowed': True,
            'csv_export_allowed': True,
            'featured_badge': True,
            'featured_top_pin': True,  # Homepage Featured Pin
        }
    },

    # ── Club Administrators (Organizers) ──
    'clubadmin': {
        'free': {
            'label': 'Community Organizer',
            'price_monthly': 0,
            'price_annual': 0,
            'max_clubs': 1,
            'max_members_per_club': 25,
            'max_tournament_bracket': 8,
            'monthly_tournaments_limit': 1,
            'advanced_formats_allowed': False,  # Single elim only
            'gcash_entry_fees_allowed': False,
            'roster_export_allowed': False,
        },
        'pro': {
            'label': 'Pro Club Pass',
            'price_monthly': 599,
            'price_annual': 479,  # ₱5,748/yr
            'max_clubs': 5,
            'max_members_per_club': 999999,
            'max_tournament_bracket': 64,
            'monthly_tournaments_limit': 999,
            'advanced_formats_allowed': True,  # Double elim, Round robin, Swiss
            'gcash_entry_fees_allowed': True,
            'roster_export_allowed': True,
        }
    },

    # ── Players (Athletes) ──
    'player': {
        'free': {
            'label': 'Player Membership',
            'price_monthly': 0,
            'price_annual': 0,
            'advance_booking_days': 3,
            'max_active_bookings': 2,
            'convenience_fee_waived': False,  # Standard ₱25 fee
            'convenience_fee_amount': 25.00,
            'priority_queue': False,
            'pro_badge': False,
            'pro_analytics': False,
            'tournament_discount_pct': 0.00,
        },
        'pro': {
            'label': 'Pickleball Pro Pass',
            'price_monthly': 199,
            'price_annual': 149,  # ₱1,788/yr
            'advance_booking_days': 14,
            'max_active_bookings': 999,
            'convenience_fee_waived': True,  # ₱0 fee
            'convenience_fee_amount': 0.00,
            'priority_queue': True,
            'pro_badge': True,  # Gold PRO paddle badge
            'pro_analytics': True,
            'tournament_discount_pct': 0.10,  # 10% off tournaments
        }
    }
}


# ─────────────────────────────────────────────────────────────────────────────
# 2. TIER RETRIEVAL & EXPIRY VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────
def get_user_tier(user_id_or_profile=None, role=None, db=None) -> str:
    """
    Returns the active subscription tier string ('free', 'pro', 'elite')
    for a given user or profile.
    Automatically verifies expiry timestamp against UTC. If expired, defaults to 'free'.
    """
    if not user_id_or_profile:
        user_id_or_profile = session.get('user_id')

    if not user_id_or_profile:
        return 'free'

    profile = None
    if isinstance(user_id_or_profile, dict):
        profile = user_id_or_profile
        # Defensive check: if the passed dictionary forgot to include subscription_tier,
        # fetch the fresh profile rather than wrongly assuming the user is 'free'
        if 'subscription_tier' not in profile and profile.get('id'):
            return get_user_tier(profile['id'], role=role, db=db)
    else:
        # Check cached profile on flask.g or session
        cached = getattr(g, 'current_profile', None)
        if cached and cached.get('id') == user_id_or_profile:
            profile = cached
        elif session.get('cached_profile') and session['cached_profile'].get('id') == user_id_or_profile:
            profile = session['cached_profile']
        else:
            try:
                client = db or get_admin_db()
                if client:
                    resp = client.table('profiles')\
                        .select('subscription_tier, subscription_status, subscription_expires_at, role')\
                        .eq('id', user_id_or_profile).single().execute()
                    profile = resp.data if resp else None
            except Exception as e:
                current_app.logger.warning(f"[get_user_tier] Error fetching tier for {user_id_or_profile}: {e}")

    if not profile:
        # Fallback to session if present
        sess_tier = session.get('subscription_tier')
        if sess_tier in ['pro', 'elite']:
            return sess_tier
        return 'free'

    raw_tier = (profile.get('subscription_tier') or session.get('subscription_tier') or 'free').strip().lower()
    if raw_tier not in ['pro', 'elite']:
        return 'free'

    # Check expiration date
    expires_at = profile.get('subscription_expires_at') or session.get('subscription_expires_at')
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(str(expires_at).replace('Z', '+00:00'))
            now_utc = datetime.now(timezone.utc)
            if now_utc > exp_dt:
                # Expired subscription
                return 'free'
        except Exception:
            pass

    return raw_tier


def get_tier_limits(role: str, tier: str = None) -> dict:
    """Return the dictionary of limits for the given role and tier."""
    role = (role or 'player').strip().lower()
    tier = (tier or 'free').strip().lower()

    role_configs = TIER_CONFIG.get(role, TIER_CONFIG.get('player'))
    return role_configs.get(tier, role_configs.get('free', {}))


# ─────────────────────────────────────────────────────────────────────────────
# 3. FEATURE LIMIT VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────
def check_feature_limit(user_id_or_profile, role: str, feature_name: str,
                        current_count: int = None, target_date=None, db=None) -> dict:
    """
    Checks if a user has permission to perform an action or if they have hit a limit.
    Returns:
    {
        'allowed': bool,
        'limit': int/float/bool,
        'current': int/None,
        'tier': str,
        'role': str,
        'message': str,
        'required_tier': str
    }
    """
    role = (role or 'player').strip().lower()
    tier = get_user_tier(user_id_or_profile, role=role, db=db)
    limits = get_tier_limits(role, tier)

    limit_val = limits.get(feature_name)

    # Default fallback response
    result = {
        'allowed': True,
        'limit': limit_val,
        'current': current_count,
        'tier': tier,
        'role': role,
        'message': '',
        'required_tier': 'pro'
    }

    # ── 1. Numerical Count Limits (Facilities, Courts, Members, etc.) ──
    if feature_name in ['max_facilities', 'max_courts_per_facility', 'max_clubs', 'max_members_per_club', 'max_staff']:
        if limit_val is not None and current_count is not None:
            if current_count >= limit_val:
                result['allowed'] = False
                if feature_name == 'max_facilities':
                    result['message'] = f"You have reached your limit of {limit_val} facility on the {limits.get('label', tier)}. Upgrade to Pro to list up to 3 facilities!"
                elif feature_name == 'max_courts_per_facility':
                    result['message'] = f"You have reached the limit of {limit_val} courts per venue on your current plan. Upgrade to Pro to add up to 8 courts!"
                elif feature_name == 'max_clubs':
                    result['message'] = f"You have reached the limit of {limit_val} active club hub on your plan. Upgrade to Pro Club Pass to manage up to 5 clubs!"
                elif feature_name == 'max_members_per_club':
                    result['message'] = f"This club has reached the maximum of {limit_val} members allowed on the Free Organizer plan."
                elif feature_name == 'max_staff':
                    result['message'] = f"Staff account delegation requires a Pro Facility subscription (up to 3 staff members) or Elite Enterprise."
                return result

    # ── 2. Player Advance Booking Window Limit ──
    elif feature_name == 'advance_booking_days':
        if target_date:
            try:
                if isinstance(target_date, str):
                    target_dt = datetime.strptime(target_date[:10], '%Y-%m-%d').date()
                elif hasattr(target_date, 'date'):
                    target_dt = target_date.date()
                else:
                    target_dt = target_date

                now_ph = datetime.now(PH_TZ).date()
                days_ahead = (target_dt - now_ph).days
                max_days = int(limit_val) if limit_val is not None else 3

                if days_ahead > max_days:
                    result['allowed'] = False
                    result['message'] = (
                        f"Booking for {target_date} is {days_ahead} days ahead. "
                        f"Free players can reserve up to {max_days} days in advance. "
                        "Upgrade to Pro Player Pass to unlock 14-day early access booking!"
                    )
                    return result
            except Exception as e:
                current_app.logger.warning(f"[check_feature_limit] Advance days parse error: {e}")

    # ── 3. Player Active Reservations Cap ──
    elif feature_name == 'max_active_bookings':
        if limit_val is not None and current_count is not None:
            if current_count >= limit_val:
                result['allowed'] = False
                result['message'] = (
                    f"You have reached the maximum of {limit_val} active upcoming bookings on the Free plan. "
                    "Upgrade to Pro Player Pass for unlimited concurrent reservations!"
                )
                return result

    # ── 4. Boolean Capability Flags ──
    elif isinstance(limit_val, bool):
        if not limit_val:
            result['allowed'] = False
            if feature_name == 'peak_pricing_allowed':
                result['message'] = "Peak vs. Off-Peak hourly rate scheduling is available exclusively on Pro and Elite facility plans."
            elif feature_name == 'csv_export_allowed':
                result['message'] = "Financial CSV and analytics exports are unlocked on Pro Facility subscriptions."
            elif feature_name == 'advanced_formats_allowed':
                result['message'] = "Double Elimination, Round Robin, and Swiss bracket engines require a Pro Club Pass."
            elif feature_name == 'gcash_entry_fees_allowed':
                result['message'] = "Automated tournament entry fee collection via GCash requires a Pro Club Pass."
            elif feature_name == 'priority_queue':
                result['message'] = "Priority matchmaker queue speed is a Pro Player privilege."
            else:
                result['message'] = "This feature requires an upgraded subscription."
            return result

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4. SUBSCRIPTION REQUIREMENT ROUTE DECORATOR
# ─────────────────────────────────────────────────────────────────────────────
def require_tier(min_tier: str = 'pro', role: str = None):
    """
    Decorator to protect routes that require a specific minimum subscription tier.
    Usage:
        @owner_bp.route('/analytics/export')
        @require_role('owner')
        @require_tier('pro')
        def export_analytics(): ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                flash('Please log in first.', 'error')
                return redirect(url_for('auth.login'))

            user_role = role or session.get('role', 'player')
            current_tier = get_user_tier(user_id, role=user_role)

            tier_rank = {'free': 0, 'pro': 1, 'elite': 2}
            min_rank = tier_rank.get(min_tier, 1)
            user_rank = tier_rank.get(current_tier, 0)

            if user_rank < min_rank:
                flash(
                    f"This feature requires an active {min_tier.capitalize()} subscription. "
                    "Please upgrade your plan to continue.",
                    'warning'
                )
                # Redirect to appropriate dashboard or pricing section
                if user_role == 'owner':
                    return redirect(url_for('owner.facilities'))
                elif user_role == 'clubadmin':
                    return redirect(url_for('clubadmin.dashboard'))
                else:
                    return redirect(url_for('player.dashboard'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator
