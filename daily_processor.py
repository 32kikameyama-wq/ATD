"""
日次の自動処理を実行するモジュール
- 24時の日付切り替え
- タスクの繰り越し処理
"""
from datetime import datetime, timedelta, date as date_module


def process_daily_rollover(user_id=None):
    """
    日次の自動処理を実行（ユーザーごとに1日1回のみ）
    - テンプレートからタスクを自動生成（毎日/毎週/毎月）
    - 今日の完了タスクをアーカイブ（未アーカイブのみ）
    - 今日の未完了タスクを明日へ繰り越し
    - 明日のタスクを今日へ移動
    - その他のタスクはそのまま
    
    注: 24時を過ぎてからダッシュボードにアクセスしたときに自動実行されます
    """
    today = date_module.today()
    
    if not user_id:
        return 0, 0
    
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
    
    # 完了したタスクをアーカイブ（昨日以前の完了タスクで未アーカイブのもの）
    yesterday = today - timedelta(days=1)
    completed_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.completed == True,
        Task.archived == False,
        db_instance.func.date(Task.updated_at) <= yesterday
    ).all()
    
    archived_count = 0
    for task in completed_tasks:
        task.archived = True
        # archived_atは date型なので、昨日の日付を設定
        if task.updated_at:
            task.archived_at = task.updated_at.date()
        else:
            task.archived_at = yesterday
        archived_count += 1
    
    # 今日の未完了タスクを明日へ繰り越し
    today_uncompleted = Task.query.filter(
        Task.user_id == user_id,
        Task.category == 'today',
        Task.completed == False,
        Task.archived == False
    ).all()
    
    moved_count = 0
    for task in today_uncompleted:
        # 昨日以前のタスクのみ繰り越す
        if task.updated_at.date() < today:
            task.category = 'tomorrow'
            task.updated_at = datetime.now()
            moved_count += 1
    
    # 明日のタスクを今日へ移動
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
    
    db_instance.session.commit()
    
    return moved_count, advanced_count, archived_count, generated_count


def get_daily_statistics(user_id, days=7):
    """
    過去N日間の統計データを取得
    """
    from models import Task, UserPerformance, db as db_instance
    
    end_date = date_module.today()
    start_date = end_date - timedelta(days=days - 1)
    
    # 過去N日間のタスク統計
    stats = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        
        # その日のタスク数
        total_on_date = Task.query.filter(
            Task.user_id == user_id,
            db_instance.func.date(Task.created_at) == current_date
        ).count()
        
        # その日の完了タスク数
        completed_on_date = Task.query.filter(
            Task.user_id == user_id,
            Task.completed == True,
            db_instance.func.date(Task.updated_at) == current_date
        ).count()
        
        # 完了率
        completion_rate = (completed_on_date / total_on_date * 100) if total_on_date > 0 else 0
        
        stats.append({
            'date': current_date,
            'total': total_on_date,
            'completed': completed_on_date,
            'completion_rate': round(completion_rate, 1)
        })
    
    return stats

