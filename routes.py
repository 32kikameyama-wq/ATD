from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required

# ブループリントを作成
main = Blueprint('main', __name__)

@main.route('/')
def index():
    """ホームページ"""
    # ログインしている場合はダッシュボードへリダイレクト
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    # 未ログインの場合はログイン画面へ
    return redirect(url_for('auth.login'))

@main.route('/dashboard')
@login_required
def dashboard():
    """ダッシュボード"""
    from models import Task
    
    # 本日のタスクを取得（優先順位順）
    today_tasks = Task.query.filter_by(
        user_id=current_user.id, 
        category='today'
    ).order_by(Task.order_index).all()
    
    # 完了済みタスク数
    completed_tasks = Task.query.filter_by(
        user_id=current_user.id,
        category='today',
        completed=True
    ).count()
    
    # 総タスク数
    total_tasks = len(today_tasks)
    
    # 進捗率（パーセンテージ）
    progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    return render_template('dashboard.html', 
                         today_tasks=today_tasks,
                         completed_tasks=completed_tasks,
                         total_tasks=total_tasks,
                         progress_percentage=progress_percentage)

@main.route('/personal-tasks')
@login_required
def personal_tasks():
    """個人タスク管理"""
    return render_template('personal_tasks.html')

@main.route('/team-management')
@login_required
def team_management():
    """チーム管理"""
    return render_template('team_management.html')

@main.route('/mindmap')
@login_required
def mindmap():
    """マインドマップ"""
    return render_template('mindmap.html')

@main.route('/profile')
@login_required
def profile():
    """プロフィール管理"""
    return render_template('profile.html')
