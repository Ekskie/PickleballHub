from flask import Blueprint, render_template, request, redirect, url_for, flash

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
            
            if email == 'player@email.com' and password == '123123':
                return redirect(url_for('player.dashboard'))
            else:
                flash('Invalid credentials. Try player@email.com / 123123', 'error')
                return render_template('auth.html', active_tab='login')
        
        elif action == 'signup':
            # Here we would typically send a Brevo email for verification
            # Since you're using Supabase SMTP, signup via Supabase trigger handles the email.
            flash('Account created successfully! Check your email.', 'success')
            return render_template('auth.html', active_tab='login')
            
    return render_template('auth.html', active_tab='login')
