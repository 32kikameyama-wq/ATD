from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import current_user, login_required
from datetime import datetime, timedelta

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
    from models import Task, db, UserPerformance
    from datetime import datetime, timedelta
    
    # パフォーマンスデータを更新
    UserPerformance.update_daily_performance(current_user.id)
    
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
    
    # 今日のパフォーマンスデータを取得
    today_performance = UserPerformance.query.filter_by(
        user_id=current_user.id,
        date=datetime.now().date()
    ).first()
    
    # 過去7日間のパフォーマンスデータ
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)
    
    performance_data = UserPerformance.query.filter(
        UserPerformance.user_id == current_user.id,
        UserPerformance.date >= start_date,
        UserPerformance.date <= end_date
    ).order_by(UserPerformance.date).all()
    
    # 過去7日間のデータを準備
    daily_completion_data = []
    labels = []
    
    for i in range(7):
        date = start_date + timedelta(days=i)
        labels.append(date.strftime('%m/%d'))
        
        # パフォーマンスデータから完了数を取得
        perf_data = next((p for p in performance_data if p.date == date), None)
        daily_completion_data.append(perf_data.tasks_completed if perf_data else 0)
    
    # 優先度別タスク数
    priority_data = {
        'high': Task.query.filter_by(user_id=current_user.id, priority='high').count(),
        'medium': Task.query.filter_by(user_id=current_user.id, priority='medium').count(),
        'low': Task.query.filter_by(user_id=current_user.id, priority='low').count()
    }
    
    # 分類別タスク数
    category_data = {
        'today': Task.query.filter_by(user_id=current_user.id, category='today').count(),
        'tomorrow': Task.query.filter_by(user_id=current_user.id, category='tomorrow').count(),
        'other': Task.query.filter_by(user_id=current_user.id, category='other').count()
    }
    
    return render_template('dashboard.html', 
                         today_tasks=today_tasks,
                         completed_tasks=completed_tasks,
                         total_tasks=total_tasks,
                         progress_percentage=progress_percentage,
                         daily_completion_data=daily_completion_data,
                         labels=labels,
                         priority_data=priority_data,
                         category_data=category_data,
                         today_performance=today_performance,
                         streak_days=today_performance.streak_days if today_performance else 0)

@main.route('/personal-tasks')
@login_required
def personal_tasks():
    """個人タスク管理"""
    return render_template('personal_tasks.html')

@main.route('/team-management')
@login_required
def team_management():
    """チーム管理"""
    from models import Team, TeamMember, TeamTask
    
    # ユーザーが所属するチームを取得
    user_teams = Team.query.join(TeamMember).filter(
        TeamMember.user_id == current_user.id
    ).all()
    
    # チームのタスク数を取得
    team_stats = {}
    for team in user_teams:
        total_tasks = TeamTask.query.filter_by(team_id=team.id).count()
        completed_tasks = TeamTask.query.filter_by(team_id=team.id, completed=True).count()
        team_stats[team.id] = {
            'total': total_tasks,
            'completed': completed_tasks,
            'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        }
    
    return render_template('team_management.html', 
                         user_teams=user_teams,
                         team_stats=team_stats)

@main.route('/team/create', methods=['GET', 'POST'])
@login_required
def create_team():
    """チーム作成"""
    from models import Team, TeamMember, db
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        # バリデーション
        if not name:
            flash('チーム名を入力してください', 'error')
            return render_template('team_create.html')
        
        # 同じ名前のチームが既に存在するかチェック
        existing_team = Team.query.filter_by(name=name).first()
        if existing_team:
            flash('このチーム名は既に使用されています', 'error')
            return render_template('team_create.html')
        
        # チーム作成
        new_team = Team(
            name=name,
            description=description,
            created_by=current_user.id
        )
        
        db.session.add(new_team)
        db.session.flush()  # IDを取得するためにflush
        
        # 作成者をチームの管理者として追加
        admin_member = TeamMember(
            team_id=new_team.id,
            user_id=current_user.id,
            role='admin'
        )
        
        db.session.add(admin_member)
        db.session.commit()
        
        flash('チームを作成しました', 'success')
        return redirect(url_for('main.team_management'))
    
    return render_template('team_create.html')

@main.route('/team/<int:team_id>/add-member', methods=['GET', 'POST'])
@login_required
def add_team_member(team_id):
    """チームメンバー追加"""
    from models import Team, TeamMember, User, db
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id, 
        user_id=current_user.id
    ).first()
    
    if not membership or membership.role != 'admin':
        flash('このチームにメンバーを追加する権限がありません', 'error')
        return redirect(url_for('main.team_management'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        
        # バリデーション
        if not username:
            flash('ユーザー名を入力してください', 'error')
            return render_template('team_add_member.html', team=team)
        
        # ユーザーの存在確認
        user = User.query.filter_by(username=username).first()
        if not user:
            flash('ユーザーが見つかりません', 'error')
            return render_template('team_add_member.html', team=team)
        
        # 既にメンバーかチェック
        existing_member = TeamMember.query.filter_by(
            team_id=team_id,
            user_id=user.id
        ).first()
        
        if existing_member:
            flash('このユーザーは既にチームメンバーです', 'error')
            return render_template('team_add_member.html', team=team)
        
        # メンバー追加
        new_member = TeamMember(
            team_id=team_id,
            user_id=user.id,
            role='member'
        )
        
        db.session.add(new_member)
        db.session.commit()
        
        flash(f'{user.username}をチームに追加しました', 'success')
        return redirect(url_for('main.team_management'))
    
    return render_template('team_add_member.html', team=team)

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

@main.route('/admin')
@login_required
def admin():
    """管理者ページ"""
    from models import User, Task, Team, TeamMember, UserPerformance
    
    # 全ユーザー情報を取得
    all_users = User.query.all()
    
    # ユーザー統計情報
    user_stats = {}
    for user in all_users:
        # タスク統計
        total_tasks = Task.query.filter_by(user_id=user.id).count()
        completed_tasks = Task.query.filter_by(user_id=user.id, completed=True).count()
        
        # チーム参加状況
        team_count = TeamMember.query.filter_by(user_id=user.id).count()
        
        # 最新のパフォーマンス
        latest_performance = UserPerformance.query.filter_by(
            user_id=user.id
        ).order_by(UserPerformance.date.desc()).first()
        
        user_stats[user.id] = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            'team_count': team_count,
            'streak_days': latest_performance.streak_days if latest_performance else 0,
            'last_active': latest_performance.date if latest_performance else None
        }
    
    # システム全体の統計
    total_users = User.query.count()
    total_tasks = Task.query.count()
    total_teams = Team.query.count()
    active_users = UserPerformance.query.filter(
        UserPerformance.date >= datetime.now().date() - timedelta(days=7)
    ).distinct(UserPerformance.user_id).count()
    
    return render_template('admin.html',
                         all_users=all_users,
                         user_stats=user_stats,
                         total_users=total_users,
                         total_tasks=total_tasks,
                         total_teams=total_teams,
                         active_users=active_users)

@main.route('/team-dashboard/<int:team_id>')
@login_required
def team_dashboard(team_id):
    """チームダッシュボード"""
    from models import Team, TeamMember, TeamTask, User
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id, 
        user_id=current_user.id
    ).first()
    
    if not membership:
        flash('このチームにアクセスする権限がありません', 'error')
        return redirect(url_for('main.team_management'))
    
    # チームの本日のタスクを取得
    today_tasks = TeamTask.query.filter_by(
        team_id=team_id,
        category='today'
    ).order_by(TeamTask.order_index).all()
    
    # チームの完了済みタスク数
    completed_tasks = TeamTask.query.filter_by(
        team_id=team_id,
        category='today',
        completed=True
    ).count()
    
    # 総タスク数
    total_tasks = len(today_tasks)
    
    # 進捗率
    progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # チームメンバーを取得
    team_members = User.query.join(TeamMember).filter(
        TeamMember.team_id == team_id
    ).all()
    
    # メンバー別タスク数
    member_stats = {}
    for member in team_members:
        assigned_tasks = TeamTask.query.filter_by(
            team_id=team_id,
            assigned_to=member.id
        ).count()
        completed_assigned = TeamTask.query.filter_by(
            team_id=team_id,
            assigned_to=member.id,
            completed=True
        ).count()
        
        member_stats[member.id] = {
            'assigned': assigned_tasks,
            'completed': completed_assigned,
            'completion_rate': (completed_assigned / assigned_tasks * 100) if assigned_tasks > 0 else 0
        }
    
    return render_template('team_dashboard.html',
                         team=team,
                         today_tasks=today_tasks,
                         completed_tasks=completed_tasks,
                         total_tasks=total_tasks,
                         progress_percentage=progress_percentage,
                         team_members=team_members,
                         member_stats=member_stats)
