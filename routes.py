from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import current_user, login_required
from datetime import datetime, timedelta, date
from models import db

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
    
    # 日次の自動処理（日付切り替え・タスク繰り越し）
    try:
        from daily_processor import process_daily_rollover, get_daily_statistics
        process_daily_rollover(current_user.id)
    except Exception as e:
        # 日次処理エラーは無視（通常の操作に影響しない）
        print(f"Daily rollover error: {e}")
        get_daily_statistics = None
    
    # 本日のタスクを取得（優先順位順）
    today_tasks = Task.query.filter_by(
        user_id=current_user.id, 
        category='today',
        archived=False
    ).order_by(Task.order_index).all()
    
    # 完了済みタスク数
    completed_tasks = Task.query.filter_by(
        user_id=current_user.id,
        category='today',
        completed=True,
        archived=False
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
        'high': Task.query.filter_by(user_id=current_user.id, priority='high', archived=False).count(),
        'medium': Task.query.filter_by(user_id=current_user.id, priority='medium', archived=False).count(),
        'low': Task.query.filter_by(user_id=current_user.id, priority='low', archived=False).count()
    }
    
    # 分類別タスク数
    category_data = {
        'today': Task.query.filter_by(user_id=current_user.id, category='today', archived=False).count(),
        'tomorrow': Task.query.filter_by(user_id=current_user.id, category='tomorrow', archived=False).count(),
        'other': Task.query.filter_by(user_id=current_user.id, category='other', archived=False).count()
    }
    
    # 過去7日間の詳細統計
    if get_daily_statistics:
        daily_stats = get_daily_statistics(current_user.id, days=7)
    else:
        daily_stats = []
    
    # 今日の統計
    today_stats = daily_stats[-1] if daily_stats else {
        'total': 0,
        'completed': 0,
        'completion_rate': 0
    }
    
    # 今日の総作業時間を計算（完了済みタスクのみ）
    today_total_seconds = sum(task.total_seconds for task in today_tasks if task.completed and not task.archived)
    
    # タスク別の作業時間データ（時間帯別ではなく完了タスク別）
    task_time_data = []
    for task in today_tasks:
        if task.completed and not task.archived:
            task_time_data.append({
                'title': task.title,
                'total_seconds': task.total_seconds,
                'formatted_time': task.format_time()
            })
    
    return render_template('dashboard.html', 
                         today_tasks=today_tasks,
                         completed_tasks=completed_tasks,
                         total_tasks=total_tasks,
                         progress_percentage=progress_percentage,
                         today_total_seconds=today_total_seconds,
                         task_time_data=task_time_data,
                         daily_completion_data=daily_completion_data,
                         labels=labels,
                         priority_data=priority_data,
                         category_data=category_data,
                         today_performance=today_performance,
                         streak_days=today_performance.streak_days if today_performance else 0,
                         daily_stats=daily_stats,
                         today_stats=today_stats)

@main.route('/personal-tasks')
@login_required
def personal_tasks():
    """個人タスク管理"""
    return render_template('personal_tasks.html')

@main.route('/notifications')
@login_required
def notifications():
    """通知一覧"""
    from models import Notification
    from datetime import datetime
    
    # 未読通知数を取得
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).count()
    
    # 通知一覧を取得（新しい順）
    all_notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    
    return render_template('notifications.html',
                         notifications=all_notifications,
                         unread_count=unread_count)

@main.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """通知を既読にする"""
    from models import Notification
    
    notification = Notification.query.get_or_404(notification_id)
    
    # 自分の通知か確認
    if notification.user_id != current_user.id:
        flash('この通知を変更する権限がありません', 'error')
        return redirect(url_for('main.notifications'))
    
    notification.read = True
    db.session.commit()
    
    return jsonify({'success': True})

@main.route('/task-templates')
@login_required
def task_templates():
    """タスクテンプレート一覧"""
    from models import TaskTemplate
    templates = TaskTemplate.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(TaskTemplate.created_at.desc()).all()
    return render_template('task_templates/list.html', templates=templates)

@main.route('/task-templates/create', methods=['GET', 'POST'])
@login_required
def create_task_template():
    """タスクテンプレート作成"""
    from models import TaskTemplate, db
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority', 'medium')
        category = request.form.get('category', 'today')
        repeat_type = request.form.get('repeat_type', 'none')
        
        if not title:
            flash('タイトルを入力してください', 'error')
            return render_template('task_templates/create.html')
        
        new_template = TaskTemplate(
            title=title,
            description=description,
            priority=priority,
            category=category,
            repeat_type=repeat_type,
            user_id=current_user.id
        )
        
        db.session.add(new_template)
        db.session.commit()
        
        flash('テンプレートを作成しました', 'success')
        return redirect(url_for('main.task_templates'))
    
    return render_template('task_templates/create.html')

@main.route('/task-templates/<int:template_id>/generate', methods=['POST'])
@login_required
def generate_task_from_template(template_id):
    """テンプレートからタスクを生成"""
    from models import TaskTemplate, Task, db
    from datetime import datetime
    
    template = TaskTemplate.query.get_or_404(template_id)
    if template.user_id != current_user.id:
        flash('このテンプレートを変更する権限がありません', 'error')
        return redirect(url_for('main.task_templates'))
    
    # 日付の指定があれば使用、なければ今日
    target_date_str = request.form.get('target_date')
    if target_date_str:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    else:
        target_date = datetime.now().date()
    
    # テンプレートからタスク作成
    new_task = template.create_task_from_template(target_date)
    db.session.add(new_task)
    db.session.commit()
    
    flash(f'テンプレートからタスクを作成しました', 'success')
    return redirect(url_for('tasks.list_tasks'))

@main.route('/calendar')
@login_required
def calendar():
    """カレンダー表示"""
    from models import Task, TaskTemplate
    from datetime import datetime, timedelta
    import calendar as cal
    
    # 表示する月の取得
    year = request.args.get('year', None, type=int)
    month = request.args.get('month', None, type=int)
    
    now = datetime.now()
    if not year or not month:
        year = now.year
        month = now.month
    
    # 月の最初の日と最後の日
    first_day = datetime(year, month, 1).date()
    last_day_num = cal.monthrange(year, month)[1]
    last_day = datetime(year, month, last_day_num).date()
    
    # カレンダーの最初と最後の日（前後の月の分も含める）
    first_weekday = first_day.weekday()
    calendar_start = first_day - timedelta(days=first_weekday)
    
    last_weekday = last_day.weekday()
    calendar_end = last_day + timedelta(days=(6 - last_weekday))
    
    # 表示範囲内のタスクを取得
    all_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.start_date >= calendar_start,
        Task.start_date <= calendar_end,
        Task.archived == False
    ).all()
    
    # 日付ごとにタスクを整理
    tasks_by_date = {}
    for task in all_tasks:
        date_key = task.start_date.strftime('%Y-%m-%d')
        if date_key not in tasks_by_date:
            tasks_by_date[date_key] = []
        tasks_by_date[date_key].append(task)
    
    # カレンダー表示用の日付リストを生成
    calendar_dates = []
    current_date = calendar_start
    while current_date <= calendar_end:
        calendar_dates.append(current_date)
        current_date += timedelta(days=1)
    
    # テンプレート一覧も取得
    templates = TaskTemplate.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(TaskTemplate.created_at.desc()).all()
    
    # 前後の月のリンク
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    
    return render_template('calendar.html',
                         year=year,
                         month=month,
                         now=now,
                         first_day=first_day,
                         last_day=last_day,
                         calendar_start=calendar_start,
                         calendar_end=calendar_end,
                         calendar_dates=calendar_dates,
                         tasks_by_date=tasks_by_date,
                         templates=templates,
                         prev_year=prev_year,
                         prev_month=prev_month,
                         next_year=next_year,
                         next_month=next_month)

@main.route('/daily-report')
@login_required
def daily_report():
    """日報レポート"""
    from models import Task, UserPerformance
    from datetime import datetime, timedelta
    from daily_processor import get_daily_statistics
    
    # 今日の日付
    today = datetime.now().date()
    
    # 今日のタスク統計
    today_stats = get_daily_statistics(current_user.id, days=1)[0] if get_daily_statistics(current_user.id, days=1) else {
        'total': 0,
        'completed': 0,
        'completion_rate': 0
    }
    
    # 過去7日間の統計
    weekly_stats = get_daily_statistics(current_user.id, days=7)
    
    # 過去30日間の統計（月間平均用）
    monthly_stats = get_daily_statistics(current_user.id, days=30)
    
    # 今日のタスク一覧
    today_tasks_list = Task.query.filter(
        Task.user_id == current_user.id,
        Task.category == 'today',
        Task.archived == False
    ).order_by(Task.priority.desc(), Task.order_index).all()
    
    # 完了率の平均
    avg_completion = sum(s['completion_rate'] for s in weekly_stats) / len(weekly_stats) if weekly_stats else 0
    
    # 月間平均完了率
    monthly_avg_completion = sum(s['completion_rate'] for s in monthly_stats) / len(monthly_stats) if monthly_stats else 0
    
    # 連続記録
    from models import UserPerformance
    latest_perf = UserPerformance.query.filter_by(
        user_id=current_user.id
    ).order_by(UserPerformance.date.desc()).first()
    streak = latest_perf.streak_days if latest_perf else 0
    
    # 計画達成状況の判定（目標は80%）
    target_completion_rate = 80.0
    today_on_target = today_stats['completion_rate'] >= target_completion_rate
    weekly_on_target = avg_completion >= target_completion_rate
    monthly_on_target = monthly_avg_completion >= target_completion_rate
    
    # 今日の総作業時間を計算（完了済みタスクのみ）
    today_total_seconds = sum(task.total_seconds for task in today_tasks_list if task.completed and not task.archived)
    
    return render_template('daily_report.html',
                         today=today,
                         today_stats=today_stats,
                         weekly_stats=weekly_stats,
                         today_tasks=today_tasks_list,
                         avg_completion=round(avg_completion, 1),
                         monthly_avg_completion=round(monthly_avg_completion, 1),
                         streak=streak,
                         today_on_target=today_on_target,
                         weekly_on_target=weekly_on_target,
                         monthly_on_target=monthly_on_target,
                         target_completion_rate=target_completion_rate,
                         today_total_seconds=today_total_seconds)

@main.route('/team-management')
@login_required
def team_management():
    """チーム管理"""
    from models import Team, TeamMember, TeamTask
    
    # ユーザーが所属するチームを取得
    user_teams = Team.query.join(TeamMember).filter(
        TeamMember.user_id == current_user.id
    ).all()
    
    # チームのタスク数とメンバー数を取得
    team_stats = {}
    for team in user_teams:
        total_tasks = TeamTask.query.filter_by(team_id=team.id).count()
        completed_tasks = TeamTask.query.filter_by(team_id=team.id, completed=True).count()
        
        # メンバー数と管理者権限をチェック
        member_count = TeamMember.query.filter_by(team_id=team.id).count()
        user_membership = TeamMember.query.filter_by(
            team_id=team.id, 
            user_id=current_user.id
        ).first()
        
        # チーム管理者かシステム管理者かをチェック
        is_team_admin = user_membership and user_membership.role == 'admin'
        is_system_admin = current_user.is_admin
        
        team_stats[team.id] = {
            'total': total_tasks,
            'completed': completed_tasks,
            'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            'member_count': member_count,
            'is_admin': is_team_admin or is_system_admin
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

@main.route('/team/<int:team_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_team(team_id):
    """チーム編集"""
    from models import Team, TeamMember, User, db
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id, 
        user_id=current_user.id
    ).first()
    
    # チーム管理者またはシステム管理者かチェック
    is_team_admin = membership and membership.role == 'admin'
    is_system_admin = current_user.is_admin
    
    if not (is_team_admin or is_system_admin):
        flash('このチームを編集する権限がありません', 'error')
        return redirect(url_for('main.team_management'))
    
    if request.method == 'POST':
        # チーム情報の更新
        team.name = request.form.get('name')
        team.description = request.form.get('description')
        db.session.commit()
        
        flash('チーム情報を更新しました', 'success')
        return redirect(url_for('main.team_management'))
    
    # メンバー一覧を取得
    members = TeamMember.query.filter_by(team_id=team_id).all()
    member_users = []
    for member in members:
        user = User.query.get(member.user_id)
        if user:
            member_users.append({
                'user': user,
                'role': member.role,
                'joined_at': member.joined_at
            })
    
    # 全ユーザーを取得（メンバー追加用）
    all_users = User.query.all()
    
    return render_template('team_edit.html',
                         team=team,
                         members=member_users,
                         all_users=all_users,
                         current_user_membership=membership)

@main.route('/team/<int:team_id>/member/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
def toggle_team_member_admin(team_id, user_id):
    """チームメンバーの管理者権限を切り替え"""
    from models import Team, TeamMember
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id, 
        user_id=current_user.id
    ).first()
    
    # チーム管理者またはシステム管理者かチェック
    is_team_admin = membership and membership.role == 'admin'
    is_system_admin = current_user.is_admin
    
    if not (is_team_admin or is_system_admin):
        return jsonify({'success': False, 'message': '権限がありません'}), 403
    
    # 対象メンバーの権限を変更
    target_member = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=user_id
    ).first_or_404()
    
    # トグル
    target_member.role = 'admin' if target_member.role == 'member' else 'member'
    db.session.commit()
    
    return jsonify({'success': True, 'message': '権限を更新しました'})

@main.route('/team/<int:team_id>/member/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_team_member(team_id, user_id):
    """チームメンバーを削除"""
    from models import Team, TeamMember
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id, 
        user_id=current_user.id
    ).first()
    
    # チーム管理者またはシステム管理者かチェック
    is_team_admin = membership and membership.role == 'admin'
    is_system_admin = current_user.is_admin
    
    if not (is_team_admin or is_system_admin):
        return jsonify({'success': False, 'message': '権限がありません'}), 403
    
    # 自分自身は削除できない
    if user_id == current_user.id:
        return jsonify({'success': False, 'message': '自分自身を削除することはできません'}), 400
    
    # メンバーを削除
    target_member = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=user_id
    ).first_or_404()
    
    db.session.delete(target_member)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'メンバーを削除しました'})

@main.route('/team/<int:team_id>/members')
@login_required
def get_team_members(team_id):
    """チームメンバー一覧を取得（API）"""
    from models import Team, TeamMember, User, Task
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id, 
        user_id=current_user.id
    ).first()
    
    if not membership:
        return jsonify({'success': False, 'message': 'このチームにアクセスする権限がありません'}), 403
    
    # メンバー一覧を取得
    members = TeamMember.query.filter_by(team_id=team_id).all()
    member_data = []
    
    for member in members:
        user = User.query.get(member.user_id)
        if user:
            # 個人タスクの統計
            personal_tasks = Task.query.filter_by(user_id=user.id, archived=False).all()
            total_personal = len(personal_tasks)
            completed_personal = sum(1 for t in personal_tasks if t.completed)
            completion_rate = (completed_personal / total_personal * 100) if total_personal > 0 else 0
            
            member_data.append({
                'user_id': user.id,
                'username': user.username,
                'display_name': user.display_name if hasattr(user, 'display_name') else None,
                'role': member.role,
                'total_tasks': total_personal,
                'completion_rate': round(completion_rate, 1)
            })
    
    return jsonify({'success': True, 'members': member_data})

@main.route('/member/<int:user_id>/detail')
@login_required
def member_detail(user_id):
    """メンバー詳細ページ"""
    from models import User, Task, TeamMember, Team, TeamTask, MindmapNode
    from datetime import datetime
    
    # 対象ユーザーを取得
    target_user = User.query.get_or_404(user_id)
    
    # チームIDを取得（クエリパラメータから）
    team_id = request.args.get('team_id', type=int)
    
    # チームメンバーかどうかチェック（team_idがある場合）
    if team_id:
        team = Team.query.get_or_404(team_id)
        membership = TeamMember.query.filter_by(
            team_id=team_id, 
            user_id=current_user.id
        ).first()
        
        if not membership:
            flash('このチームにアクセスする権限がありません', 'error')
            return redirect(url_for('main.team_management'))
        
        team_name = team.name
    else:
        team_name = None
    
    # 個人タスクを取得
    all_tasks = Task.query.filter_by(user_id=user_id, archived=False).all()
    
    # 分類別にタスクを整理
    today_tasks = [t for t in all_tasks if t.category == 'today']
    tomorrow_tasks = [t for t in all_tasks if t.category == 'tomorrow']
    other_tasks = [t for t in all_tasks if t.category == 'other']
    
    # 完了率の計算
    total_tasks = len(all_tasks)
    completed_tasks = sum(1 for t in all_tasks if t.completed)
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # チームタスクを取得（該当チームから割り当てられたタスク）
    team_tasks = []
    if team_id:
        team_task_ids = []
        for task in all_tasks:
            if task.title.startswith('【'):
                team_task_ids.append(task.id)
        
        team_tasks = [t for t in all_tasks if t.id in team_task_ids]
    
    # マインドマップノードを取得
    # TODO: マインドマップの実装に応じて追加
    
    return render_template('member_detail.html',
                         target_user=target_user,
                         team_name=team_name,
                         today_tasks=today_tasks,
                         tomorrow_tasks=tomorrow_tasks,
                         other_tasks=other_tasks,
                         team_tasks=team_tasks,
                         total_tasks=total_tasks,
                         completed_tasks=completed_tasks,
                         completion_rate=completion_rate)

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
    """個人マインドマップ"""
    from models import Mindmap
    
    # URLパラメータからマインドマップIDを取得
    mindmap_id = request.args.get('mindmap_id', type=int)
    
    # 個人マインドマップ一覧を取得（日付順）
    all_mindmaps = Mindmap.query.filter_by(user_id=current_user.id).order_by(Mindmap.date.desc(), Mindmap.created_at.desc()).all()
    
    # 選択中のマインドマップを取得
    current_mindmap = None
    if mindmap_id:
        current_mindmap = Mindmap.query.filter_by(id=mindmap_id, user_id=current_user.id).first()
    elif all_mindmaps:
        # デフォルトで最新のものを表示
        current_mindmap = all_mindmaps[0]
    
    return render_template('mindmap.html', 
                         all_mindmaps=all_mindmaps,
                         current_mindmap=current_mindmap)

@main.route('/team-mindmap')
@login_required
def team_mindmap():
    """チーム目標マインドマップ"""
    from models import Team, TeamMember
    
    # ユーザーが所属しているチームを取得
    user_teams = Team.query.join(TeamMember).filter(
        TeamMember.user_id == current_user.id
    ).all()
    
    return render_template('team_mindmap.html', teams=user_teams)

@main.route('/team-tasks')
@login_required
def team_tasks():
    """チームタスク管理"""
    from models import Team, TeamMember, TeamTask, Task, User, TaskAssignee
    
    # ユーザーが所属しているチームを取得
    user_teams = Team.query.join(TeamMember).filter(
        TeamMember.user_id == current_user.id
    ).all()
    
    # チームIDをクエリパラメータから取得
    team_id = request.args.get('team_id', type=int)
    user_id = request.args.get('user_id', type=int)
    
    # 選択されたチームの情報
    selected_team = None
    selected_user = None
    assigned_tasks = []
    
    if team_id:
        selected_team = Team.query.get_or_404(team_id)
        
        # そのチームのメンバーかチェック
        membership = TeamMember.query.filter_by(
            team_id=team_id,
            user_id=current_user.id
        ).first()
        
        if not membership:
            flash('このチームにアクセスする権限がありません', 'error')
            return redirect(url_for('main.team_tasks'))
        
        # ユーザーIDが指定されている場合
        if user_id:
            selected_user = User.query.get_or_404(user_id)
            
            # そのユーザーがチームメンバーかチェック
            user_membership = TeamMember.query.filter_by(
                team_id=team_id,
                user_id=user_id
            ).first()
            
            if not user_membership:
                flash('指定されたユーザーはこのチームのメンバーではありません', 'error')
                return redirect(url_for('main.team_tasks', team_id=team_id))
            
            # TaskAssigneeからそのユーザーに割り当てられたチームタスクを取得
            task_assignees = TaskAssignee.query.filter_by(user_id=user_id).all()
            
            # チームタスクから対応する個人タスクを取得
            for task_assignee in task_assignees:
                team_task = TeamTask.query.get(task_assignee.team_task_id)
                if team_task and team_task.team_id == team_id:
                    personal_task = Task.query.filter_by(
                        team_task_id=team_task.id,
                        user_id=user_id
                    ).first()
                    assigned_tasks.append({
                        'team_task': team_task,
                        'personal_task': personal_task,
                        'node': team_task.parent_node  # マップカード（ノード）情報
                    })
    
    # チームの全メンバーを取得
    team_members = []
    if selected_team:
        members = TeamMember.query.filter_by(team_id=selected_team.id).all()
        for member in members:
            user = User.query.get(member.user_id)
            if user:
                team_members.append({
                    'user': user,
                    'role': member.role
                })
    
    return render_template('team_tasks.html',
                         teams=user_teams,
                         selected_team=selected_team,
                         selected_user=selected_user,
                         assigned_tasks=assigned_tasks,
                         team_members=team_members)

@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """プロフィール管理"""
    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        bio = request.form.get('bio', '').strip()
        
        # プロフィール情報を更新
        if display_name:
            current_user.display_name = display_name
        if bio:
            current_user.bio = bio
        
        db.session.commit()
        flash('プロフィールを更新しました', 'success')
        return redirect(url_for('main.profile'))
    
    # タスク統計を取得
    from models import Task
    completed_count = Task.query.filter_by(user_id=current_user.id, completed=True, archived=False).count()
    in_progress_count = Task.query.filter_by(user_id=current_user.id, completed=False, archived=False).count()
    
    # 完了率を計算
    total_tasks = Task.query.filter_by(user_id=current_user.id, archived=False).count()
    completion_rate = (completed_count / total_tasks * 100) if total_tasks > 0 else 0
    
    return render_template('profile.html',
                         completed_count=completed_count,
                         in_progress_count=in_progress_count,
                         completion_rate=round(completion_rate, 1))

@main.route('/admin')
@login_required
def admin():
    """管理者ページ"""
    from models import User, Task, Team, TeamMember, UserPerformance
    
    # 管理者権限チェック
    if not current_user.is_admin:
        flash('管理者権限が必要です', 'error')
        return redirect(url_for('main.dashboard'))
    
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

@main.route('/team-task-detail/<int:team_id>/node/<int:node_id>')
@login_required
def team_task_detail(team_id, node_id):
    """チームタスク詳細ページ"""
    from models import Team, TeamMember, TeamTask, MindmapNode, User, TaskAssignee
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id, 
        user_id=current_user.id
    ).first()
    
    if not membership:
        flash('このチームにアクセスする権限がありません', 'error')
        return redirect(url_for('main.team_management'))
    
    # ノードの取得
    node = MindmapNode.query.get_or_404(node_id)
    
    # このノード（カード）配下のタスクを取得
    tasks = TeamTask.query.filter_by(parent_node_id=node_id).order_by(TeamTask.created_at.desc()).all()
    
    # 各タスクのTaskAssigneeを取得
    task_assignees_map = {}
    for task in tasks:
        assignees = TaskAssignee.query.filter_by(team_task_id=task.id).all()
        task_assignees_map[task.id] = assignees
    
    # チームメンバーを取得
    members = User.query.join(TeamMember).filter(
        TeamMember.team_id == team_id
    ).all()
    
    return render_template('team_task_detail.html',
                         team=team,
                         node=node,
                         tasks=tasks,
                         members=members,
                         task_assignees_map=task_assignees_map)

@main.route('/team-task-detail/<int:team_id>/node/<int:node_id>/add-task', methods=['POST'])
@login_required
def add_team_task_to_node(team_id, node_id):
    """ノードにタスクを追加"""
    from models import Team, TeamMember, TeamTask, MindmapNode
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id, 
        user_id=current_user.id
    ).first()
    
    if not membership:
        flash('このチームにアクセスする権限がありません', 'error')
        return redirect(url_for('main.team_management'))
    
    # ノードの取得
    node = MindmapNode.query.get_or_404(node_id)
    
    # タスク作成
    title = request.form.get('title')
    description = request.form.get('description', '')
    due_date_str = request.form.get('due_date')
    priority = request.form.get('priority', 'medium')
    assigned_to_values = request.form.getlist('assigned_to')  # 複数選択対応
    
    # 完了予定日の処理
    due_date_obj = None
    if due_date_str:
        try:
            due_date_obj = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # 担当者の処理（複数選択）
    assigned_to = None
    if assigned_to_values:
        try:
            assigned_to = int(assigned_to_values[0]) if assigned_to_values else None  # 最初の担当者を使用
        except ValueError:
            pass
    
    team_task = TeamTask(
        team_id=team_id,
        title=title,
        description=description,
        due_date=due_date_obj,
        priority=priority,
        created_by=current_user.id,
        parent_node_id=node_id,  # カード（ノード）配下のタスクとして紐付け
        assigned_to=assigned_to
    )
    
    db.session.add(team_task)
    db.session.flush()  # IDを取得するため
    
    # 選択された全ての担当者に対してTaskAssignee、個人タスクと通知を作成
    if assigned_to_values:
        from models import Task, Notification, TaskAssignee
        for assignee_id_str in assigned_to_values:
            try:
                assignee_id = int(assignee_id_str)
                
                # TaskAssigneeを作成
                task_assignee = TaskAssignee(
                    team_task_id=team_task.id,
                    user_id=assignee_id,
                    completed=False
                )
                db.session.add(task_assignee)
                
                # 個人タスクを作成
                personal_task = Task(
                    user_id=assignee_id,
                    title=f'【{team.name}】{title}',
                    description=description if description else None,
                    start_date=due_date_obj,
                    end_date=due_date_obj,
                    priority=priority,
                    category='other',
                    team_task_id=team_task.id
                )
                db.session.add(personal_task)
                db.session.flush()
                
                # 通知を作成
                notification = Notification(
                    user_id=assignee_id,
                    title='チームタスクが割り当てられました',
                    message=f'チーム「{team.name}」からタスク「{title}」が割り当てられました。',
                    notification_type='info',
                    related_team_id=team_id,
                    related_task_id=personal_task.id
                )
                db.session.add(notification)
            except ValueError:
                pass
    
    db.session.commit()
    
    flash('タスクを追加しました', 'success')
    return redirect(url_for('main.team_task_detail', team_id=team_id, node_id=node_id))

@main.route('/team-task-detail/<int:team_id>/node/<int:node_id>/delete-task/<int:task_id>', methods=['POST'])
@login_required
def delete_team_task_from_node(team_id, node_id, task_id):
    """ノードからタスクを削除"""
    from models import Team, TeamMember, TeamTask, MindmapNode, Task, Mindmap, TaskAssignee
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user.id
    ).first()
    
    if not membership:
        return jsonify({'success': False, 'message': 'このチームにアクセスする権限がありません'}), 403
    
    # タスクの取得
    task = TeamTask.query.get_or_404(task_id)
    
    # ノードに紐づいているか確認
    if task.parent_node_id != node_id:
        return jsonify({'success': False, 'message': 'タスクがこのノードに紐づいていません'}), 400
    
    # TaskAssigneeを削除
    task_assignees = TaskAssignee.query.filter_by(team_task_id=task.id).all()
    for assignee in task_assignees:
        db.session.delete(assignee)
    
    # 関連する個人タスクを削除
    personal_tasks = Task.query.filter_by(team_task_id=task.id).all()
    for personal_task in personal_tasks:
        db.session.delete(personal_task)
    
    # 関連する子ノードを削除
    mindmap_obj = Mindmap.query.filter_by(team_id=team_id).first()
    if mindmap_obj:
        child_nodes = MindmapNode.query.filter_by(
            mindmap_id=mindmap_obj.id,
            team_task_id=task.id
        ).all()
        for child_node in child_nodes:
            db.session.delete(child_node)
    
    # チームタスクを削除
    db.session.delete(task)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'タスクを削除しました'})

@main.route('/team-task-detail/<int:team_id>/node/<int:node_id>/task-info/<int:task_id>')
@login_required
def get_task_info(team_id, node_id, task_id):
    """タスク情報取得API"""
    from models import Team, TeamMember, TeamTask, TaskAssignee, User
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user.id
    ).first()
    
    if not membership:
        return jsonify({'success': False, 'message': 'このチームにアクセスする権限がありません'}), 403
    
    # タスクの取得
    task = TeamTask.query.get_or_404(task_id)
    
    # ノードに紐づいているか確認
    if task.parent_node_id != node_id:
        return jsonify({'success': False, 'message': 'タスクがこのノードに紐づいていません'}), 400
    
    # TaskAssigneeを取得
    assignees = TaskAssignee.query.filter_by(team_task_id=task.id).all()
    assignees_data = []
    for assignee in assignees:
        user = User.query.get(assignee.user_id)
        if user:
            assignees_data.append({
                'user_id': user.id,
                'username': user.username,
                'display_name': user.display_name if hasattr(user, 'display_name') else None,
                'completed': assignee.completed,
                'completed_at': assignee.completed_at.isoformat() if assignee.completed_at else None
            })
    
    task_data = {
        'title': task.title,
        'description': task.description,
        'priority': task.priority,
        'due_date': task.due_date.isoformat() if task.due_date else None
    }
    
    completion_rate = task.calculate_completion_rate()
    
    return jsonify({
        'success': True,
        'task': task_data,
        'assignees': assignees_data,
        'completion_rate': completion_rate
    })

@main.route('/team-task-detail/<int:team_id>/node/<int:node_id>/edit-task/<int:task_id>', methods=['POST'])
@login_required
def edit_team_task(team_id, node_id, task_id):
    """タスク編集API"""
    from models import Team, TeamMember, TeamTask, TaskAssignee, Task, Notification
    from datetime import datetime
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user.id
    ).first()
    
    if not membership:
        return jsonify({'success': False, 'message': 'このチームにアクセスする権限がありません'}), 403
    
    # タスクの取得
    task = TeamTask.query.get_or_404(task_id)
    
    # ノードに紐づいているか確認
    if task.parent_node_id != node_id:
        return jsonify({'success': False, 'message': 'タスクがこのノードに紐づいていません'}), 400
    
    # フォームデータを取得
    title = request.form.get('title')
    description = request.form.get('description', '')
    due_date_str = request.form.get('due_date')
    priority = request.form.get('priority', 'medium')
    assigned_to_values = request.form.getlist('assigned_to')
    
    # 完了予定日の処理
    due_date_obj = None
    if due_date_str:
        try:
            due_date_obj = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # タスク情報を更新
    task.title = title
    task.description = description if description else None
    task.due_date = due_date_obj
    task.priority = priority
    task.updated_at = datetime.utcnow()
    
    # 既存のTaskAssigneeを取得
    existing_assignees = TaskAssignee.query.filter_by(team_task_id=task.id).all()
    existing_user_ids = {a.user_id for a in existing_assignees}
    
    # 新しい担当者リスト
    new_user_ids = set()
    for user_id_str in assigned_to_values:
        try:
            new_user_ids.add(int(user_id_str))
        except ValueError:
            pass
    
    # 削除する担当者（既存だが新リストにない）
    to_remove = existing_user_ids - new_user_ids
    for user_id in to_remove:
        task_assignee = TaskAssignee.query.filter_by(
            team_task_id=task.id,
            user_id=user_id
        ).first()
        if task_assignee:
            # 対応する個人タスクも削除
            personal_task = Task.query.filter_by(
                team_task_id=task.id,
                user_id=user_id
            ).first()
            if personal_task:
                db.session.delete(personal_task)
            db.session.delete(task_assignee)
    
    # 追加する担当者（新リストにはあるが既存にない）
    to_add = new_user_ids - existing_user_ids
    for user_id in to_add:
        # TaskAssigneeを作成
        task_assignee = TaskAssignee(
            team_task_id=task.id,
            user_id=user_id,
            completed=False
        )
        db.session.add(task_assignee)
        
        # 個人タスクを作成
        personal_task = Task(
            user_id=user_id,
            title=f'【{team.name}】{title}',
            description=description if description else None,
            start_date=due_date_obj,
            end_date=due_date_obj,
            priority=priority,
            category='other',
            team_task_id=task.id
        )
        db.session.add(personal_task)
        db.session.flush()
        
        # 通知を作成
        notification = Notification(
            user_id=user_id,
            title='チームタスクが割り当てられました',
            message=f'チーム「{team.name}」からタスク「{title}」が割り当てられました。',
            notification_type='info',
            related_team_id=team_id,
            related_task_id=personal_task.id
        )
        db.session.add(notification)
    
    # 既存の担当者の個人タスクも更新
    for user_id in existing_user_ids & new_user_ids:
        personal_task = Task.query.filter_by(
            team_task_id=task.id,
            user_id=user_id
        ).first()
        if personal_task:
            personal_task.title = f'【{team.name}】{title}'
            personal_task.description = description if description else None
            personal_task.start_date = due_date_obj
            personal_task.end_date = due_date_obj
            personal_task.priority = priority
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'タスクを更新しました'})

@main.route('/team-task-toggle', methods=['POST'])
@login_required
def toggle_team_task():
    """チームタスクの完了報告"""
    from models import TeamTask, TeamMember, Task, TaskAssignee, MindmapNode
    
    task_id = request.form.get('task_id')
    if not task_id:
        return jsonify({'success': False, 'message': 'タスクIDが指定されていません'}), 400
    
    team_task = TeamTask.query.get_or_404(int(task_id))
    
    # チームに所属しているか確認
    membership = TeamMember.query.filter_by(
        team_id=team_task.team_id,
        user_id=current_user.id
    ).first()
    
    if not membership:
        return jsonify({'success': False, 'message': 'このタスクを変更する権限がありません'}), 403
    
    # そのユーザーの個人タスクを取得
    personal_task = Task.query.filter_by(
        team_task_id=team_task.id,
        user_id=current_user.id
    ).first()
    
    if not personal_task:
        return jsonify({'success': False, 'message': 'このタスクの担当者ではありません'}), 403
    
    # 完了状態を切り替え
    personal_task.completed = not personal_task.completed
    
    # 完了にした場合、時間計測を停止
    if personal_task.completed and personal_task.is_tracking:
        if personal_task.tracking_start_time:
            elapsed = (datetime.utcnow() - personal_task.tracking_start_time).total_seconds()
            personal_task.total_seconds += int(elapsed)
        personal_task.is_tracking = False
        personal_task.tracking_start_time = None
    
    # TaskAssigneeを更新
    task_assignee = TaskAssignee.query.filter_by(
        team_task_id=team_task.id,
        user_id=current_user.id
    ).first()
    if task_assignee:
        task_assignee.completed = personal_task.completed
        task_assignee.completed_at = datetime.utcnow() if personal_task.completed else None
    
    # チームタスクの完了率を計算して更新
    completion_rate = team_task.calculate_completion_rate()
    team_task.completed = (completion_rate == 100)
    team_task.updated_at = datetime.utcnow()
    
    # 親ノードの進捗率を更新
    if team_task.parent_node_id:
        parent_node = MindmapNode.query.get(team_task.parent_node_id)
        if parent_node:
            parent_node.progress = parent_node.calculate_progress()
    
    # UserPerformanceを更新
    from models import UserPerformance
    UserPerformance.update_daily_performance(current_user.id)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'タスクを{"完了" if personal_task.completed else "未完了"}に変更しました'})

# ===== マインドマップAPI =====

@main.route('/mindmap/<int:team_id>/create', methods=['POST'])
@login_required
def create_mindmap(team_id):
    """マインドマップ作成"""
    from models import Team, TeamMember, Mindmap
    
    # チームに所属しているか確認
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user.id
    ).first()
    
    if not membership:
        return jsonify({'error': '権限がありません'}), 403
    
    data = request.get_json()
    name = data.get('name', '新規マインドマップ')
    description = data.get('description', '')
    
    # 既存のマインドマップを削除（1チーム1マインドマップの制約）
    existing = Mindmap.query.filter_by(team_id=team_id).first()
    if existing:
        db.session.delete(existing)
    
    # 新しいマインドマップを作成
    new_mindmap = Mindmap(
        team_id=team_id,
        name=name,
        description=description,
        created_by=current_user.id
    )
    
    db.session.add(new_mindmap)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'mindmap_id': new_mindmap.id
    })

@main.route('/mindmap/<int:team_id>/nodes', methods=['GET', 'POST'])
@login_required
def mindmap_nodes(team_id):
    """マインドマップノードの取得・作成"""
    from models import Team, TeamMember, Mindmap, MindmapNode
    
    # チームに所属しているか確認
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user.id
    ).first()
    
    if not membership:
        return jsonify({'error': '権限がありません'}), 403
    
    mindmap_obj = Mindmap.query.filter_by(team_id=team_id).first()
    if not mindmap_obj:
        return jsonify({'nodes': []})
    
    if request.method == 'GET':
        # ノード一覧を取得
        nodes = MindmapNode.query.filter_by(mindmap_id=mindmap_obj.id).all()
        nodes_data = []
        
        for node in nodes:
            nodes_data.append({
                'id': node.id,
                'parent_id': node.parent_id,
                'title': node.title,
                'description': node.description,
                'position_x': node.position_x,
                'position_y': node.position_y,
                'progress': node.progress,
                'completed': node.completed,
                'is_task': node.is_task,
                'team_task_id': node.team_task_id,
                'due_date': node.due_date.isoformat() if node.due_date else None
            })
        
        return jsonify({
            'nodes': nodes_data,
            'mindmap_id': mindmap_obj.id
        })
    
    elif request.method == 'POST':
        # ノード作成
        from models import TeamTask
        data = request.get_json()
        
        # 完了予定日の処理
        due_date_obj = None
        if data.get('due_date'):
            try:
                due_date_obj = datetime.strptime(data.get('due_date'), '%Y-%m-%d').date()
            except ValueError:
                pass
        
        new_node = MindmapNode(
            mindmap_id=mindmap_obj.id,
            parent_id=data.get('parent_id'),
            title=data.get('title', '新規ノード'),
            description=data.get('description', ''),
            position_x=data.get('position_x', 0),
            position_y=data.get('position_y', 0),
            is_task=data.get('is_task', False),
            due_date=due_date_obj
        )
        
        db.session.add(new_node)
        db.session.flush()  # IDを取得するため
        
        # 子ノード（親が存在する）の場合、自動でチームタスクを作成
        if data.get('parent_id'):
            team_task = TeamTask(
                team_id=team_id,
                title=data.get('title', '新規ノード'),
                description=data.get('description', ''),
                created_by=current_user.id,
                due_date=due_date_obj,
                parent_node_id=new_node.parent_id
            )
            db.session.add(team_task)
            db.session.flush()  # IDを取得するため
            
            # ノードとタスクを紐付け
            new_node.is_task = True
            new_node.team_task_id = team_task.id
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'node_id': new_node.id
        })

@main.route('/mindmap/<int:team_id>/nodes/<int:node_id>', methods=['PUT', 'DELETE'])
@login_required
def update_mindmap_node(team_id, node_id):
    """ノードの更新・削除"""
    from models import Team, TeamMember, Mindmap, MindmapNode
    
    # チームに所属しているか確認
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user.id
    ).first()
    
    if not membership:
        return jsonify({'error': '権限がありません'}), 403
    
    node = MindmapNode.query.get_or_404(node_id)
    
    if request.method == 'PUT':
        # ノード更新
        data = request.get_json()
        
        if 'title' in data:
            node.title = data['title']
        if 'description' in data:
            node.description = data['description']
        if 'position_x' in data:
            node.position_x = data['position_x']
        if 'position_y' in data:
            node.position_y = data['position_y']
        if 'progress' in data:
            node.progress = data['progress']
        if 'completed' in data:
            node.completed = data['completed']
        if 'due_date' in data:
            if data['due_date']:
                try:
                    node.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
                except ValueError:
                    pass
            else:
                node.due_date = None
        
        node.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        # ノード削除
        from models import TeamTask, Task, TaskAssignee
        
        # このノードに紐づいている全てのチームタスクを取得（サブタスクとして）
        related_team_tasks = TeamTask.query.filter_by(parent_node_id=node_id).all()
        
        # 関連するチームタスクを削除
        for team_task in related_team_tasks:
            # TaskAssigneeを削除
            task_assignees = TaskAssignee.query.filter_by(team_task_id=team_task.id).all()
            for assignee in task_assignees:
                # 対応する個人タスクも削除
                personal_task = Task.query.filter_by(
                    team_task_id=team_task.id,
                    user_id=assignee.user_id
                ).first()
                if personal_task:
                    db.session.delete(personal_task)
                db.session.delete(assignee)
            
            # チームタスクを削除
            db.session.delete(team_task)
        
        # ノードを削除（子ノードはcascadeで自動削除される）
        db.session.delete(node)
        db.session.commit()
        
        return jsonify({'success': True})

@main.route('/mindmap/<int:team_id>/nodes/<int:node_id>/task', methods=['POST'])
@login_required
def create_task_from_node(team_id, node_id):
    """ノードからタスクを作成"""
    from models import Team, TeamMember, Mindmap, MindmapNode, TeamTask
    
    # チームに所属しているか確認
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user.id
    ).first()
    
    if not membership:
        return jsonify({'error': '権限がありません'}), 403
    
    node = MindmapNode.query.get_or_404(node_id)
    
    # 既にタスクが紐づいているか確認
    if node.is_task and node.team_task_id:
        return jsonify({'error': '既にタスクが紐づいています'}), 400
    
    # チームタスクを作成
    new_task = TeamTask(
        team_id=team_id,
        title=node.title,
        description=node.description,
        created_by=current_user.id
    )
    
    db.session.add(new_task)
    db.session.flush()  # IDを取得するため
    
    # ノードとタスクを紐付け
    node.is_task = True
    node.team_task_id = new_task.id
    db.session.commit()
    
    return jsonify({
        'success': True,
        'task_id': new_task.id
    })

@main.route('/mindmap/<int:team_id>/progress')
@login_required
def get_mindmap_progress(team_id):
    """マインドマップ全体の達成度を取得"""
    from models import Team, TeamMember, Mindmap
    
    # チームに所属しているか確認
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user.id
    ).first()
    
    if not membership:
        return jsonify({'error': '権限がありません'}), 403
    
    mindmap_obj = Mindmap.query.filter_by(team_id=team_id).first()
    if not mindmap_obj:
        return jsonify({'progress': 0})
    
    progress = mindmap_obj.calculate_progress()
    
    return jsonify({'progress': progress})

# ===== 個人マインドマップAPI =====

@main.route('/personal/mindmap/create', methods=['POST'])
@login_required
def create_personal_mindmap():
    """個人マインドマップ作成"""
    from models import Mindmap
    
    data = request.get_json()
    name = data.get('name', '新規マインドマップ')
    description = data.get('description', '')
    map_date = data.get('date')  # 'YYYY-MM-DD'形式
    
    # 日付の変換
    date_obj = None
    if map_date:
        try:
            date_obj = datetime.strptime(map_date, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # デフォルトは今日の日付
    if not date_obj:
        date_obj = date.today()
    
    # 新しいマインドマップを作成
    new_mindmap = Mindmap(
        user_id=current_user.id,
        name=name,
        description=description,
        date=date_obj,
        created_by=current_user.id
    )
    
    db.session.add(new_mindmap)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'mindmap_id': new_mindmap.id
    })

@main.route('/personal/mindmap/nodes', methods=['GET', 'POST'])
@login_required
def personal_mindmap_nodes():
    """個人マインドマップノードの取得・作成"""
    from models import Mindmap, MindmapNode, Task
    
    # URLパラメータからマインドマップIDを取得
    mindmap_id = request.args.get('mindmap_id', type=int)
    
    # マインドマップを取得
    if mindmap_id:
        mindmap_obj = Mindmap.query.filter_by(id=mindmap_id, user_id=current_user.id).first()
    else:
        # デフォルトで最新のものを取得
        mindmap_obj = Mindmap.query.filter_by(user_id=current_user.id).order_by(Mindmap.date.desc(), Mindmap.created_at.desc()).first()
    
    if not mindmap_obj:
        return jsonify({'nodes': []})
    
    if request.method == 'GET':
        # ノード一覧を取得
        nodes = MindmapNode.query.filter_by(mindmap_id=mindmap_obj.id).all()
        nodes_data = []
        
        for node in nodes:
            nodes_data.append({
                'id': node.id,
                'parent_id': node.parent_id,
                'title': node.title,
                'description': node.description,
                'position_x': node.position_x,
                'position_y': node.position_y,
                'progress': node.progress,
                'completed': node.completed,
                'is_task': node.is_task
            })
        
        return jsonify({'nodes': nodes_data, 'mindmap_id': mindmap_obj.id})
    
    elif request.method == 'POST':
        # ノード作成
        data = request.get_json()
        
        new_node = MindmapNode(
            mindmap_id=mindmap_obj.id,
            parent_id=data.get('parent_id'),
            title=data.get('title', '新規ノード'),
            description=data.get('description', ''),
            position_x=data.get('position_x', 0),
            position_y=data.get('position_y', 0),
            is_task=data.get('is_task', False)
        )
        
        # タスクとして設定されている場合、個人タスクを作成
        if data.get('is_task', False) and not data.get('parent_id'):
            # ルートノードのみタスクとして作成
            new_task = Task(
                title=new_node.title,
                description=new_node.description,
                user_id=current_user.id,
                category='other',
                priority='medium',
                completed=False
            )
            db.session.add(new_task)
            db.session.flush()  # task_idを取得
            new_node.task_id = new_task.id
        
        db.session.add(new_node)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'node_id': new_node.id
        })

@main.route('/personal/mindmap/nodes/<int:node_id>', methods=['PUT', 'DELETE'])
@login_required
def update_personal_mindmap_node(node_id):
    """個人マインドマップノードの更新・削除"""
    from models import Mindmap, MindmapNode, Task, UserPerformance
    
    node = MindmapNode.query.get_or_404(node_id)
    
    # 自分のマインドマップのノードか確認
    mindmap_obj = Mindmap.query.filter_by(id=node.mindmap_id, user_id=current_user.id).first()
    if not mindmap_obj:
        return jsonify({'error': '権限がありません'}), 403
    
    if request.method == 'PUT':
        # ノード更新
        data = request.get_json()
        
        if 'title' in data:
            node.title = data['title']
        if 'description' in data:
            node.description = data['description']
        if 'position_x' in data:
            node.position_x = data['position_x']
        if 'position_y' in data:
            node.position_y = data['position_y']
        if 'progress' in data:
            node.progress = data['progress']
        if 'completed' in data:
            node.completed = data['completed']
        
        # is_taskが変更された場合の処理
        if 'is_task' in data:
            is_task = data['is_task']
            
            # ルートノードでis_taskがTrueになった場合、個人タスクを作成
            if is_task and not node.parent_id and not node.task_id:
                new_task = Task(
                    title=node.title,
                    description=node.description or '',
                    user_id=current_user.id,
                    category='other',
                    priority='medium',
                    completed=False
                )
                db.session.add(new_task)
                db.session.flush()
                node.task_id = new_task.id
                
                # パフォーマンス更新
                UserPerformance.update_daily_performance(current_user.id)
            
            # is_taskがFalseになった場合、リンクされたタスクを削除
            elif not is_task and node.task_id:
                task = Task.query.get(node.task_id)
                if task:
                    db.session.delete(task)
                node.task_id = None
            
            node.is_task = is_task
        
        # 既存のタスクがリンクされている場合、タスクも更新
        if node.task_id:
            task = Task.query.get(node.task_id)
            if task:
                if 'title' in data:
                    task.title = data['title']
                if 'description' in data:
                    task.description = data.get('description', '')
                if 'completed' in data:
                    task.completed = data['completed']
                
                # パフォーマンス更新
                UserPerformance.update_daily_performance(current_user.id)
        
        node.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        # ノード削除時、リンクされたタスクも削除
        if node.task_id:
            task = Task.query.get(node.task_id)
            if task:
                db.session.delete(task)
        
        db.session.delete(node)
        db.session.commit()
        
        return jsonify({'success': True})

@main.route('/personal/mindmap/progress')
@login_required
def get_personal_mindmap_progress():
    """個人マインドマップ全体の達成度を取得"""
    from models import Mindmap
    
    # URLパラメータからマインドマップIDを取得
    mindmap_id = request.args.get('mindmap_id', type=int)
    
    # マインドマップを取得
    if mindmap_id:
        mindmap_obj = Mindmap.query.filter_by(id=mindmap_id, user_id=current_user.id).first()
    else:
        # デフォルトで最新のものを取得
        mindmap_obj = Mindmap.query.filter_by(user_id=current_user.id).order_by(Mindmap.date.desc(), Mindmap.created_at.desc()).first()
    
    if not mindmap_obj:
        return jsonify({'progress': 0})
    
    progress = mindmap_obj.calculate_progress()
    
    return jsonify({'progress': progress})

@main.route('/personal/mindmaps')
@login_required
def list_personal_mindmaps():
    """個人マインドマップ一覧を取得"""
    from models import Mindmap
    
    mindmaps = Mindmap.query.filter_by(user_id=current_user.id).order_by(Mindmap.date.desc(), Mindmap.created_at.desc()).all()
    
    mindmaps_data = []
    for mindmap in mindmaps:
        mindmaps_data.append({
            'id': mindmap.id,
            'name': mindmap.name,
            'description': mindmap.description,
            'date': mindmap.date.isoformat() if mindmap.date else None
        })
    
    return jsonify({'mindmaps': mindmaps_data})

@main.route('/admin/toggle-admin', methods=['POST'])
@login_required
def toggle_admin():
    """管理者フラグの切り替え"""
    from models import User
    from flask import request as flask_request
    
    # 管理者権限チェック
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '管理者権限が必要です'}), 403
    
    data = flask_request.get_json()
    user_id = data.get('user_id')
    is_admin = data.get('is_admin')
    
    if not user_id:
        return jsonify({'success': False, 'message': 'ユーザーIDが指定されていません'}), 400
    
    user = User.query.get_or_404(user_id)
    user.is_admin = is_admin
    db.session.commit()
    
    return jsonify({'success': True, 'message': '管理者権限を更新しました'})

@main.route('/admin/create-user', methods=['POST'])
@login_required
def create_user():
    """新規ユーザー作成（管理者のみ）"""
    from models import User
    
    # 管理者権限チェック
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '管理者権限が必要です'}), 403
    
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    password_confirm = data.get('password_confirm', '')
    
    # バリデーション
    if not username or not email or not password:
        return jsonify({'success': False, 'message': 'すべての項目を入力してください'}), 400
    
    if password != password_confirm:
        return jsonify({'success': False, 'message': 'パスワードが一致しません'}), 400
    
    # ユーザー名の重複チェック
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'このユーザー名は既に使用されています'}), 400
    
    # メールアドレスの重複チェック
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'このメールアドレスは既に使用されています'}), 400
    
    # 新規ユーザー作成
    new_user = User(
        username=username,
        email=email,
        is_admin=False
    )
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'ユーザー「{username}」を作成しました',
        'user_id': new_user.id
    })
