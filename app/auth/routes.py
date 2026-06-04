"""
Authentication Routes
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, current_user
from app.auth import auth_bp
from app.models import User
from app import db
from datetime import datetime


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    print("[DEBUG] Login route accessed")  # Debug log
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Tài khoản của bạn đã bị vô hiệu hóa.', 'danger')
                return render_template('auth/login.html')

            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()

            login_user(user, remember=remember)
            flash(f'Chào mừng {user.username}!', 'success')

            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard.index'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """Logout"""
    logout_user()
    flash('Bạn đã đăng xuất thành công.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Register new user (optional - can be disabled in production)"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        # Validation
        if not username or not email or not password:
            flash('Vui lòng điền đầy đủ thông tin.', 'danger')
            return render_template('auth/register.html')

        if password != password_confirm:
            flash('Mật khẩu xác nhận không khớp.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Mật khẩu phải có ít nhất 6 ký tự.', 'danger')
            return render_template('auth/register.html')

        # Check if username exists
        if User.query.filter_by(username=username).first():
            flash('Tên đăng nhập đã tồn tại.', 'danger')
            return render_template('auth/register.html')

        # Check if email exists
        if User.query.filter_by(email=email).first():
            flash('Email đã được sử dụng.', 'danger')
            return render_template('auth/register.html')

        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Đăng ký thành công! Bạn có thể đăng nhập ngay.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/test')
def test():
    """Simple test endpoint"""
    return jsonify({'status': 'OK', 'message': 'Server is working!'})
