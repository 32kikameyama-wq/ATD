from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from werkzeug.security import check_password_hash

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """ログインページ"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # ユーザー検索
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash('ログイン成功！', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('ユーザー名またはパスワードが間違っています', 'error')
    
    return render_template('auth/login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    """ユーザー登録ページ"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        # バリデーション
        if password != password_confirm:
            flash('パスワードが一致しません', 'error')
            return redirect(url_for('auth.register'))
        
        # ユーザーが既に存在するかチェック
        if User.query.filter_by(username=username).first():
            flash('このユーザー名は既に使用されています', 'error')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('このメールアドレスは既に使用されています', 'error')
            return redirect(url_for('auth.register'))
        
        # 新規ユーザー作成
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('登録が完了しました！ログインしてください', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth.route('/logout')
@login_required
def logout():
    """ログアウト"""
    logout_user()
    flash('ログアウトしました', 'success')
    return redirect(url_for('main.index'))
