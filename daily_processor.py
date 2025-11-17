"""
日次の自動処理を実行するモジュール
- 24時の日付切り替え
- タスクの繰り越し処理
"""
from datetime import datetime, timedelta, date as date_module
from zoneinfo import ZoneInfo


def process_daily_rollover(user_id=None):
    """
    日次の自動処理を実行（0時00分になったら自動実行）
    - テンプレートからタスクを自動生成（毎日/毎週/毎月）
    - 完了したタスクをアーカイブ（2日前以前の完了タスクで未アーカイブのもの）
    - 明日のタスクを本日のタスクに移動
    - カレンダーで指定されたタスク（start_date/end_dateが今日になったタスク）を明日のタスクに繰り上げ
    - 本日のタスク（未完了）はそのまま本日のタスクとして残す
    
    注: ダッシュボードにアクセスしたときに自動実行されます（1日に1回のみ）
    """
    # 今日の日付を取得（日本時間基準）
    now = datetime.now(ZoneInfo('Asia/Tokyo'))
    today = now.date()
    current_time = now.strftime('%Y-%m-%d %H:%M:%S')
    now_naive = now.replace(tzinfo=None)
    
    print(f"[DEBUG] Daily rollover started at: {current_time}, Date: {today}, User: {user_id}")
    
    if not user_id:
        return 0, 0, 0, 0
    
    from models import Task, TaskTemplate, UserPerformance, db as db_instance
    
    # 日付が変わったかどうかをチェック
    # 昨日のUserPerformanceレコードが存在し、今日のレコードが存在しない場合 = 日付が変わった
    yesterday = today - timedelta(days=1)
    yesterday_performance = UserPerformance.query.filter_by(
        user_id=user_id,
        date=yesterday
    ).first()
    
    today_performance = UserPerformance.query.filter_by(
        user_id=user_id,
        date=today
    ).first()
    
    # 今日のレコードが既に存在する場合、日次処理は既に実行済み
    if today_performance:
        print(f"[DEBUG] Daily rollover already executed today for user {user_id}, skipping")
        return 0, 0, 0, 0
    
    # 昨日のレコードが存在しない場合、初回アクセスまたは日付が変わっていない
    # この場合は、日次処理を実行しない（まだ日付が変わっていない）
    if not yesterday_performance:
        print(f"[DEBUG] Daily rollover skipped: Yesterday's record not found (date may not have changed), user={user_id}")
        return 0, 0, 0, 0
    
    # 昨日のレコードが存在し、今日のレコードが存在しない場合 = 日付が変わった
    print(f"[DEBUG] Daily rollover: Date changed detected (yesterday={yesterday}, today={today}), executing rollover")
    
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
                
                # カテゴリが正しく設定されているか確認（Noneの場合は'other'を使用）
                category = new_task.category or 'other'
                new_task.category = category
                
                # 同じカテゴリのタスクの中で最大のorder_indexを取得
                from sqlalchemy import func
                max_order = db_instance.session.query(func.max(Task.order_index)).filter_by(
                    user_id=user_id,
                    category=category
                ).scalar() or 0
                
                # order_indexを設定（タスク一覧で正しく表示されるように）
                new_task.order_index = max_order + 1
                
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
    # 注意: これは日付が変わったとき（0時00分）にのみ実行すべき
    # 今日の日次処理が初めて実行される場合のみ、「明日のタスク」を「本日のタスク」に移動
    # これは、昨日の「明日のタスク」が今日の「本日のタスク」になるため
    tomorrow_tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.category == 'tomorrow',
        Task.archived == False
    ).all()
    
    advanced_count = 0
    for task in tomorrow_tasks:
        task.category = 'today'
        task.updated_at = now_naive
        advanced_count += 1
    
    print(f"[DEBUG] Daily rollover: Moved {advanced_count} tasks from 'tomorrow' to 'today'")
    
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
            task.updated_at = now_naive
            calendar_moved_count += 1
    
    # 4. 昨日以前の本日のタスク（未完了）で、start_dateが昨日以前のものはそのまま残す
    # これは既にcategory='today'なので何もしない
    
    # コミット
    db_instance.session.commit()
    
    print(f"[DEBUG] Daily rollover completed: advanced={advanced_count}, calendar={calendar_moved_count}, archived={archived_count}, generated={generated_count}")
    
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

