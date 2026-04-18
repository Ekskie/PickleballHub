from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import supabase

auth_bp = Blueprint('auth', __name__, url_prefix='')

def _redirect_by_role(role: str):
    """Return the correct dashboard redirect for a given role string."""
    role = (role or 'player').strip().lower()
    if role == 'player':
        return redirect(url_for('player.dashboard'))
    # Future roles: admin, staff, etc.
    return redirect(url_for('player.dashboard'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect already-authenticated users
    if request.method == 'GET' and session.get('user_id'):
        return _redirect_by_role(session.get('role', 'player'))

    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')
        
        try:
            if supabase:
                response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                
                if response.user:
                    user     = response.user
                    meta     = user.user_metadata or {}

                    session['user_id']    = user.id
                    session['email']      = user.email or email or ''
                    session['first_name'] = meta.get('first_name', '')
                    session['last_name']  = meta.get('last_name',  '')
                    session['phone']      = meta.get('phone', '')
                    session['role']       = meta.get('role', 'player') or 'player'

                    return _redirect_by_role(session['role'])

                flash('Login failed: no user returned.', 'error')
                return render_template('login.html')
            else:
                flash('Supabase not configured locally.', 'error')
                return render_template('login.html')
                
        except Exception as e:
            flash(f"Login Failed: {str(e)}", 'error')
            return render_template('login.html')

    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET' and session.get('user_id'):
        return _redirect_by_role(session.get('role', 'player'))

    if request.method == 'POST':
        email      = request.form.get('email')
        password   = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name  = request.form.get('last_name')
        role       = request.form.get('role')
        phone      = request.form.get('phone')
        proficiency = request.form.get('proficiency') if role == 'player' else None
        
        try:
            if supabase:
                supabase.auth.sign_up({
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {
                            "first_name":  first_name,
                            "last_name":   last_name,
                            "role":        role,
                            "proficiency": proficiency,
                            "phone":       phone
                        }
                    }
                })
                flash('Account created! Please verify your email to log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('Supabase not configured locally.', 'error')
                return render_template('signup.html')
                
        except Exception as e:
            flash(f"Signup Failed: {str(e)}", 'error')
            return render_template('signup.html')

    return render_template('signup.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    if supabase:
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
    return redirect(url_for('auth.login'))

