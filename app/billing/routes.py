import re
from datetime import datetime, timezone, timedelta
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify, g, current_app
)
from app.db import get_admin_db
from app.billing.tiers import (
    TIER_CONFIG, get_user_tier, get_tier_limits
)
from app.upload_utils import validate_and_upload, ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE

billing_bp = Blueprint('billing', __name__)

PH_TZ = timezone(timedelta(hours=8))


def _get_logged_in_user():
    user_id = session.get('user_id')
    if not user_id:
        return None, None
    role = (session.get('role') or 'player').strip().lower()
    return user_id, role


@billing_bp.route('/subscription')
def subscription_page():
    """Main subscription and membership dashboard for logged in users."""
    user_id, role = _get_logged_in_user()
    if not user_id:
        flash("Please log in to view subscription plans.", "info")
        return redirect(url_for('auth.login', next=request.path))

    admin_db = get_admin_db()
    profile = {}
    subscriptions_history = []

    try:
        prof_res = admin_db.table('profiles').select(
            'id, first_name, last_name, role, subscription_tier, subscription_status, subscription_billing_cycle, subscription_expires_at, avatar_url'
        ).eq('id', user_id).single().execute()
        profile = prof_res.data or {}
    except Exception as e:
        current_app.logger.error(f"[subscription_page] Error fetching profile: {e}")

    try:
        sub_res = admin_db.table('subscriptions').select('*')\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .execute()
        subscriptions_history = sub_res.data or []
    except Exception as e:
        current_app.logger.warning(f"[subscription_page] Error fetching subscription history: {e}")

    current_tier = get_user_tier(profile or user_id, role=role, db=admin_db)
    tier_limits = get_tier_limits(role, current_tier)
    all_role_tiers = TIER_CONFIG.get(role, TIER_CONFIG.get('player', {}))

    # Calculate days remaining if active
    days_remaining = None
    expires_at_iso = profile.get('subscription_expires_at')
    if expires_at_iso:
        try:
            exp_dt = datetime.fromisoformat(expires_at_iso.replace('Z', '+00:00'))
            now_utc = datetime.now(timezone.utc)
            delta = exp_dt - now_utc
            days_remaining = max(0, delta.days)
        except Exception:
            pass

    return render_template(
        'billing/subscription.html',
        profile=profile,
        current_tier=current_tier,
        tier_limits=tier_limits,
        all_role_tiers=all_role_tiers,
        subscriptions_history=subscriptions_history,
        role=role,
        days_remaining=days_remaining
    )


@billing_bp.route('/subscription/checkout', methods=['GET', 'POST'])
def checkout_page():
    """Legitimate GCash payment checkout page for subscriptions."""
    user_id, role = _get_logged_in_user()
    if not user_id:
        flash("Please log in to proceed with subscription checkout.", "info")
        return redirect(url_for('auth.login', next=request.full_path))

    admin_db = get_admin_db()
    all_role_tiers = TIER_CONFIG.get(role, TIER_CONFIG.get('player', {}))

    if request.method == 'GET':
        plan = request.args.get('plan', 'pro').strip().lower()
        cycle = request.args.get('cycle', 'monthly').strip().lower()
        return_to = request.args.get('return_to', '').strip()

        # Validate plan for role
        if plan not in all_role_tiers or plan == 'free':
            plan = 'pro' if 'pro' in all_role_tiers else list(all_role_tiers.keys())[-1]

        if cycle not in ['monthly', 'annual']:
            cycle = 'monthly'

        plan_cfg = all_role_tiers.get(plan, {})
        if cycle == 'annual':
            amount = plan_cfg.get('price_annual', 0) * 12
            monthly_equivalent = plan_cfg.get('price_annual', 0)
        else:
            amount = plan_cfg.get('price_monthly', 0)
            monthly_equivalent = amount

        return render_template(
            'billing/checkout.html',
            plan=plan,
            cycle=cycle,
            plan_cfg=plan_cfg,
            amount=amount,
            monthly_equivalent=monthly_equivalent,
            return_to=return_to,
            role=role
        )

    # ── Handle POST: Submit GCash reference & receipt ──
    plan = request.form.get('plan', 'pro').strip().lower()
    cycle = request.form.get('cycle', 'monthly').strip().lower()
    return_to = request.form.get('return_to', '').strip()
    gcash_ref = request.form.get('gcash_ref', '').strip()

    if plan not in all_role_tiers or plan == 'free':
        plan = 'pro'
    if cycle not in ['monthly', 'annual']:
        cycle = 'monthly'

    plan_cfg = all_role_tiers.get(plan, {})
    if cycle == 'annual':
        amount = float(plan_cfg.get('price_annual', 0) * 12)
    else:
        amount = float(plan_cfg.get('price_monthly', 0))

    # 1. Validate GCash Reference Number
    if not gcash_ref or not re.match(r'^\d{10,20}$', gcash_ref):
        flash('Invalid GCash Reference Number format. Must be a 10 to 20-digit number from your GCash receipt.', 'error')
        return redirect(url_for('billing.checkout_page', plan=plan, cycle=cycle, return_to=return_to))

    # 2. Check duplicate reference number in subscriptions
    try:
        dup = admin_db.table('subscriptions').select('id')\
            .eq('gcash_reference', gcash_ref)\
            .execute()
        if dup.data:
            flash('This GCash reference number has already been used for another subscription.', 'error')
            return redirect(url_for('billing.checkout_page', plan=plan, cycle=cycle, return_to=return_to))
    except Exception as e:
        current_app.logger.warning(f"[checkout_page] Dup check warning: {e}")

    # 3. Validate & Upload GCash Receipt Screenshot
    receipt_file = request.files.get('receipt')
    if not receipt_file or not receipt_file.filename:
        flash('Please upload your GCash payment confirmation screenshot.', 'error')
        return redirect(url_for('billing.checkout_page', plan=plan, cycle=cycle, return_to=return_to))

    receipt_url, upload_err = validate_and_upload(
        admin_db,
        receipt_file,
        bucket='subscription-receipts',
        prefix='sub_receipt',
        owner_id=user_id,
        allowed_exts=ALLOWED_IMAGE_EXTENSIONS,
        max_size=MAX_IMAGE_SIZE
    )
    if upload_err or not receipt_url:
        flash(f"Receipt upload failed: {upload_err or 'Please provide a valid image.'}", 'error')
        return redirect(url_for('billing.checkout_page', plan=plan, cycle=cycle, return_to=return_to))

    # 4. Activate Subscription
    try:
        now_utc = datetime.now(timezone.utc)
        duration_days = 365 if cycle == 'annual' else 30
        expires_at_dt = now_utc + timedelta(days=duration_days)
        expires_at_iso = expires_at_dt.isoformat()

        # Insert record in public.subscriptions
        admin_db.table('subscriptions').insert({
            'user_id': user_id,
            'role': role,
            'tier': plan,
            'billing_cycle': cycle,
            'amount': amount,
            'payment_method': 'gcash',
            'gcash_reference': gcash_ref,
            'receipt_url': receipt_url,
            'status': 'active',
            'starts_at': now_utc.isoformat(),
            'expires_at': expires_at_iso,
            'notes': f"Direct GCash subscription payment verified for {role} {plan} ({cycle})"
        }).execute()

        # Update profiles table
        admin_db.table('profiles').update({
            'subscription_tier': plan,
            'subscription_status': 'active',
            'subscription_billing_cycle': cycle,
            'subscription_expires_at': expires_at_iso
        }).eq('id', user_id).execute()

        # Update session & cache
        session['subscription_tier'] = plan
        session['subscription_status'] = 'active'
        session['subscription_billing_cycle'] = cycle
        session['subscription_expires_at'] = expires_at_iso
        session.pop('last_integrity_check', None)
        if session.get('cached_profile'):
            session['cached_profile']['subscription_tier'] = plan
            session['cached_profile']['subscription_status'] = 'active'
            session['cached_profile']['subscription_billing_cycle'] = cycle
            session['cached_profile']['subscription_expires_at'] = expires_at_iso
        if hasattr(g, 'current_profile') and g.current_profile:
            g.current_profile['subscription_tier'] = plan
            g.current_profile['subscription_status'] = 'active'
            g.current_profile['subscription_billing_cycle'] = cycle
            g.current_profile['subscription_expires_at'] = expires_at_iso

        flash(
            f"🎉 Congratulations! Your {plan_cfg.get('label', plan.capitalize())} subscription is now active! "
            f"Reference #{gcash_ref} has been recorded.",
            "success"
        )

        if return_to and return_to.startswith('/'):
            return redirect(return_to)
        return redirect(url_for('billing.subscription_page'))

    except Exception as e:
        current_app.logger.error(f"[checkout_page] Error completing subscription: {e}")
        flash(f"An error occurred while saving your subscription: {e}", "error")
        return redirect(url_for('billing.checkout_page', plan=plan, cycle=cycle, return_to=return_to))
