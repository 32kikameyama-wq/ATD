def _update_task_card_progress(node_id):
    """カードに紐づくタスクの完了率を再計算"""
    from models import MindmapNode, Task
    node = MindmapNode.query.get(node_id)
    if not node:
        return
    card_tasks = Task.query.filter_by(task_card_node_id=node.id, archived=False).all()
    if card_tasks:
        progress = int(sum(1 for task in card_tasks if task.completed) / len(card_tasks) * 100)
    else:
        progress = 0
    if node.progress != progress:
        node.progress = progress
        db.session.add(node)
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import current_user, login_required
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from models import db

# ブループリントを作成
main = Blueprint('main', __name__)


def _is_mobile_user_agent():
    ua = request.headers.get('User-Agent', '').lower()
    mobile_keywords = ['iphone', 'android', 'ipad', 'ipod', 'mobile']
    return any(keyword in ua for keyword in mobile_keywords)


@main.before_app_request
def redirect_mobile_users():
    if request.method != 'GET':
        return
    if not current_user.is_authenticated:
        return
    if request.path.startswith('/mobile') or request.path.startswith('/static'):
        return
    if request.args.get('view') == 'desktop':
        return
    if not _is_mobile_user_agent():
        return

    normalized_path = request.path.rstrip('/') or '/'
    mobile_route_map = {
        '/': 'main.mobile_home',
        '/dashboard': 'main.mobile_home',
        '/tasks': 'main.mobile_tasks',
        '/personal-tasks': 'main.mobile_tasks',
        '/tasks/create': 'tasks.mobile_create_task',
        '/team-management': 'main.mobile_team',
        '/team-tasks': 'main.mobile_team',
        '/team-mindmap': 'main.mobile_team_mindmap',
        '/notifications': 'main.mobile_notifications',
        '/profile': 'main.mobile_settings',
    }

    endpoint = mobile_route_map.get(normalized_path)
    if endpoint:
        return redirect(url_for(endpoint))


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
    
    # 日付を取得（現在時刻から取得）
    now = datetime.now(ZoneInfo('Asia/Tokyo'))
    today = now.date()
    current_time = now.strftime('%Y-%m-%d %H:%M:%S')
    
    # デバッグ: 現在の日時を出力
    print(f"[DEBUG] Dashboard accessed at: {current_time}, Date: {today}")
    
    # 日次の自動処理（日付切り替え・タスク繰り越し）- 日付が変わった時のみ実行
    # 昨日のUserPerformanceレコードが存在し、今日のレコードが存在しない場合 = 日付が変わった
    get_daily_statistics = None
    try:
        from daily_processor import process_daily_rollover, get_daily_statistics
        # 日次処理はprocess_daily_rollover内で日付変更をチェックして実行
        result = process_daily_rollover(current_user.id)
        print(f"[DEBUG] Daily rollover result: {result}")
    except Exception as e:
        # 日次処理エラーはログに記録
        print(f"[ERROR] Daily rollover error: {e}")
        import traceback
        traceback.print_exc()
        # get_daily_statisticsがNoneの場合は、後でエラーが発生しないようにする
        if 'get_daily_statistics' not in locals():
            get_daily_statistics = None
    
    # パフォーマンスデータを更新（日次処理の後）
    UserPerformance.update_daily_performance(current_user.id, date=today)
    
    # 本日のタスクを取得（優先順位順）
    # category='today'のタスクをすべて取得（昨日の未完了タスクも含む）
    today_tasks_all = Task.query.filter_by(
        user_id=current_user.id,
        category='today',
        archived=False
    ).order_by(Task.order_index).all()
    today_tasks = []
    for task in today_tasks_all:
        if task.completed and task.completed_at and task.completed_at.date() < today:
            continue
        today_tasks.append(task)

    # 完了済みタスク数（当日分のみ）
    completed_tasks = sum(1 for task in today_tasks if task.completed)

    # 総タスク数（当日表示対象）
    total_tasks = len(today_tasks)
    
    # 進捗率（パーセンテージ）
    progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # 今日のパフォーマンスデータを取得（今日の日付を使用）
    today_performance = UserPerformance.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first()
    
    # 過去7日間のパフォーマンスデータ
    end_date = today
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
    try:
        if get_daily_statistics and callable(get_daily_statistics):
            daily_stats = get_daily_statistics(current_user.id, days=7)
        else:
            daily_stats = []
    except Exception as e:
        print(f"get_daily_statistics error: {e}")
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
        if task.completed and not task.archived and task.total_seconds > 0:
            # タイトルが長すぎる場合は切り詰める（30文字まで）
            title = task.title[:30] + '...' if len(task.title) > 30 else task.title
            # 変な文字が含まれている可能性があるので、改行や特殊文字を除去
            title = title.replace('\n', ' ').replace('\r', ' ').strip()
            task_time_data.append({
                'title': title,
                'total_seconds': task.total_seconds,
                'formatted_time': task.format_time()
            })
    
    # 過去のタスクを取得（URLパラメータから日付を取得）
    selected_date_str = request.args.get('past_date')
    past_tasks = []
    selected_date = None
    
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            # 指定された日付のタスクを取得（完了したタスクも含む）
            past_tasks = Task.query.filter(
                Task.user_id == current_user.id,
                Task.archived == False,
                db.func.date(Task.created_at) == selected_date
            ).order_by(Task.order_index).all()
        except ValueError:
            pass
    
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
                         today_stats=today_stats,
                         past_tasks=past_tasks,
                         selected_date=selected_date)


@main.route('/mobile')
@login_required
def mobile_index():
    return redirect(url_for('main.mobile_home'))


@main.route('/mobile/home')
@login_required
def mobile_home():
    from models import Task, UserPerformance, TeamMember, TeamTask

    now = datetime.now(ZoneInfo('Asia/Tokyo'))
    today = now.date()

    UserPerformance.update_daily_performance(current_user.id, date=today)

    today_tasks_all = Task.query.filter_by(
        user_id=current_user.id,
        category='today',
        archived=False
    ).order_by(Task.order_index).all()
    today_tasks = []
    for task in today_tasks_all:
        if task.completed and task.completed_at and task.completed_at.date() < today:
            continue
        today_tasks.append(task)

    completed_tasks = sum(1 for task in today_tasks if task.completed)
    total_tasks = len(today_tasks)
    progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    today_stats = UserPerformance.query.filter_by(
        user_id=current_user.id,
        date=today
    ).first()

    memberships = TeamMember.query.filter_by(user_id=current_user.id).all()
    team_ids = [membership.team_id for membership in memberships if membership.team_id]

    if team_ids:
        total_team_tasks = TeamTask.query.filter(TeamTask.team_id.in_(team_ids)).count()
        completed_team_tasks = TeamTask.query.filter(
            TeamTask.team_id.in_(team_ids),
            TeamTask.completed == True
        ).count()
        team_member_count = TeamMember.query.filter(TeamMember.team_id.in_(team_ids)).count()
        team_progress = int(completed_team_tasks / total_team_tasks * 100) if total_team_tasks else 0
    else:
        team_member_count = 0
        team_progress = 0

    return render_template('mobile/home.html',
                           today_tasks=today_tasks,
                           progress_percentage=progress_percentage,
                           completed_tasks=completed_tasks,
                           total_tasks=total_tasks,
                           today_stats=today_stats,
                           team_progress=team_progress,
                           team_member_count=team_member_count)


@main.route('/mobile/tasks')
@login_required
def mobile_tasks():
    from models import Task

    today = datetime.now(ZoneInfo('Asia/Tokyo')).date()
    today_tasks_all = Task.query.filter_by(
        user_id=current_user.id,
        category='today',
        archived=False
    ).order_by(Task.order_index).all()
    today_tasks = []
    for task in today_tasks_all:
        if task.completed and task.completed_at and task.completed_at.date() < today:
            continue
        today_tasks.append(task)
    tomorrow_tasks = Task.query.filter_by(
        user_id=current_user.id,
        category='tomorrow',
        archived=False
    ).filter(Task.completed == False).order_by(Task.order_index).all()
    other_tasks = Task.query.filter_by(
        user_id=current_user.id,
        category='other',
        archived=False
    ).filter(Task.completed == False).order_by(Task.order_index).all()

    return render_template('mobile/tasks.html',
                           today_tasks=today_tasks,
                           tomorrow_tasks=tomorrow_tasks,
                           other_tasks=other_tasks)


@main.route('/mobile/team')
@login_required
def mobile_team():
    from models import Team, TeamMember, TeamTask, TaskAssignee, User

    memberships = TeamMember.query.filter_by(user_id=current_user.id).all()
    team_ids = [membership.team_id for membership in memberships if membership.team_id]

    team_overview = []
    active_team_tasks = []

    if team_ids:
        teams = Team.query.filter(Team.id.in_(team_ids)).all()
        for team in teams:
            members = TeamMember.query.filter_by(team_id=team.id).count()
            total_tasks = TeamTask.query.filter_by(team_id=team.id).count()
            completed_tasks = TeamTask.query.filter_by(team_id=team.id, completed=True).count()
            progress = int(completed_tasks / total_tasks * 100) if total_tasks else 0
            team_overview.append({
                'name': team.name,
                'members': members,
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'progress': progress
            })

        team_tasks = TeamTask.query.filter(TeamTask.team_id.in_(team_ids)).order_by(TeamTask.due_date.asc(), TeamTask.created_at.desc()).all()
        for task in team_tasks:
            assignees = TaskAssignee.query.filter_by(team_task_id=task.id).all()
            assignee_names = []
            for assignee in assignees:
                user = User.query.get(assignee.user_id)
                if user:
                    assignee_names.append(user.display_name or user.username)
            active_team_tasks.append({
                'id': task.id,
                'title': task.title,
                'due_date': task.due_date,
                'completed': task.completed,
                'assignee_names': ', '.join(assignee_names) if assignee_names else '未割り当て'
            })

    return render_template('mobile/team.html',
                           team_overview=team_overview,
                           active_team_tasks=active_team_tasks)


@main.route('/mobile/team-mindmap')
@login_required
def mobile_team_mindmap():
    from models import Team, TeamMember, Mindmap, MindmapNode

    memberships = TeamMember.query.filter_by(user_id=current_user.id).all()
    team_ids = [membership.team_id for membership in memberships if membership.team_id]
    team_mindmaps = []
    if team_ids:
        teams = Team.query.filter(Team.id.in_(team_ids)).all()
        for team in teams:
            mindmaps = Mindmap.query.filter_by(team_id=team.id).order_by(
                Mindmap.date.desc().nullslast(), Mindmap.created_at.desc()
            ).all()
            mindmap_data = []
            for mindmap in mindmaps:
                root_nodes = MindmapNode.query.filter_by(
                    mindmap_id=mindmap.id, parent_id=None
                ).order_by(MindmapNode.id.asc()).all()

                node_summaries = []
                for node in root_nodes:
                    node_summaries.append({
                        'id': node.id,
                        'title': node.title,
                        'progress': node.calculate_progress(),
                        'children_count': len(node.children),
                        'is_task': node.is_task,
                        'due_date': node.due_date
                    })

                mindmap_data.append({
                    'id': mindmap.id,
                    'name': mindmap.name,
                    'description': mindmap.description,
                    'date': mindmap.date,
                    'node_summaries': node_summaries
                })

            team_mindmaps.append({
                'team': team,
                'mindmaps': mindmap_data
            })

    return render_template('mobile/team_mindmap.html', team_mindmaps=team_mindmaps)


@main.route('/mobile/notifications')
@login_required
def mobile_notifications():
    from models import Notification

    unread_notifications_list = Notification.query.filter_by(
        user_id=current_user.id,
        read=False
    ).order_by(Notification.created_at.desc()).all()

    all_notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(30).all()

    return render_template('mobile/notifications.html',
                           unread_notifications_list=unread_notifications_list,
                           all_notifications=all_notifications)


@main.route('/mobile/settings')
@login_required
def mobile_settings():
    return render_template('mobile/settings.html')

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
        from zoneinfo import ZoneInfo
        target_date = datetime.now(ZoneInfo('Asia/Tokyo')).date()
    
    # テンプレートからタスク作成
    new_task = template.create_task_from_template(target_date)
    db.session.add(new_task)
    db.session.commit()
    
    flash(f'テンプレートからタスクを作成しました', 'success')
    return redirect(url_for('tasks.list_tasks'))

def _build_calendar_context(year=None, month=None):
    """カレンダー画面で共通利用するデータを生成"""
    from models import Task, TaskTemplate
    from datetime import datetime, timedelta
    import calendar as cal
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo('Asia/Tokyo'))
    target_year = year or now.year
    target_month = month or now.month

    first_day = datetime(target_year, target_month, 1).date()
    last_day_num = cal.monthrange(target_year, target_month)[1]
    last_day = datetime(target_year, target_month, last_day_num).date()

    first_weekday = (first_day.weekday() + 1) % 7
    calendar_start = first_day - timedelta(days=first_weekday)

    last_weekday = (last_day.weekday() + 1) % 7
    calendar_end = last_day + timedelta(days=(6 - last_weekday))

    all_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.start_date >= calendar_start,
        Task.start_date <= calendar_end,
        Task.archived == False
    ).all()

    tasks_by_date = {}
    tasks_by_date_json = {}
    for task in all_tasks:
        date_key = task.start_date.strftime('%Y-%m-%d')
        if date_key not in tasks_by_date:
            tasks_by_date[date_key] = []
            tasks_by_date_json[date_key] = []
        tasks_by_date[date_key].append(task)
        tasks_by_date_json[date_key].append({
            'id': task.id,
            'title': task.title,
            'description': task.description or '',
            'priority': task.priority,
            'completed': task.completed,
            'start_date': task.start_date.strftime('%Y-%m-%d'),
            'end_date': task.end_date.strftime('%Y-%m-%d') if task.end_date else None
        })

    calendar_dates = []
    current_date = calendar_start
    while current_date <= calendar_end:
        calendar_dates.append(current_date)
        current_date += timedelta(days=1)

    templates = TaskTemplate.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(TaskTemplate.created_at.desc()).all()

    prev_month = target_month - 1
    prev_year = target_year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    next_month = target_month + 1
    next_year = target_year
    if next_month > 12:
        next_month = 1
        next_year += 1

    calendar_weeks = [
        calendar_dates[i:i + 7] for i in range(0, len(calendar_dates), 7)
    ]

    return {
        'year': target_year,
        'month': target_month,
        'now': now,
        'first_day': first_day,
        'last_day': last_day,
        'calendar_start': calendar_start,
        'calendar_end': calendar_end,
        'calendar_dates': calendar_dates,
        'calendar_weeks': calendar_weeks,
        'tasks_by_date': tasks_by_date,
        'tasks_by_date_json': tasks_by_date_json,
        'templates': templates,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'today_str': now.strftime('%Y-%m-%d')
    }


@main.route('/calendar')
@login_required
def calendar():
    """カレンダー表示（デスクトップ）"""
    year = request.args.get('year', None, type=int)
    month = request.args.get('month', None, type=int)
    context = _build_calendar_context(year=year, month=month)
    return render_template('calendar.html', **context)


@main.route('/mobile/calendar')
@login_required
def mobile_calendar():
    """モバイル向けカレンダー表示"""
    year = request.args.get('year', None, type=int)
    month = request.args.get('month', None, type=int)
    context = _build_calendar_context(year=year, month=month)

    selected_date = request.args.get('date') or context['today_str']
    from datetime import datetime
    try:
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        selected_date = context['today_str']
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()

    weekday_labels = ['月', '火', '水', '木', '金', '土', '日']
    context['selected_date'] = selected_date
    context['selected_date_display'] = f"{selected_date_obj.strftime('%Y年%m月%d日')}（{weekday_labels[selected_date_obj.weekday()]}）"
    context['selected_day_tasks'] = context['tasks_by_date'].get(selected_date, [])
    context['weekday_headers'] = ['日', '月', '火', '水', '木', '金', '土']

    return render_template('mobile/calendar.html', **context)

@main.route('/daily-report')
@login_required
def daily_report():
    """日報レポート"""
    from models import Task, UserPerformance
    from datetime import datetime, timedelta
    from daily_processor import get_daily_statistics
    
    # 今日の日付
    today = datetime.now(ZoneInfo('Asia/Tokyo')).date()
    
    # URLパラメータから日付と期間を取得
    selected_date_str = request.args.get('date')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # 日付選択モード（単一日付）
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            report_date = selected_date
            report_mode = 'single'  # 単一日付モード
        except ValueError:
            report_date = today
            report_mode = 'today'
    # 期間選択モード
    elif start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            report_date = start_date  # 表示用
            report_mode = 'period'  # 期間モード
            # 期間の日数を計算
            period_days = (end_date - start_date).days + 1
        except ValueError:
            report_date = today
            report_mode = 'today'
            period_days = 1
    else:
        # デフォルトは今日
        report_date = today
        report_mode = 'today'
        period_days = 1
    
    # 報告日（または期間）のタスク統計を取得
    if report_mode == 'single':
        # 単一日付の場合、その日の統計を取得
        # SQLite互換性のため、Python側でフィルタリング
        all_tasks = Task.query.filter(
            Task.user_id == current_user.id,
            Task.archived == False
        ).all()
        
        # その日に作成されたタスク数
        total_on_date = 0
        completed_on_date = 0
        
        for task in all_tasks:
            if task.created_at:
                created_date = task.created_at.date()
                if created_date == report_date:
                    total_on_date += 1
                    
                if task.completed and task.updated_at:
                    updated_date = task.updated_at.date()
                    if updated_date == report_date:
                        completed_on_date += 1
        
        completion_rate = (completed_on_date / total_on_date * 100) if total_on_date > 0 else 0
        
        today_stats = {
            'date': report_date,
            'total': total_on_date,
            'completed': completed_on_date,
            'completion_rate': round(completion_rate, 1)
        }
        
        # その日のタスク一覧を取得
        today_tasks_list = []
        for task in all_tasks:
            if task.created_at:
                created_date = task.created_at.date()
                if created_date == report_date:
                    today_tasks_list.append(task)
        
        # その日の総作業時間を計算
        today_total_seconds = sum(
            task.total_seconds for task in today_tasks_list 
            if task.completed and not task.archived
        )
        
        # 週間統計は過去7日間（報告日から）
        weekly_stats = []
        for i in range(7):
            check_date = report_date - timedelta(days=6-i)
            total_count = 0
            completed_count = 0
            
            for task in all_tasks:
                if task.created_at:
                    created_date = task.created_at.date()
                    if created_date == check_date:
                        total_count += 1
                    if task.completed and task.updated_at:
                        updated_date = task.updated_at.date()
                        if updated_date == check_date:
                            completed_count += 1
            
            rate = (completed_count / total_count * 100) if total_count > 0 else 0
            weekly_stats.append({
                'date': check_date,
                'total': total_count,
                'completed': completed_count,
                'completion_rate': round(rate, 1)
            })
        
        avg_completion = sum(s['completion_rate'] for s in weekly_stats) / len(weekly_stats) if weekly_stats else 0
        
        # 月間統計は過去30日間（報告日から）
        monthly_stats = []
        for i in range(30):
            check_date = report_date - timedelta(days=29-i)
            total_count = 0
            completed_count = 0
            
            for task in all_tasks:
                if task.created_at:
                    created_date = task.created_at.date()
                    if created_date == check_date:
                        total_count += 1
                    if task.completed and task.updated_at:
                        updated_date = task.updated_at.date()
                        if updated_date == check_date:
                            completed_count += 1
            
            rate = (completed_count / total_count * 100) if total_count > 0 else 0
            monthly_stats.append({
                'date': check_date,
                'total': total_count,
                'completed': completed_count,
                'completion_rate': round(rate, 1)
            })
        
        monthly_avg_completion = sum(s['completion_rate'] for s in monthly_stats) / len(monthly_stats) if monthly_stats else 0
        
    elif report_mode == 'period':
        # 期間モードの場合、期間内の統計を集計
        all_tasks = Task.query.filter(
            Task.user_id == current_user.id,
            Task.archived == False
        ).all()
        
        # 期間内のタスクを集計
        period_tasks = []
        period_total = 0
        period_completed = 0
        period_total_seconds = 0
        
        for task in all_tasks:
            if task.created_at:
                created_date = task.created_at.date()
                if start_date <= created_date <= end_date:
                    period_tasks.append(task)
                    period_total += 1
                    if task.completed and task.updated_at:
                        updated_date = task.updated_at.date()
                        if start_date <= updated_date <= end_date:
                            period_completed += 1
                            period_total_seconds += task.total_seconds
        
        period_completion_rate = (period_completed / period_total * 100) if period_total > 0 else 0
        
        today_stats = {
            'date': start_date,
            'total': period_total,
            'completed': period_completed,
            'completion_rate': round(period_completion_rate, 1)
        }
        
        today_tasks_list = period_tasks
        today_total_seconds = period_total_seconds
        
        # 期間内の日次統計を生成
        weekly_stats = []
        for i in range(period_days):
            check_date = start_date + timedelta(days=i)
            if check_date > end_date:
                break
                
            total_count = 0
            completed_count = 0
            
            for task in all_tasks:
                if task.created_at:
                    created_date = task.created_at.date()
                    if created_date == check_date:
                        total_count += 1
                    if task.completed and task.updated_at:
                        updated_date = task.updated_at.date()
                        if updated_date == check_date:
                            completed_count += 1
            
            rate = (completed_count / total_count * 100) if total_count > 0 else 0
            weekly_stats.append({
                'date': check_date,
                'total': total_count,
                'completed': completed_count,
                'completion_rate': round(rate, 1)
            })
        
        avg_completion = sum(s['completion_rate'] for s in weekly_stats) / len(weekly_stats) if weekly_stats else 0
        monthly_stats = weekly_stats  # 期間内の統計をそのまま使用
        monthly_avg_completion = avg_completion
        
    else:
        # デフォルト（今日）の場合
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
        
        # 今日の総作業時間を計算（完了済みタスクのみ）
        today_total_seconds = sum(task.total_seconds for task in today_tasks_list if task.completed and not task.archived)
    
    # 連続記録
    latest_perf = UserPerformance.query.filter_by(
        user_id=current_user.id
    ).order_by(UserPerformance.date.desc()).first()
    streak = latest_perf.streak_days if latest_perf else 0
    
    # 計画達成状況の判定（目標は80%）
    target_completion_rate = 80.0
    today_on_target = today_stats['completion_rate'] >= target_completion_rate
    weekly_on_target = avg_completion >= target_completion_rate
    monthly_on_target = monthly_avg_completion >= target_completion_rate
    
    return render_template('daily_report.html',
                         today=today,
                         report_date=report_date,
                         report_mode=report_mode,
                         start_date=start_date if report_mode == 'period' else None,
                         end_date=end_date if report_mode == 'period' else None,
                         period_days=period_days if report_mode == 'period' else 1,
                         today_stats=today_stats,
                         weekly_stats=weekly_stats,
                         today_tasks=today_tasks_list,
                         avg_completion=round(avg_completion, 1),
                         monthly_avg_completion=round(monthly_avg_completion, 1),
                         streak=streak,
                         target_completion_rate=target_completion_rate,
                         today_on_target=today_on_target,
                         weekly_on_target=weekly_on_target,
                         monthly_on_target=monthly_on_target,
                         today_total_seconds=today_total_seconds)

@main.route('/team-management')
@login_required
def team_management():
    """チーム管理"""
    from models import Team, TeamMember, TeamTask, Task, User
    from datetime import datetime, date
    
    # 期間パラメータの取得（デフォルトは今日）
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = date.today()
    else:
        start_date = date.today()
    
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = date.today()
    else:
        end_date = date.today()
    
    # チームメンバー全体用のチーム選択パラメータを取得
    selected_team_id = request.args.get('selected_team_id', type=int)
    
    # ユーザーが所属するチームを取得
    user_teams = Team.query.join(TeamMember).filter(
        TeamMember.user_id == current_user.id
    ).all()
    
    # チームのタスク数とメンバー数を取得（期間フィルタなし）
    team_stats = {}
    for team in user_teams:
        # 全チームタスクを取得（期間フィルタなし）
        all_team_tasks = TeamTask.query.filter(
            TeamTask.team_id == team.id
        ).all()
        
        total_tasks = len(all_team_tasks)
        completed_tasks = sum(1 for task in all_team_tasks if task.completed)
        
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
    
    # チーム全体の統計（期間フィルタなし）
    # チームタスク（TeamTask）を集計：チームから割り当てられたタスク＋割り当てられていないが存在するタスク
    all_team_ids = [team.id for team in user_teams]
    
    # 全チームタスクを取得（期間フィルタなし）
    all_team_tasks = TeamTask.query.filter(
        TeamTask.team_id.in_(all_team_ids)
    ).all() if all_team_ids else []
    
    # 統計を計算（期間フィルタなし）
    overall_total_tasks = len(all_team_tasks)
    overall_completed_tasks = sum(1 for task in all_team_tasks if task.completed)
    overall_progress = (overall_completed_tasks / overall_total_tasks * 100) if overall_total_tasks > 0 else 0
    total_teams = len(user_teams)
    
    # チームメンバー全体：選択したチームのメンバーの個人タスクの統計を計算（期間フィルタなし）
    # 選択したチームのメンバーの個人タスク（Task）を集計
    if selected_team_id:
        # 選択したチームのメンバーを取得
        team_members = TeamMember.query.filter_by(team_id=selected_team_id).all()
        member_ids = [member.user_id for member in team_members]
        
        if member_ids:
            # 選択したチームのメンバーの個人タスクを取得（archived=Falseのみ、期間フィルタなし）
            all_personal_tasks = Task.query.filter(
                Task.user_id.in_(member_ids),
                Task.archived == False
            ).all()
            
            # 統計を計算
            personal_total_tasks = len(all_personal_tasks)
            personal_completed_tasks = sum(1 for task in all_personal_tasks if task.completed)
            personal_progress_percentage = (personal_completed_tasks / personal_total_tasks * 100) if personal_total_tasks > 0 else 0
        else:
            personal_total_tasks = 0
            personal_completed_tasks = 0
            personal_progress_percentage = 0
    else:
        # チームが選択されていない場合は0
        personal_total_tasks = 0
        personal_completed_tasks = 0
        personal_progress_percentage = 0
    
    return render_template('team_management.html', 
                         user_teams=user_teams,
                         team_stats=team_stats,
                         personal_total_tasks=personal_total_tasks,
                         personal_completed_tasks=personal_completed_tasks,
                         personal_progress_percentage=personal_progress_percentage,
                         start_date=start_date,
                         end_date=end_date,
                         overall_total_tasks=overall_total_tasks,
                         overall_completed_tasks=overall_completed_tasks,
                         overall_progress=overall_progress,
                         total_teams=total_teams,
                         selected_team_id=selected_team_id)

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


@main.route('/personal/task-cards')
@login_required
def personal_task_cards():
    """個人向けタスクカードビュー"""
    return render_template('personal_task_cards.html')


@main.route('/team-mindmap')
@login_required
def team_mindmap():
    """チーム目標マインドマップ"""
    from models import Team, TeamMember
    
    # ユーザーが所属しているチームを取得
    user_teams = Team.query.join(TeamMember).filter(
        TeamMember.user_id == current_user.id
    ).all()
    
    selected_team_id = request.args.get('team_id', type=int)
    return render_template('team_mindmap.html', teams=user_teams, selected_team_id=selected_team_id)

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
        UserPerformance.date >= datetime.now(ZoneInfo('Asia/Tokyo')).date() - timedelta(days=7)
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
    from models import Team, TeamMember, TeamTask, User, Task
    from datetime import datetime, date, timedelta
    
    # チームの存在確認とアクセス権限チェック
    team = Team.query.get_or_404(team_id)
    membership = TeamMember.query.filter_by(
        team_id=team_id, 
        user_id=current_user.id
    ).first()
    
    if not membership:
        flash('このチームにアクセスする権限がありません', 'error')
        return redirect(url_for('main.team_management'))
    
    # 期間パラメータの取得（デフォルトは今日）
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = date.today()
    else:
        start_date = date.today()
    
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = date.today()
    else:
        end_date = date.today()
    
    # 期間内のチームタスクを取得（created_atでフィルタ）
    team_tasks_query = TeamTask.query.filter(
        TeamTask.team_id == team_id
    )
    
    # 期間内のチームタスクを取得
    team_tasks = team_tasks_query.filter(
        db.func.date(TeamTask.created_at) >= start_date,
        db.func.date(TeamTask.created_at) <= end_date
    ).order_by(TeamTask.order_index).all()
    
    # 期間内のチームタスクの完了済みタスク数
    completed_tasks = team_tasks_query.filter(
        db.func.date(TeamTask.created_at) >= start_date,
        db.func.date(TeamTask.created_at) <= end_date,
        TeamTask.completed == True
    ).count()
    
    # 総タスク数
    total_tasks = len(team_tasks)
    
    # 進捗率
    progress_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # チームメンバーを取得
    team_members = User.query.join(TeamMember).filter(
        TeamMember.team_id == team_id
    ).all()
    
    # メンバー別タスク数（チームタスク）
    member_stats = {}
    for member in team_members:
        assigned_tasks = TeamTask.query.filter(
            TeamTask.team_id == team_id,
            TeamTask.assigned_to == member.id,
            db.func.date(TeamTask.created_at) >= start_date,
            db.func.date(TeamTask.created_at) <= end_date
        ).count()
        completed_assigned = TeamTask.query.filter(
            TeamTask.team_id == team_id,
            TeamTask.assigned_to == member.id,
            TeamTask.completed == True,
            db.func.date(TeamTask.created_at) >= start_date,
            db.func.date(TeamTask.created_at) <= end_date
        ).count()
        
        member_stats[member.id] = {
            'assigned': assigned_tasks,
            'completed': completed_assigned,
            'completion_rate': (completed_assigned / assigned_tasks * 100) if assigned_tasks > 0 else 0
        }
    
    # チームメンバー全員の個人タスク（Task）の統計を取得
    member_user_ids = [member.id for member in team_members]
    
    # 期間内の個人タスクを取得
    personal_tasks = Task.query.filter(
        Task.user_id.in_(member_user_ids),
        Task.archived == False,
        db.func.date(Task.created_at) >= start_date,
        db.func.date(Task.created_at) <= end_date
    ).all()
    
    # 個人タスクの合計値
    personal_total_tasks = len(personal_tasks)
    personal_completed_tasks = sum(1 for task in personal_tasks if task.completed)
    personal_progress_percentage = (personal_completed_tasks / personal_total_tasks * 100) if personal_total_tasks > 0 else 0
    
    return render_template('team_dashboard.html',
                         team=team,
                         today_tasks=team_tasks,
                         completed_tasks=completed_tasks,
                         total_tasks=total_tasks,
                         progress_percentage=progress_percentage,
                         team_members=team_members,
                         member_stats=member_stats,
                         start_date=start_date,
                         end_date=end_date,
                         personal_total_tasks=personal_total_tasks,
                         personal_completed_tasks=personal_completed_tasks,
                         personal_progress_percentage=personal_progress_percentage)

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
    personal_task.completed_at = datetime.utcnow() if personal_task.completed else None
    
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


@main.route('/personal/task-cards/<int:node_id>')
@login_required
def personal_task_card_detail(node_id):
    """タスクカード詳細"""
    from models import Mindmap, MindmapNode, Task
    
    node = MindmapNode.query.get_or_404(node_id)
    mindmap_obj = Mindmap.query.get_or_404(node.mindmap_id)
    if mindmap_obj.user_id != current_user.id:
        flash('アクセス権限がありません', 'error')
        return redirect(url_for('main.personal_task_cards'))
    
    tasks = Task.query.filter_by(
        user_id=current_user.id,
        task_card_node_id=node.id,
        archived=False
    ).order_by(Task.completed, Task.category, Task.priority, Task.created_at.desc()).all()
    
    active_tasks = [task for task in tasks if not task.completed]
    completed_tasks = [task for task in tasks if task.completed]
    
    _update_task_card_progress(node.id)
    db.session.commit()
    
    return render_template(
        'personal_task_card_detail.html',
        card_node=node,
        mindmap=mindmap_obj,
        active_tasks=active_tasks,
        completed_tasks=completed_tasks
    )


@main.route('/personal/task-cards/<int:node_id>/tasks', methods=['POST'])
@login_required
def add_personal_task_card_task(node_id):
    """カード詳細からタスクを追加"""
    from models import Mindmap, MindmapNode, Task, UserPerformance
    mindmap_node = MindmapNode.query.get_or_404(node_id)
    mindmap_obj = Mindmap.query.get_or_404(mindmap_node.mindmap_id)
    if mindmap_obj.user_id != current_user.id:
        flash('アクセス権限がありません', 'error')
        return redirect(url_for('main.personal_task_cards'))
    
    title = (request.form.get('title') or '').strip()
    description = (request.form.get('description') or '').strip()
    due_date_str = request.form.get('due_date')
    priority = request.form.get('priority', 'medium')
    
    if not title:
        flash('タイトルを入力してください', 'error')
        return redirect(url_for('main.personal_task_card_detail', node_id=node_id))
    
    try:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None
    except ValueError:
        flash('完了予定日は YYYY-MM-DD 形式で入力してください', 'error')
        return redirect(url_for('main.personal_task_card_detail', node_id=node_id))
    
    start_date = due_date or datetime.now(ZoneInfo('Asia/Tokyo')).date()
    
    new_task = Task(
        title=title,
        description=description,
        user_id=current_user.id,
        category='other',
        priority=priority if priority in ['high', 'medium', 'low'] else 'medium',
        start_date=start_date,
        end_date=due_date or start_date,
        due_date=due_date,
        task_card_node_id=node_id
    )
    
    db.session.add(new_task)
    db.session.flush()
    
    mindmap_node.is_task = True
    if not mindmap_node.task_id:
        mindmap_node.task_id = new_task.id
    
    _update_task_card_progress(node_id)
    db.session.commit()
    
    UserPerformance.update_daily_performance(current_user.id)
    
    flash('タスクを追加しました', 'success')
    return redirect(url_for('main.personal_task_card_detail', node_id=node_id))

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
    from models import Mindmap, MindmapNode, Task, UserPerformance
    from zoneinfo import ZoneInfo
    
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
            card_tasks = Task.query.filter_by(
                user_id=current_user.id,
                task_card_node_id=node.id,
                archived=False
            ).all()
            total_card_tasks = len(card_tasks)
            completed_card_tasks = sum(1 for t in card_tasks if t.completed)
            calculated_progress = int(completed_card_tasks / total_card_tasks * 100) if total_card_tasks > 0 else 0
            if node.progress != calculated_progress:
                node.progress = calculated_progress
                db.session.add(node)

            nodes_data.append({
                'id': node.id,
                'parent_id': node.parent_id,
                'title': node.title,
                'description': node.description,
                'position_x': node.position_x,
                'position_y': node.position_y,
                'progress': calculated_progress,
                'completed': node.completed,
                'is_task': node.is_task,
                'due_date': node.due_date.isoformat() if node.due_date else None,
                'task_id': node.task_id,
                'task_completed': node.linked_task.completed if node.linked_task else False,
                'task_count': total_card_tasks,
                'completed_task_count': completed_card_tasks
            })
        
        db.session.commit()
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
        
        # 期日を設定
        due_date_str = data.get('due_date')
        if due_date_str:
            try:
                new_node.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                new_node.due_date = None
        
        db.session.add(new_node)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'node_id': new_node.id,
            'task_id': new_node.task_id
        })

@main.route('/personal/mindmap/nodes/<int:node_id>', methods=['PUT', 'DELETE'])
@login_required
def update_personal_mindmap_node(node_id):
    """個人マインドマップノードの更新・削除"""
    from models import Mindmap, MindmapNode, Task, UserPerformance
    from zoneinfo import ZoneInfo
    
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
        if 'due_date' in data:
            due_date_str = data['due_date']
            if due_date_str:
                try:
                    node.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                except ValueError:
                    node.due_date = None
            else:
                node.due_date = None
        
        # is_taskが変更された場合の処理
        if 'is_task' in data:
            is_task = data['is_task']
            
            # is_taskがTrueになった場合、個人タスクを作成
            if is_task and not node.task_id:
                new_task = Task(
                    title=node.title,
                    description=node.description or '',
                    user_id=current_user.id,
                    category='other',
                    priority='medium',
                    completed=False,
                    start_date=node.due_date,
                    end_date=node.due_date
                )
                db.session.add(new_task)
                db.session.flush()
                node.task_id = new_task.id
                
                # パフォーマンス更新
                UserPerformance.update_daily_performance(current_user.id)
            
            # is_taskがFalseになった場合、リンクされたタスクを削除
            elif not is_task:
                linked_tasks = Task.query.filter_by(task_card_node_id=node.id).all()
                for linked in linked_tasks:
                    db.session.delete(linked)
                node.task_id = None
                UserPerformance.update_daily_performance(current_user.id)
            
            node.is_task = is_task
        
        # 既存のタスクがリンクされている場合、タスクも更新
        if node.task_id:
            task = Task.query.get(node.task_id)
            if task:
                if 'title' in data:
                    task.title = data['title']
                if 'description' in data:
                    task.description = data.get('description', '')
                if 'due_date' in data:
                    task.start_date = node.due_date
                    task.end_date = node.due_date
                if 'completed' in data:
                    task.completed = data['completed']
                    task.completed_at = datetime.now(ZoneInfo('Asia/Tokyo')).replace(tzinfo=None) if task.completed else None
                
                # パフォーマンス更新
                UserPerformance.update_daily_performance(current_user.id)
        
        node.updated_at = datetime.utcnow()
        _update_task_card_progress(node.id)
        db.session.commit()
        
        return jsonify({'success': True, 'task_id': node.task_id})
    
    elif request.method == 'DELETE':
        # ノード削除時、リンクされたタスクも削除
        linked_tasks = Task.query.filter_by(task_card_node_id=node.id).all()
        for linked in linked_tasks:
            db.session.delete(linked)
        
        db.session.delete(node)
        db.session.commit()
        UserPerformance.update_daily_performance(current_user.id)
        
        return jsonify({'success': True})


@main.route('/personal/mindmap/nodes/<int:node_id>/create-task', methods=['POST'])
@login_required
def create_task_from_personal_card(node_id):
    """タスクカードから個人タスクを作成"""
    from models import Mindmap, MindmapNode, Task, UserPerformance
    from zoneinfo import ZoneInfo
    
    node = MindmapNode.query.get_or_404(node_id)
    mindmap_obj = Mindmap.query.filter_by(id=node.mindmap_id, user_id=current_user.id).first()
    if not mindmap_obj:
        return jsonify({'error': '権限がありません'}), 403
    
    data = request.get_json() or {}
    category = data.get('category', '').strip().lower()
    priority = data.get('priority', '').strip().lower()
    
    if category not in ['today', 'tomorrow', 'other']:
        # 期日に応じて自動判定
        today = date.today()
        if node.due_date == today:
            category = 'today'
        elif node.due_date == today + timedelta(days=1):
            category = 'tomorrow'
        else:
            category = 'other'
    
    if priority not in ['high', 'medium', 'low']:
        priority = 'medium'
    
    start_date = node.due_date or date.today()
    end_date = start_date
    
    new_task = Task(
        title=node.title or '新しいタスク',
        description=node.description or '',
        user_id=current_user.id,
        category=category,
        priority=priority,
        completed=False,
        start_date=start_date,
        end_date=end_date,
        task_card_node_id=node.id
    )
    
    db.session.add(new_task)
    db.session.flush()
    
    node.is_task = True
    if not node.task_id:
        node.task_id = new_task.id
    _update_task_card_progress(node.id)
    db.session.commit()

    UserPerformance.update_daily_performance(current_user.id)
    
    return jsonify({
        'success': True,
        'task_id': new_task.id
    })

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

@main.route('/admin/reset-password', methods=['POST'])
@login_required
def reset_password():
    """パスワードリセット（管理者のみ）"""
    from models import User
    
    # 管理者権限チェック
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '管理者権限が必要です'}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    new_password = data.get('new_password', '').strip()
    
    # バリデーション
    if not user_id or not new_password:
        return jsonify({'success': False, 'message': 'ユーザーIDと新しいパスワードを入力してください'}), 400
    
    if len(new_password) < 4:
        return jsonify({'success': False, 'message': 'パスワードは4文字以上で入力してください'}), 400
    
    # ユーザー取得
    user = User.query.get_or_404(user_id)
    
    # パスワードを設定
    user.set_password(new_password)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'ユーザー「{user.username}」のパスワードをリセットしました'
    })

@main.route('/admin/delete-user', methods=['POST'])
@login_required
def delete_user():
    """ユーザー削除（管理者のみ）"""
    from models import User, Task, TeamMember, Team, Notification, ConversationSession
    
    # 管理者権限チェック
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '管理者権限が必要です'}), 403
    
    data = request.get_json()
    user_id = data.get('user_id')
    
    # バリデーション
    if not user_id:
        return jsonify({'success': False, 'message': 'ユーザーIDを指定してください'}), 400
    
    # 自分自身は削除できない
    if user_id == current_user.id:
        return jsonify({'success': False, 'message': '自分自身を削除することはできません'}), 400
    
    # ユーザー取得
    user = User.query.get_or_404(user_id)
    username = user.username
    
    # ユーザーに関連するデータを削除（cascadeで自動削除されるものも多いが、明示的に削除）
    # Taskはcascadeで自動削除される
    # TeamMemberは削除
    TeamMember.query.filter_by(user_id=user_id).delete()
    
    # 自分が作成したチームがある場合、チームも削除（cascadeで自動削除）
    Team.query.filter_by(created_by=user_id).delete()
    
    # Notificationを削除
    Notification.query.filter_by(user_id=user_id).delete()
    
    # ConversationSessionとその関連データはcascadeで自動削除される
    
    # ユーザーを削除
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'ユーザー「{username}」を削除しました'
    })

@main.route('/admin/export-data', methods=['GET'])
@login_required
def export_data():
    """全データをエクスポート（管理者のみ）"""
    from models import (
        User, Task, UserPerformance, Team, TeamMember, TeamTask, TaskAssignee,
        Mindmap, MindmapNode, TaskTemplate, Notification,
        ConversationSession, ConversationMessage, SuggestedTask
    )
    from flask import make_response
    import json
    from datetime import datetime
    
    # 管理者権限チェック
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '管理者権限が必要です'}), 403
    
    # 全データを取得してJSON形式に変換
    export_data = {
        'version': '1.0',
        'exported_at': datetime.utcnow().isoformat(),
        'data': {}
    }
    
    # User（独立）
    users = User.query.all()
    export_data['data']['users'] = [{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'password_hash': u.password_hash,
        'is_admin': u.is_admin,
        'display_name': u.display_name,
        'bio': u.bio,
        'created_at': u.created_at.isoformat() if u.created_at else None
    } for u in users]
    
    # Team（Userに依存）
    teams = Team.query.all()
    export_data['data']['teams'] = [{
        'id': t.id,
        'name': t.name,
        'description': t.description,
        'created_by': t.created_by,
        'created_at': t.created_at.isoformat() if t.created_at else None
    } for t in teams]
    
    # TeamMember（User, Teamに依存）
    team_members = TeamMember.query.all()
    export_data['data']['team_members'] = [{
        'id': tm.id,
        'team_id': tm.team_id,
        'user_id': tm.user_id,
        'role': tm.role,
        'joined_at': tm.joined_at.isoformat() if tm.joined_at else None
    } for tm in team_members]
    
    # Mindmap（User, Teamに依存）
    mindmaps = Mindmap.query.all()
    export_data['data']['mindmaps'] = [{
        'id': m.id,
        'team_id': m.team_id,
        'user_id': m.user_id,
        'name': m.name,
        'description': m.description,
        'date': m.date.isoformat() if m.date else None,
        'created_by': m.created_by,
        'created_at': m.created_at.isoformat() if m.created_at else None,
        'updated_at': m.updated_at.isoformat() if m.updated_at else None
    } for m in mindmaps]
    
    # UserPerformance（Userに依存）
    user_performances = UserPerformance.query.all()
    export_data['data']['user_performances'] = [{
        'id': up.id,
        'user_id': up.user_id,
        'date': up.date.isoformat() if up.date else None,
        'tasks_completed': up.tasks_completed,
        'tasks_created': up.tasks_created,
        'completion_rate': up.completion_rate,
        'streak_days': up.streak_days,
        'total_work_seconds': up.total_work_seconds,
        'created_at': up.created_at.isoformat() if up.created_at else None,
        'updated_at': up.updated_at.isoformat() if up.updated_at else None
    } for up in user_performances]
    
    # TaskTemplate（Userに依存）
    task_templates = TaskTemplate.query.all()
    export_data['data']['task_templates'] = [{
        'id': tt.id,
        'user_id': tt.user_id,
        'title': tt.title,
        'description': tt.description,
        'priority': tt.priority,
        'category': tt.category,
        'repeat_type': tt.repeat_type,
        'is_active': tt.is_active,
        'created_at': tt.created_at.isoformat() if tt.created_at else None
    } for tt in task_templates]
    
    # TeamTask（Team, User, MindmapNodeに依存）
    team_tasks = TeamTask.query.all()
    export_data['data']['team_tasks'] = [{
        'id': tt.id,
        'team_id': tt.team_id,
        'title': tt.title,
        'description': tt.description,
        'completed': tt.completed,
        'due_date': tt.due_date.isoformat() if tt.due_date else None,
        'priority': tt.priority,
        'category': tt.category,
        'order_index': tt.order_index,
        'assigned_to': tt.assigned_to,
        'created_by': tt.created_by,
        'parent_node_id': tt.parent_node_id,
        'created_at': tt.created_at.isoformat() if tt.created_at else None,
        'updated_at': tt.updated_at.isoformat() if tt.updated_at else None
    } for tt in team_tasks]
    
    # MindmapNode（Mindmap, TeamTask, Taskに依存）
    mindmap_nodes = MindmapNode.query.all()
    export_data['data']['mindmap_nodes'] = [{
        'id': mn.id,
        'mindmap_id': mn.mindmap_id,
        'parent_id': mn.parent_id,
        'title': mn.title,
        'description': mn.description,
        'position_x': mn.position_x,
        'position_y': mn.position_y,
        'completed': mn.completed,
        'progress': mn.progress,
        'due_date': mn.due_date.isoformat() if mn.due_date else None,
        'is_task': mn.is_task,
        'team_task_id': mn.team_task_id,
        'task_id': mn.task_id,
        'created_at': mn.created_at.isoformat() if mn.created_at else None,
        'updated_at': mn.updated_at.isoformat() if mn.updated_at else None
    } for mn in mindmap_nodes]
    
    # Task（User, TeamTaskに依存）
    tasks = Task.query.all()
    export_data['data']['tasks'] = [{
        'id': t.id,
        'user_id': t.user_id,
        'title': t.title,
        'description': t.description,
        'completed': t.completed,
        'due_date': t.due_date.isoformat() if t.due_date else None,
        'start_date': t.start_date.isoformat() if t.start_date else None,
        'end_date': t.end_date.isoformat() if t.end_date else None,
        'priority': t.priority,
        'category': t.category,
        'order_index': t.order_index,
        'archived': t.archived,
        'archived_at': t.archived_at.isoformat() if t.archived_at else None,
        'is_tracking': t.is_tracking,
        'tracking_start_time': t.tracking_start_time.isoformat() if t.tracking_start_time else None,
        'total_seconds': t.total_seconds,
        'team_task_id': t.team_task_id,
        'completed_at': t.completed_at.isoformat() if t.completed_at else None,
        'created_at': t.created_at.isoformat() if t.created_at else None,
        'updated_at': t.updated_at.isoformat() if t.updated_at else None
    } for t in tasks]
    
    # TaskAssignee（TeamTask, Userに依存）
    task_assignees = TaskAssignee.query.all()
    export_data['data']['task_assignees'] = [{
        'id': ta.id,
        'team_task_id': ta.team_task_id,
        'user_id': ta.user_id,
        'completed': ta.completed,
        'completed_at': ta.completed_at.isoformat() if ta.completed_at else None,
        'created_at': ta.created_at.isoformat() if ta.created_at else None
    } for ta in task_assignees]
    
    # Notification（User, Teamに依存）
    notifications = Notification.query.all()
    export_data['data']['notifications'] = [{
        'id': n.id,
        'user_id': n.user_id,
        'title': n.title,
        'message': n.message,
        'notification_type': n.notification_type,
        'read': n.read,
        'related_team_id': n.related_team_id,
        'related_task_id': n.related_task_id,
        'created_at': n.created_at.isoformat() if n.created_at else None
    } for n in notifications]
    
    # ConversationSession（Userに依存）
    conversation_sessions = ConversationSession.query.all()
    export_data['data']['conversation_sessions'] = [{
        'id': cs.id,
        'user_id': cs.user_id,
        'title': cs.title,
        'goal': cs.goal,
        'created_at': cs.created_at.isoformat() if cs.created_at else None,
        'updated_at': cs.updated_at.isoformat() if cs.updated_at else None
    } for cs in conversation_sessions]
    
    # ConversationMessage（ConversationSessionに依存）
    conversation_messages = ConversationMessage.query.all()
    export_data['data']['conversation_messages'] = [{
        'id': cm.id,
        'session_id': cm.session_id,
        'role': cm.role,
        'content': cm.content,
        'created_at': cm.created_at.isoformat() if cm.created_at else None
    } for cm in conversation_messages]
    
    # SuggestedTask（ConversationSessionに依存）
    suggested_tasks = SuggestedTask.query.all()
    export_data['data']['suggested_tasks'] = [{
        'id': st.id,
        'session_id': st.session_id,
        'title': st.title,
        'description': st.description,
        'priority': st.priority,
        'suggested_date': st.suggested_date.isoformat() if st.suggested_date else None,
        'is_created': st.is_created,
        'created_at': st.created_at.isoformat() if st.created_at else None
    } for st in suggested_tasks]
    
    # JSON文字列に変換
    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
    
    # ファイル名を生成（日時を含める）
    filename = f"atd_backup_{datetime.now(ZoneInfo('Asia/Tokyo')).strftime('%Y%m%d_%H%M%S')}.json"
    
    # レスポンスを作成
    response = make_response(json_str)
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response

@main.route('/admin/import-data', methods=['POST'])
@login_required
def import_data():
    """データをインポート（管理者のみ）"""
    from models import (
        User, Task, UserPerformance, Team, TeamMember, TeamTask, TaskAssignee,
        Mindmap, MindmapNode, TaskTemplate, Notification,
        ConversationSession, ConversationMessage, SuggestedTask
    )
    import json
    from datetime import datetime
    
    # 管理者権限チェック
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '管理者権限が必要です'}), 403
    
    # ファイルがアップロードされているか確認
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'ファイルが選択されていません'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'ファイルが選択されていません'}), 400
    
    # ファイルを読み込む
    try:
        file_content = file.read().decode('utf-8')
        import_data = json.loads(file_content)
    except json.JSONDecodeError:
        return jsonify({'success': False, 'message': 'JSONファイルの形式が正しくありません'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'ファイルの読み込みに失敗しました: {str(e)}'}), 400
    
    # バージョンチェック
    if 'version' not in import_data or 'data' not in import_data:
        return jsonify({'success': False, 'message': '不正なバックアップファイルです'}), 400
    
    try:
        # 既存データを削除（外部キー制約を考慮して順序よく削除）
        # 依存関係の逆順で削除
        SuggestedTask.query.delete()
        ConversationMessage.query.delete()
        ConversationSession.query.delete()
        Notification.query.delete()
        TaskAssignee.query.delete()
        MindmapNode.query.delete()
        Task.query.delete()
        TeamTask.query.delete()
        TaskTemplate.query.delete()
        UserPerformance.query.delete()
        TeamMember.query.delete()
        Mindmap.query.delete()
        Team.query.delete()
        User.query.delete()
        
        db.session.commit()
        
        # IDマッピング（旧ID -> 新ID）
        id_mapping = {
            'users': {},
            'teams': {},
            'mindmaps': {},
            'team_tasks': {},
            'mindmap_nodes': {},
            'tasks': {},
            'conversation_sessions': {}
        }
        
        # データをインポート（依存関係を考慮して順序よく）
        data = import_data['data']
        
        # 1. User（独立）
        for user_data in data.get('users', []):
            old_id = user_data['id']
            new_user = User(
                username=user_data['username'],
                email=user_data['email'],
                password_hash=user_data['password_hash'],
                is_admin=user_data.get('is_admin', False),
                display_name=user_data.get('display_name'),
                bio=user_data.get('bio')
            )
            if user_data.get('created_at'):
                new_user.created_at = datetime.fromisoformat(user_data['created_at'].replace('Z', '+00:00'))
            db.session.add(new_user)
            db.session.flush()  # IDを取得
            id_mapping['users'][old_id] = new_user.id
        
        # 2. Team（Userに依存）
        for team_data in data.get('teams', []):
            old_id = team_data['id']
            new_team = Team(
                name=team_data['name'],
                description=team_data.get('description'),
                created_by=id_mapping['users'].get(team_data['created_by'], team_data['created_by'])
            )
            if team_data.get('created_at'):
                new_team.created_at = datetime.fromisoformat(team_data['created_at'].replace('Z', '+00:00'))
            db.session.add(new_team)
            db.session.flush()
            id_mapping['teams'][old_id] = new_team.id
        
        # 3. TeamMember（User, Teamに依存）
        for tm_data in data.get('team_members', []):
            new_tm = TeamMember(
                team_id=id_mapping['teams'].get(tm_data['team_id'], tm_data['team_id']),
                user_id=id_mapping['users'].get(tm_data['user_id'], tm_data['user_id']),
                role=tm_data.get('role', 'member')
            )
            if tm_data.get('joined_at'):
                new_tm.joined_at = datetime.fromisoformat(tm_data['joined_at'].replace('Z', '+00:00'))
            db.session.add(new_tm)
        
        # 4. Mindmap（User, Teamに依存）
        for mindmap_data in data.get('mindmaps', []):
            old_id = mindmap_data['id']
            new_mindmap = Mindmap(
                team_id=id_mapping['teams'].get(mindmap_data['team_id']) if mindmap_data.get('team_id') else None,
                user_id=id_mapping['users'].get(mindmap_data['user_id']) if mindmap_data.get('user_id') else None,
                name=mindmap_data['name'],
                description=mindmap_data.get('description'),
                created_by=id_mapping['users'].get(mindmap_data['created_by'], mindmap_data['created_by'])
            )
            if mindmap_data.get('date'):
                from datetime import date as date_class
                new_mindmap.date = date_class.fromisoformat(mindmap_data['date'])
            if mindmap_data.get('created_at'):
                new_mindmap.created_at = datetime.fromisoformat(mindmap_data['created_at'].replace('Z', '+00:00'))
            if mindmap_data.get('updated_at'):
                new_mindmap.updated_at = datetime.fromisoformat(mindmap_data['updated_at'].replace('Z', '+00:00'))
            db.session.add(new_mindmap)
            db.session.flush()
            id_mapping['mindmaps'][old_id] = new_mindmap.id
        
        # 5. UserPerformance（Userに依存）
        for up_data in data.get('user_performances', []):
            from datetime import date as date_class
            new_up = UserPerformance(
                user_id=id_mapping['users'].get(up_data['user_id'], up_data['user_id']),
                date=date_class.fromisoformat(up_data['date']) if up_data.get('date') else None,
                tasks_completed=up_data.get('tasks_completed', 0),
                tasks_created=up_data.get('tasks_created', 0),
                completion_rate=up_data.get('completion_rate', 0.0),
                streak_days=up_data.get('streak_days', 0),
                total_work_seconds=up_data.get('total_work_seconds', 0)
            )
            if up_data.get('created_at'):
                new_up.created_at = datetime.fromisoformat(up_data['created_at'].replace('Z', '+00:00'))
            if up_data.get('updated_at'):
                new_up.updated_at = datetime.fromisoformat(up_data['updated_at'].replace('Z', '+00:00'))
            db.session.add(new_up)
        
        # 6. TaskTemplate（Userに依存）
        for tt_data in data.get('task_templates', []):
            new_tt = TaskTemplate(
                user_id=id_mapping['users'].get(tt_data['user_id'], tt_data['user_id']),
                title=tt_data['title'],
                description=tt_data.get('description'),
                priority=tt_data.get('priority', 'medium'),
                category=tt_data.get('category', 'today'),
                repeat_type=tt_data.get('repeat_type'),
                is_active=tt_data.get('is_active', True)
            )
            if tt_data.get('created_at'):
                new_tt.created_at = datetime.fromisoformat(tt_data['created_at'].replace('Z', '+00:00'))
            db.session.add(new_tt)
        
        # 7. TeamTask（Team, Userに依存。parent_node_idは後で更新）
        # TeamTaskとMindmapNodeの循環参照を解決するため、まずTeamTaskを作成（parent_node_idはNone）
        team_task_parent_mapping = {}  # 旧TeamTask ID -> 旧parent_node_id
        for tt_data in data.get('team_tasks', []):
            old_id = tt_data['id']
            old_parent_node_id = tt_data.get('parent_node_id')
            if old_parent_node_id:
                team_task_parent_mapping[old_id] = old_parent_node_id
            
            from datetime import date as date_class
            new_tt = TeamTask(
                team_id=id_mapping['teams'].get(tt_data['team_id'], tt_data['team_id']),
                title=tt_data['title'],
                description=tt_data.get('description'),
                completed=tt_data.get('completed', False),
                due_date=date_class.fromisoformat(tt_data['due_date']) if tt_data.get('due_date') else None,
                priority=tt_data.get('priority', 'medium'),
                category=tt_data.get('category', 'other'),
                order_index=tt_data.get('order_index', 0),
                assigned_to=id_mapping['users'].get(tt_data['assigned_to']) if tt_data.get('assigned_to') else None,
                created_by=id_mapping['users'].get(tt_data['created_by'], tt_data['created_by']),
                parent_node_id=None  # 一時的にNone（後で更新）
            )
            if tt_data.get('created_at'):
                new_tt.created_at = datetime.fromisoformat(tt_data['created_at'].replace('Z', '+00:00'))
            if tt_data.get('updated_at'):
                new_tt.updated_at = datetime.fromisoformat(tt_data['updated_at'].replace('Z', '+00:00'))
            db.session.add(new_tt)
            db.session.flush()
            id_mapping['team_tasks'][old_id] = new_tt.id
        
        # 8. MindmapNode（Mindmap, TeamTaskに依存。Taskは後で更新）
        for mn_data in data.get('mindmap_nodes', []):
            old_id = mn_data['id']
            from datetime import date as date_class
            new_mn = MindmapNode(
                mindmap_id=id_mapping['mindmaps'].get(mn_data['mindmap_id'], mn_data['mindmap_id']),
                parent_id=None,  # 一時的にNone（後で更新）
                title=mn_data['title'],
                description=mn_data.get('description'),
                position_x=mn_data.get('position_x', 0.0),
                position_y=mn_data.get('position_y', 0.0),
                completed=mn_data.get('completed', False),
                progress=mn_data.get('progress', 0),
                due_date=date_class.fromisoformat(mn_data['due_date']) if mn_data.get('due_date') else None,
                is_task=mn_data.get('is_task', False),
                team_task_id=id_mapping['team_tasks'].get(mn_data['team_task_id']) if mn_data.get('team_task_id') else None,
                task_id=None  # 一時的にNone（後で更新）
            )
            if mn_data.get('created_at'):
                new_mn.created_at = datetime.fromisoformat(mn_data['created_at'].replace('Z', '+00:00'))
            if mn_data.get('updated_at'):
                new_mn.updated_at = datetime.fromisoformat(mn_data['updated_at'].replace('Z', '+00:00'))
            db.session.add(new_mn)
            db.session.flush()
            id_mapping['mindmap_nodes'][old_id] = new_mn.id
        
        # 8.5. MindmapNodeのparent_idとtask_idを更新
        for mn_data in data.get('mindmap_nodes', []):
            old_id = mn_data['id']
            new_mn_id = id_mapping['mindmap_nodes'][old_id]
            new_mn = MindmapNode.query.get(new_mn_id)
            if new_mn:
                if mn_data.get('parent_id'):
                    new_mn.parent_id = id_mapping['mindmap_nodes'].get(mn_data['parent_id'])
                if mn_data.get('task_id'):
                    new_mn.task_id = id_mapping['tasks'].get(mn_data['task_id'])
        
        # 8.6. TeamTaskのparent_node_idを更新
        for old_tt_id, old_parent_node_id in team_task_parent_mapping.items():
            new_tt_id = id_mapping['team_tasks'].get(old_tt_id)
            if new_tt_id:
                new_tt = TeamTask.query.get(new_tt_id)
                if new_tt:
                    new_tt.parent_node_id = id_mapping['mindmap_nodes'].get(old_parent_node_id)
        
        # 9. Task（User, TeamTaskに依存）
        for task_data in data.get('tasks', []):
            old_id = task_data['id']
            from datetime import date as date_class
            new_task = Task(
                user_id=id_mapping['users'].get(task_data['user_id'], task_data['user_id']),
                title=task_data['title'],
                description=task_data.get('description'),
                completed=task_data.get('completed', False),
                due_date=date_class.fromisoformat(task_data['due_date']) if task_data.get('due_date') else None,
                start_date=date_class.fromisoformat(task_data['start_date']) if task_data.get('start_date') else None,
                end_date=date_class.fromisoformat(task_data['end_date']) if task_data.get('end_date') else None,
                priority=task_data.get('priority', 'medium'),
                category=task_data.get('category', 'other'),
                order_index=task_data.get('order_index', 0),
                archived=task_data.get('archived', False),
                archived_at=date_class.fromisoformat(task_data['archived_at']) if task_data.get('archived_at') else None,
                is_tracking=task_data.get('is_tracking', False),
                tracking_start_time=datetime.fromisoformat(task_data['tracking_start_time'].replace('Z', '+00:00')) if task_data.get('tracking_start_time') else None,
                total_seconds=task_data.get('total_seconds', 0),
                team_task_id=id_mapping['team_tasks'].get(task_data['team_task_id']) if task_data.get('team_task_id') else None
            )
            if task_data.get('created_at'):
                new_task.created_at = datetime.fromisoformat(task_data['created_at'].replace('Z', '+00:00'))
            if task_data.get('updated_at'):
                new_task.updated_at = datetime.fromisoformat(task_data['updated_at'].replace('Z', '+00:00'))
            if task_data.get('completed_at'):
                new_task.completed_at = datetime.fromisoformat(task_data['completed_at'].replace('Z', '+00:00'))
            db.session.add(new_task)
            db.session.flush()
            id_mapping['tasks'][old_id] = new_task.id
        
        # 10. TaskAssignee（TeamTask, Userに依存）
        for ta_data in data.get('task_assignees', []):
            new_ta = TaskAssignee(
                team_task_id=id_mapping['team_tasks'].get(ta_data['team_task_id'], ta_data['team_task_id']),
                user_id=id_mapping['users'].get(ta_data['user_id'], ta_data['user_id']),
                completed=ta_data.get('completed', False),
                completed_at=datetime.fromisoformat(ta_data['completed_at'].replace('Z', '+00:00')) if ta_data.get('completed_at') else None
            )
            if ta_data.get('created_at'):
                new_ta.created_at = datetime.fromisoformat(ta_data['created_at'].replace('Z', '+00:00'))
            db.session.add(new_ta)
        
        # 11. Notification（User, Teamに依存）
        for n_data in data.get('notifications', []):
            new_n = Notification(
                user_id=id_mapping['users'].get(n_data['user_id'], n_data['user_id']),
                title=n_data['title'],
                message=n_data['message'],
                notification_type=n_data.get('notification_type', 'info'),
                read=n_data.get('read', False),
                related_team_id=id_mapping['teams'].get(n_data['related_team_id']) if n_data.get('related_team_id') else None,
                related_task_id=id_mapping['tasks'].get(n_data['related_task_id']) if n_data.get('related_task_id') else None
            )
            if n_data.get('created_at'):
                new_n.created_at = datetime.fromisoformat(n_data['created_at'].replace('Z', '+00:00'))
            db.session.add(new_n)
        
        # 12. ConversationSession（Userに依存）
        for cs_data in data.get('conversation_sessions', []):
            old_id = cs_data['id']
            new_cs = ConversationSession(
                user_id=id_mapping['users'].get(cs_data['user_id'], cs_data['user_id']),
                title=cs_data.get('title'),
                goal=cs_data.get('goal')
            )
            if cs_data.get('created_at'):
                new_cs.created_at = datetime.fromisoformat(cs_data['created_at'].replace('Z', '+00:00'))
            if cs_data.get('updated_at'):
                new_cs.updated_at = datetime.fromisoformat(cs_data['updated_at'].replace('Z', '+00:00'))
            db.session.add(new_cs)
            db.session.flush()
            id_mapping['conversation_sessions'][old_id] = new_cs.id
        
        # 13. ConversationMessage（ConversationSessionに依存）
        for cm_data in data.get('conversation_messages', []):
            new_cm = ConversationMessage(
                session_id=id_mapping['conversation_sessions'].get(cm_data['session_id'], cm_data['session_id']),
                role=cm_data['role'],
                content=cm_data['content']
            )
            if cm_data.get('created_at'):
                new_cm.created_at = datetime.fromisoformat(cm_data['created_at'].replace('Z', '+00:00'))
            db.session.add(new_cm)
        
        # 14. SuggestedTask（ConversationSessionに依存）
        for st_data in data.get('suggested_tasks', []):
            from datetime import date as date_class
            new_st = SuggestedTask(
                session_id=id_mapping['conversation_sessions'].get(st_data['session_id'], st_data['session_id']),
                title=st_data['title'],
                description=st_data.get('description'),
                priority=st_data.get('priority', 'medium'),
                suggested_date=date_class.fromisoformat(st_data['suggested_date']) if st_data.get('suggested_date') else None,
                is_created=st_data.get('is_created', False)
            )
            if st_data.get('created_at'):
                new_st.created_at = datetime.fromisoformat(st_data['created_at'].replace('Z', '+00:00'))
            db.session.add(new_st)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'データのインポートが完了しました'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'インポート中にエラーが発生しました: {str(e)}'
        }), 500

# ===== 壁打ち機能 =====

@main.route('/brainstorm')
@login_required
def brainstorm():
    """壁打ちページ（一括作成）"""
    from models import ConversationSession
    
    # new_session=1パラメータがあったら新しいセッションを作成
    new_session_flag = request.args.get('new_session', '0') == '1'
    
    if new_session_flag:
        # 新しいセッションを作成（会話履歴なし）
        latest_session = None
    else:
        # 最新のセッションを取得（なければNone）
        latest_session = ConversationSession.query.filter_by(
            user_id=current_user.id
        ).order_by(ConversationSession.created_at.desc()).first()
    
    return render_template('brainstorm.html', session=latest_session, is_new_session=new_session_flag)


@main.route('/brainstorm/session/create', methods=['POST'])
@login_required
def create_brainstorm_session():
    """新しい壁打ちセッションを作成"""
    from models import ConversationSession, db
    
    data = request.get_json()
    goal = data.get('goal', '').strip()
    
    # 新しいセッションを作成
    new_session = ConversationSession(
        user_id=current_user.id,
        goal=goal,
        title=goal[:50] if goal else '新しい壁打ち'
    )
    
    db.session.add(new_session)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'session_id': new_session.id,
        'message': '新しいセッションを作成しました'
    })


@main.route('/brainstorm/session/<int:session_id>/message', methods=['POST'])
@login_required
def add_brainstorm_message(session_id):
    """会話メッセージを追加"""
    from models import ConversationSession, ConversationMessage, SuggestedTask, db
    from brainstorm import suggest_tasks_from_conversation, generate_response_message, extract_date_from_text
    
    # セッションの確認
    session = ConversationSession.query.filter_by(
        id=session_id,
        user_id=current_user.id
    ).first_or_404()
    
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'success': False, 'message': 'メッセージを入力してください'}), 400
    
    # ユーザーメッセージを保存
    user_msg = ConversationMessage(
        session_id=session_id,
        role='user',
        content=user_message
    )
    db.session.add(user_msg)
    db.session.flush()
    
    # ルールベースでタスク指示を解析（柔軟な会話は不要）
    messages = session.messages
    
    # 「このタスクを○日間分入れてください」などの指示を解析
    from brainstorm import parse_task_instruction
    from models import Task
    
    # 指示を解析
    instruction = parse_task_instruction(user_message, messages + [user_msg], session.goal)
    
    # タスク作成指示がある場合
    if instruction and instruction.get('create_tasks'):
        # 直接タスクを作成
        task_title = instruction.get('task_title', 'タスク')
        days = instruction.get('days', 0)
        months = instruction.get('months', 0)
        start_date = instruction.get('start_date')
        
        created_tasks = []
        from datetime import date, timedelta
        from dateutil.relativedelta import relativedelta
        
        if months > 0:
            # 月単位で日割り
            if not start_date:
                start_date = date.today()
            from calendar import monthrange
            for i in range(months):
                month_start = start_date + relativedelta(months=i)
                # 月の日数を計算
                days_in_month = monthrange(month_start.year, month_start.month)[1]
                
                for day in range(days_in_month):
                    task_date = month_start + timedelta(days=day)
                    new_task = Task(
                        user_id=current_user.id,
                        title=f"{task_title} (Day {day+1})" if days_in_month > 1 else task_title,
                        description=session.goal if session.goal else '',
                        priority='medium',
                        category='today' if task_date == date.today() else 'other',
                        start_date=task_date,
                        end_date=task_date
                    )
                    db.session.add(new_task)
                    created_tasks.append(new_task)
        elif days > 0:
            # 日単位で日割り
            if not start_date:
                start_date = date.today()
            for i in range(days):
                task_date = start_date + timedelta(days=i)
                new_task = Task(
                    user_id=current_user.id,
                    title=f"{task_title} (Day {i+1})" if days > 1 else task_title,
                    description=session.goal if session.goal else '',
                    priority='medium',
                    category='today' if task_date == date.today() else 'other',
                    start_date=task_date,
                    end_date=task_date
                )
                db.session.add(new_task)
                created_tasks.append(new_task)
        else:
            # 単一タスク
            task_date = start_date or date.today()
            new_task = Task(
                user_id=current_user.id,
                title=task_title,
                description=session.goal if session.goal else '',
                priority='medium',
                category='today' if task_date == date.today() else 'other',
                start_date=task_date,
                end_date=task_date
            )
            db.session.add(new_task)
            created_tasks.append(new_task)
        
        db.session.commit()
        
        # 返答を生成
        if len(created_tasks) > 1:
            assistant_response = f"{len(created_tasks)}件のタスクをカレンダーに追加しました。"
        else:
            assistant_response = f"タスク「{task_title}」をカレンダーに追加しました。"
        
        # アシスタントメッセージを保存
        assistant_msg = ConversationMessage(
            session_id=session_id,
            role='assistant',
            content=assistant_response
        )
        db.session.add(assistant_msg)
        session.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'assistant_message': assistant_response,
            'tasks_created': len(created_tasks),
            'redirect': '/tasks'  # タスク一覧にリダイレクト
        })
    
    # 通常のタスク提案（指示がない場合）
    from brainstorm import suggest_tasks_from_conversation, generate_response_message
    suggested_tasks = suggest_tasks_from_conversation(messages + [user_msg], session.goal)
    has_tasks = len(suggested_tasks) > 0
    task_count = len(suggested_tasks)
    assistant_response = generate_response_message(
        user_message,
        session.goal,
        messages,
        has_suggested_tasks=has_tasks,
        suggested_task_count=task_count
    )
    
    # 既存の提案タスクを削除（更新するため）
    SuggestedTask.query.filter_by(session_id=session_id, is_created=False).delete()
    
    # 新しい提案タスクを保存
    suggested_task_objects = []
    for task_data in suggested_tasks:
        suggested_task = SuggestedTask(
            session_id=session_id,
            title=task_data['title'],
            description=task_data.get('description', ''),
            priority=task_data.get('priority', 'medium'),
            suggested_date=task_data.get('suggested_date')
        )
        db.session.add(suggested_task)
        suggested_task_objects.append(suggested_task)
    
    db.session.flush()  # タスクIDを取得するため
    
    # アシスタントメッセージを保存
    assistant_msg = ConversationMessage(
        session_id=session_id,
        role='assistant',
        content=assistant_response
    )
    db.session.add(assistant_msg)
    
    session.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'assistant_message': assistant_response,
        'suggested_tasks': [
            {
                'id': t.id,
                'title': t.title,
                'description': t.description,
                'priority': t.priority,
                'suggested_date': t.suggested_date.isoformat() if t.suggested_date else None
            }
            for t in SuggestedTask.query.filter_by(session_id=session_id, is_created=False).all()
        ]
    })


@main.route('/brainstorm/session/<int:session_id>/tasks/create', methods=['POST'])
@login_required
def create_tasks_from_brainstorm(session_id):
    """壁打ちセッションからタスクを作成"""
    from models import ConversationSession, SuggestedTask, Task, db
    from brainstorm import parse_duration, extract_date_from_text
    from datetime import date, timedelta
    from dateutil.relativedelta import relativedelta
    
    # セッションの確認
    session = ConversationSession.query.filter_by(
        id=session_id,
        user_id=current_user.id
    ).first_or_404()
    
    data = request.get_json()
    task_ids = data.get('task_ids', [])  # 作成するタスクのIDリスト
    date_input = data.get('date', '').strip()  # 日付指定（11/4など）
    duration_input = data.get('duration', '').strip()  # 期間指定（1ヶ月分日割りなど）
    
    created_tasks = []
    
    # 提案タスクを取得
    suggested_tasks = SuggestedTask.query.filter_by(
        session_id=session_id,
        is_created=False
    ).all()
    
    if not task_ids:
        # 全ての提案タスクを作成
        tasks_to_create = suggested_tasks
    else:
        # 指定されたタスクのみ作成
        tasks_to_create = [t for t in suggested_tasks if t.id in task_ids]
    
    # 期間指定（1ヶ月分日割りなど）の場合
    if duration_input:
        duration_type = parse_duration(duration_input)
        
        if duration_type == 'monthly_daily':
            # 1ヶ月分を日割りで作成
            today = date.today()
            next_month = today + relativedelta(months=1)
            days_diff = (next_month - today).days
            
            for suggested_task in tasks_to_create:
                for i in range(days_diff):
                    task_date = today + timedelta(days=i)
                    
                    new_task = Task(
                        user_id=current_user.id,
                        title=f"{suggested_task.title} (Day {i+1})",
                        description=suggested_task.description,
                        priority=suggested_task.priority,
                        category='today' if i == 0 else 'other',
                        start_date=task_date,
                        end_date=task_date
                    )
                    db.session.add(new_task)
                    created_tasks.append(new_task)
            
            # 提案タスクをマーク
            for suggested_task in tasks_to_create:
                suggested_task.is_created = True
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'{len(created_tasks)}件のタスクを1ヶ月分日割りで作成しました',
                'created_count': len(created_tasks)
            })
        
        elif duration_type == 'weekly_daily':
            # 1週間分を日割りで作成
            today = date.today()
            
            for suggested_task in tasks_to_create:
                for i in range(7):
                    task_date = today + timedelta(days=i)
                    
                    new_task = Task(
                        user_id=current_user.id,
                        title=f"{suggested_task.title} (Day {i+1})",
                        description=suggested_task.description,
                        priority=suggested_task.priority,
                        category='today' if i == 0 else 'other',
                        start_date=task_date,
                        end_date=task_date
                    )
                    db.session.add(new_task)
                    created_tasks.append(new_task)
            
            # 提案タスクをマーク
            for suggested_task in tasks_to_create:
                suggested_task.is_created = True
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'{len(created_tasks)}件のタスクを1週間分日割りで作成しました',
                'created_count': len(created_tasks)
            })
    
    # 通常のタスク作成（日付指定あり/なし）
    target_date = None
    if date_input:
        target_date = extract_date_from_text(date_input)
        if not target_date:
            # 日付解析に失敗した場合は今日の日付を使用
            target_date = date.today()
    elif duration_input:
        # 期間指定がない場合は今日の日付を使用
        target_date = date.today()
    
    # 提案タスクからタスクを作成
    for suggested_task in tasks_to_create:
        # 日付が提案されていない場合は指定日付を使用、なければ今日
        task_date = suggested_task.suggested_date or target_date or date.today()
        
        new_task = Task(
            user_id=current_user.id,
            title=suggested_task.title,
            description=suggested_task.description,
            priority=suggested_task.priority,
            category='today' if task_date == date.today() else 'other',
            start_date=task_date,
            end_date=task_date
        )
        db.session.add(new_task)
        created_tasks.append(new_task)
        
        # 提案タスクをマーク
        suggested_task.is_created = True
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{len(created_tasks)}件のタスクを作成しました',
        'created_count': len(created_tasks)
    })


@main.route('/brainstorm/session/<int:session_id>')
@login_required
def get_brainstorm_session(session_id):
    """壁打ちセッションの詳細を取得"""
    from models import ConversationSession, ConversationMessage, SuggestedTask
    
    session = ConversationSession.query.filter_by(
        id=session_id,
        user_id=current_user.id
    ).first_or_404()
    
    messages = [
        {
            'id': msg.id,
            'role': msg.role,
            'content': msg.content,
            'created_at': msg.created_at.isoformat()
        }
        for msg in session.messages
    ]
    
    suggested_tasks = [
        {
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'priority': task.priority,
            'suggested_date': task.suggested_date.isoformat() if task.suggested_date else None,
            'is_created': task.is_created
        }
        for task in session.suggested_tasks
    ]
    
    return jsonify({
        'success': True,
        'session': {
            'id': session.id,
            'title': session.title,
            'goal': session.goal,
            'created_at': session.created_at.isoformat()
        },
        'messages': messages,
        'suggested_tasks': suggested_tasks
    })
