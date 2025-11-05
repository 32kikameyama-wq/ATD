"""
日次の自動処理を実行するモジュール
- 24時の日付切り替え
- タスクの繰り越し処理
"""
from datetime import datetime, timedelta, date as date_module


def process_daily_rollover(user_id=None):
    """
    日次の自動処理を実行（0時00分になったら自動実行）
    - テンプレートからタスクを自動生成（毎日/毎週/毎月）
    - 完了したタスクをアーカイブ（2日前以前の完了タスクで未アーカイブのもの）
    - 明日のタスクを本日のタスクに移動
    - カレンダーで指定されたタスク（start_date/end_dateが今日になったタスク）を明日のタスクに繰り上げ
    - 本日のタスク（未完了）はそのまま本日のタスクとして残す
    
    注: ダッシュボードにアクセスしたときに自動実行されます
    """
    # 今日の日付を取得（現在時刻から取得）
    now = datetime.now()
    today = now.date()
    current_time = now.strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"[DEBUG] Daily rollover started at: {current_time}, Date: {today}, User: {user_id}")
    
    if not user_id:
        return 0, 0, 0, 0
    
    from models import Task, TaskTemplate, db as db_instance
    
    # テンプレートからタスクを自動生成
    templates = TaskTemplate.query.filter_by(
        user_id=user_id,
        is_active=True
    ).filter(TaskTemplate.repeat_type != 'none').all()
    
    generated_count = 0
    for template in templates:
        should_generate = False
        
        if template.repeat_type == 'daily':
            should_generate = True
        elif template.repeat_type == 'weekly':
            # 毎週の場合は月曜日
            should_generate = today.weekday() == 0
        elif template.repeat_type == 'monthly':
            # 毎月の場合は1日
            should_generate = today.day == 1
        
        if should_generate:
            # 今日すでにこのテンプレートから作成されたタスクがあるかチェック
            existing = Task.query.filter(
                Task.user_id == user_id,
                Task.title == template.title,
                Task.start_date == today,
                Task.archived == False
            ).first()
            
            if not existing:
                new_task = template.create_task_from_template(today)
                db_instance.session.add(new_task)
                generated_count += 1
    
    # 完了したタスクをアーカイブ（2日前以前の完了タスクで未アーカイブのもの）
    two_days_ago = today - timedelta(days=2)
    # SQLite互換性のため、Python側でフィルタリング
    all_completed_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.completed == True,
        Task.archived == False
    ).all()
    
    completed_tasks = []
    for task in all_completed_tasks:
        if task.updated_at:
            task_date = task.updated_at.date()
        else:
            task_date = task.created_at.date() if task.created_at else today
        if task_date <= two_days_ago:
            completed_tasks.append(task)
    
    archived_count = 0
    for task in completed_tasks:
        task.archived = True
        if task.updated_at:
            task.archived_at = task.updated_at.date()
        else:
            task.archived_at = two_days_ago
        archived_count += 1
    
    # 1. 昨日以前に作成された本日のタスク（未完了）を確認
    # 昨日以前に作成されたタスクは、start_dateが今日でない限り、そのまま残す
    # （未完了のタスクは引き続き作業するため）
    
    # 2. 明日のタスクを本日のタスクに移動
    tomorrow_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.category == 'tomorrow',
        Task.archived == False
    ).all()
    
    advanced_count = 0
    for task in tomorrow_tasks:
        task.category = 'today'
        task.updated_at = datetime.now()
        advanced_count += 1
    
    # 3. カレンダーで指定されたタスク（start_date/end_dateが今日になったタスク）を明日のタスクに繰り上げ
    # start_date <= today <= end_date のタスクで、category='other'のものを探す
    calendar_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.category == 'other',
        Task.archived == False,
        Task.start_date <= today,
        Task.end_date >= today
    ).all()
    
    calendar_moved_count = 0
    for task in calendar_tasks:
        # 今日がタスクの期間内なら、明日のタスクに繰り上げ
        if task.start_date <= today <= task.end_date:
            task.category = 'tomorrow'
            task.updated_at = datetime.now()
            calendar_moved_count += 1
    
    # 4. 昨日以前の本日のタスク（未完了）で、start_dateが昨日以前のものはそのまま残す
    # これは既にcategory='today'なので何もしない
    
    db_instance.session.commit()
    
    return advanced_count, calendar_moved_count, archived_count, generated_count


def get_daily_statistics(user_id, days=7):
    """
    過去N日間の統計データを取得
    """
    from models import Task, UserPerformance, db as db_instance
    
    end_date = date_module.today()
    start_date = end_date - timedelta(days=days - 1)
    
    # 過去N日間のタスク統計
    # SQLite互換性のため、Python側でフィルタリング
    all_tasks = Task.query.filter(
        Task.user_id == user_id
    ).all()
    
    stats = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        
        # その日のタスク数（Python側でフィルタリング）
        total_on_date = 0
        completed_on_date = 0
        
        for task in all_tasks:
            if task.created_at:
                created_date = task.created_at.date()
                if created_date == current_date:
                    total_on_date += 1
            
            if task.completed and task.updated_at:
                updated_date = task.updated_at.date()
                if updated_date == current_date:
                    completed_on_date += 1
        
        # 完了率
        completion_rate = (completed_on_date / total_on_date * 100) if total_on_date > 0 else 0
        
        stats.append({
            'date': current_date,
            'total': total_on_date,
            'completed': completed_on_date,
            'completion_rate': round(completion_rate, 1)
        })
    
    return stats

