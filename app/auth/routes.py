from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app import supabase

auth_bp = Blueprint('auth', __name__, url_prefix='')

@auth_bp.route('/')
def index():
    return redirect(url_for('auth.auth'))

@auth_bp.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'login':
            email = request.form.get('email')
            password = request.form.get('password')
            
            try:
                if supabase:
                    # Authenticate directly with Supabase
                    response = supabase.auth.sign_in_with_password({
                        "email": email, 
                        "password": password
                    })
                    
                    # Store user ID loosely in session
                    if response.user:
                        session['user_id'] = response.user.id
                        
                    # Currently routing default to player
                    return redirect(url_for('player.dashboard'))
                else:
                    flash('Supabase not configured locally.', 'error')
                    return render_template('auth.html', active_tab='login')
                    
            except Exception as e:
                flash(f"Login Failed: {str(e)}", 'error')
                return render_template('auth.html', active_tab='login')
        
        elif action == 'signup':
            email = request.form.get('email')
            password = request.form.get('password')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            role = request.form.get('role')
            phone = request.form.get('phone')
            
            # Proficiency only applies if the user selected 'player'
            proficiency = request.form.get('proficiency') if role == 'player' else None
            
            try:
                if supabase:
                    # Pass additional form fields securely into the raw user meta data.
                    # Our Supabase SQL trigger will hook into these and insert them into the 'profiles' layer cleanly.
                    response = supabase.auth.sign_up({
                        "email": email, 
                        "password": password,
                        "options": {
                            "data": {
                                "first_name": first_name,
                                "last_name": last_name,
                                "role": role,
                                "proficiency": proficiency,
                                "phone": phone
                            }
                        }
                    })
                    
                    flash('Account created successfully! Please verify your email to log in.', 'success')
                    return render_template('auth.html', active_tab='login')
                else:
                    flash('Supabase not configured locally.', 'error')
                    return render_template('auth.html', active_tab='signup')
                    
            except Exception as e:
                flash(f"Signup Failed: {str(e)}", 'error')
                return render_template('auth.html', active_tab='signup')
                
    return render_template('auth.html', active_tab='login')
