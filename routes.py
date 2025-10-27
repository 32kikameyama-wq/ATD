from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

# ブループリントを作成
main = Blueprint('main', __name__)

@main.route('/')
def index():
    """ホームページ"""
    # ログインしている場合はタスク一覧へリダイレクト
    if current_user.is_authenticated:
        return redirect(url_for('tasks.list_tasks'))
    
    # 未ログインの場合はログイン画面へ
    return redirect(url_for('auth.login'))
