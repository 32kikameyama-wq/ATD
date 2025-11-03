from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models import db, Task
from datetime import datetime

tasks = Blueprint('tasks', __name__)

@tasks.route('/tasks')
@login_required
def list_tasks():
    """タスク一覧"""
    from datetime import date
    
    # 分類別にタスクを取得（アーカイブ済みは除外）
    today_tasks = Task.query.filter_by(user_id=current_user.id, category='today', archived=False).order_by(Task.order_index).all()
    tomorrow_tasks = Task.query.filter_by(user_id=current_user.id, category='tomorrow', archived=False).order_by(Task.order_index).all()
    other_tasks = Task.query.filter_by(user_id=current_user.id, category='other', archived=False).order_by(Task.order_index).all()
    
    return render_template('tasks/list.html', 
                         today_tasks=today_tasks,
                         tomorrow_tasks=tomorrow_tasks,
                         other_tasks=other_tasks,
                         current_date=date.today())

@tasks.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create_task():
    """タスク作成"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        priority = request.form.get('priority')
        category = request.form.get('category')
        
        # バリデーション
        if not title or not start_date_str or not end_date_str or not priority or not category:
            flash('必須項目を入力してください', 'error')
            return render_template('tasks/create.html')
        
        # 日付の変換
        start_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('有効な開始日を入力してください', 'error')
                return render_template('tasks/create.html')
        
        end_date = None
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('有効な終了日を入力してください', 'error')
                return render_template('tasks/create.html')
        
        # 開始日が終了日より後の場合はエラー
        if start_date and end_date and start_date > end_date:
            flash('開始日は終了日より前でなければなりません', 'error')
            return render_template('tasks/create.html')
        
        # 同じタイトルのタスクが既に存在するかチェック
        existing_task = Task.query.filter_by(
            title=title,
            start_date=start_date,
            end_date=end_date,
            user_id=current_user.id
        ).first()
        
        if existing_task:
            flash('同じタイトルと期間のタスクが既に存在します', 'error')
            return render_template('tasks/create.html')
        
        # 次のorder_indexを取得
        max_order = db.session.query(db.func.max(Task.order_index)).filter_by(
            user_id=current_user.id,
            category=category
        ).scalar() or 0
        
        # タスク作成
        new_task = Task(
            title=title,
            description=description,
            start_date=start_date,
            end_date=end_date,
            priority=priority,
            category=category,
            order_index=max_order + 1,
            user_id=current_user.id
        )
        
        db.session.add(new_task)
        db.session.commit()
        
        # パフォーマンスデータを更新
        from models import UserPerformance
        UserPerformance.update_daily_performance(current_user.id)
        
        flash('タスクを作成しました', 'success')
        return redirect(url_for('tasks.list_tasks'))
    
    return render_template('tasks/create.html')

@tasks.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    """タスク編集"""
    task = Task.query.get_or_404(task_id)
    
    # 自分のタスクか確認
    if task.user_id != current_user.id:
        flash('このタスクを編集する権限がありません', 'error')
        return redirect(url_for('tasks.list_tasks'))
    
    if request.method == 'POST':
        task.title = request.form.get('title')
        task.description = request.form.get('description')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        task.priority = request.form.get('priority')
        task.category = request.form.get('category')
        
        # バリデーション
        if not task.title or not start_date_str or not end_date_str or not task.priority or not task.category:
            flash('必須項目を入力してください', 'error')
            return render_template('tasks/edit.html', task=task)
        
        # 日付の変換
        if start_date_str:
            try:
                task.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('有効な開始日を入力してください', 'error')
                return render_template('tasks/edit.html', task=task)
        else:
            task.start_date = None
        
        if end_date_str:
            try:
                task.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('有効な終了日を入力してください', 'error')
                return render_template('tasks/edit.html', task=task)
        else:
            task.end_date = None
        
        # 開始日が終了日より後の場合はエラー
        if task.start_date and task.end_date and task.start_date > task.end_date:
            flash('開始日は終了日より前でなければなりません', 'error')
            return render_template('tasks/edit.html', task=task)
        
        db.session.commit()
        
        flash('タスクを更新しました', 'success')
        return redirect(url_for('tasks.list_tasks'))
    
    return render_template('tasks/edit.html', task=task)

@tasks.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    """タスク削除"""
    task = Task.query.get_or_404(task_id)
    
    # 自分のタスクか確認
    if task.user_id != current_user.id:
        flash('このタスクを削除する権限がありません', 'error')
        return redirect(url_for('tasks.list_tasks'))
    
    db.session.delete(task)
    db.session.commit()
    
    flash('タスクを削除しました', 'success')
    return redirect(url_for('tasks.list_tasks'))

@tasks.route('/tasks/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    """タスクの完了/未完了切り替え"""
    from models import UserPerformance
    from datetime import datetime
    
    task = Task.query.get_or_404(task_id)
    
    # 自分のタスクか確認
    if task.user_id != current_user.id:
        flash('このタスクを変更する権限がありません', 'error')
        return redirect(url_for('tasks.list_tasks'))
    
    # 完了状態を切り替え
    task.completed = not task.completed
    
    # 完了にした場合、時間計測を停止
    if task.completed and task.is_tracking:
        if task.tracking_start_time:
            elapsed = (datetime.utcnow() - task.tracking_start_time).total_seconds()
            task.total_seconds += int(elapsed)
        task.is_tracking = False
        task.tracking_start_time = None
    
    # チームタスクと紐付いている場合、TaskAssigneeを更新
    if task.team_task_id:
        from models import TaskAssignee, TeamTask, MindmapNode
        task_assignee = TaskAssignee.query.filter_by(
            team_task_id=task.team_task_id,
            user_id=current_user.id
        ).first()
        if task_assignee:
            task_assignee.completed = task.completed
            task_assignee.completed_at = datetime.utcnow() if task.completed else None
        
        # チームタスクの完了率を計算して更新
        team_task = TeamTask.query.get(task.team_task_id)
        if team_task:
            completion_rate = team_task.calculate_completion_rate()
            team_task.completed = (completion_rate == 100)
            team_task.updated_at = datetime.utcnow()
            
            # 親ノードの進捗率を更新
            if team_task.parent_node_id:
                parent_node = MindmapNode.query.get(team_task.parent_node_id)
                if parent_node:
                    parent_node.progress = parent_node.calculate_progress()
                    db.session.add(parent_node)
    
    db.session.commit()
    
    # パフォーマンスデータを更新
    UserPerformance.update_daily_performance(current_user.id)
    
    flash(f'タスクを{"完了" if task.completed else "未完了"}に変更しました', 'success')
    
    # リファラーに基づいてリダイレクト先を決定
    referer = request.headers.get('Referer')
    if referer and 'dashboard' in referer:
        return redirect(url_for('main.dashboard'))
    else:
        return redirect(url_for('tasks.list_tasks'))

@tasks.route('/tasks/<int:task_id>/move', methods=['POST'])
@login_required
def move_task(task_id):
    """タスクの分類移動"""
    task = Task.query.get_or_404(task_id)
    
    # 自分のタスクか確認
    if task.user_id != current_user.id:
        flash('このタスクを変更する権限がありません', 'error')
        return redirect(url_for('tasks.list_tasks'))
    
    new_category = request.form.get('category')
    if new_category not in ['today', 'tomorrow', 'other']:
        flash('無効な分類です', 'error')
        return redirect(url_for('tasks.list_tasks'))
    
    # 新しい分類での次のorder_indexを取得
    max_order = db.session.query(db.func.max(Task.order_index)).filter_by(
        user_id=current_user.id,
        category=new_category
    ).scalar() or 0
    
    task.category = new_category
    task.order_index = max_order + 1
    db.session.commit()
    
    category_names = {'today': '本日のタスク', 'tomorrow': '明日のタスク', 'other': 'その他のタスク'}
    flash(f'タスクを{category_names[new_category]}に移動しました', 'success')
    return redirect(url_for('tasks.list_tasks'))

@tasks.route('/tasks/<int:task_id>/toggle-tracking', methods=['POST'])
@login_required
def toggle_tracking(task_id):
    """時間計測の開始/停止"""
    from datetime import datetime
    from models import UserPerformance
    
    task = Task.query.get_or_404(task_id)
    
    # 自分のタスクか確認
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'message': '権限がありません'}), 403
    
    # 完了タスクは計測不可
    if task.completed:
        return jsonify({'success': False, 'message': '完了済みタスクは計測できません'}), 400
    
    if task.is_tracking:
        # 計測停止
        if task.tracking_start_time:
            elapsed = (datetime.utcnow() - task.tracking_start_time).total_seconds()
            task.total_seconds += int(elapsed)
        task.is_tracking = False
        task.tracking_start_time = None
        message = '計測を停止しました'
    else:
        # 計測開始
        task.is_tracking = True
        task.tracking_start_time = datetime.utcnow()
        message = '計測を開始しました'
    
    db.session.commit()
    
    # パフォーマンスデータを更新（計測停止時のみ）
    if not task.is_tracking:
        UserPerformance.update_daily_performance(current_user.id)
    
    return jsonify({
        'success': True,
        'message': message,
        'is_tracking': task.is_tracking,
        'total_seconds': task.total_seconds,
        'formatted_time': task.format_time()
    })

@tasks.route('/tasks/<int:task_id>/current-time', methods=['GET'])
@login_required
def get_current_time(task_id):
    """現在の経過時間を取得（リアルタイム更新用）"""
    task = Task.query.get_or_404(task_id)
    
    # 自分のタスクか確認
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'message': '権限がありません'}), 403
    
    current_elapsed = task.get_current_elapsed_time()
    
    hours = current_elapsed // 3600
    minutes = (current_elapsed % 3600) // 60
    seconds = current_elapsed % 60
    
    return jsonify({
        'success': True,
        'total_seconds': current_elapsed,
        'formatted_time': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        'is_tracking': task.is_tracking
    })

@tasks.route('/tasks/<int:task_id>/reorder', methods=['POST'])
@login_required
def reorder_task(task_id):
    """タスクの優先順位変更"""
    task = Task.query.get_or_404(task_id)
    
    # 自分のタスクか確認
    if task.user_id != current_user.id:
        return jsonify({'error': '権限がありません'}), 403
    
    direction = request.json.get('direction')  # 'up' or 'down'
    if direction not in ['up', 'down']:
        return jsonify({'error': '無効な方向です'}), 400
    
    # 同じ分類のタスクを取得
    same_category_tasks = Task.query.filter_by(
        user_id=current_user.id,
        category=task.category
    ).order_by(Task.order_index).all()
    
    current_index = same_category_tasks.index(task)
    
    if direction == 'up' and current_index > 0:
        # 上のタスクと入れ替え
        prev_task = same_category_tasks[current_index - 1]
        task.order_index, prev_task.order_index = prev_task.order_index, task.order_index
    elif direction == 'down' and current_index < len(same_category_tasks) - 1:
        # 下のタスクと入れ替え
        next_task = same_category_tasks[current_index + 1]
        task.order_index, next_task.order_index = next_task.order_index, task.order_index
    else:
        return jsonify({'error': '移動できません'}), 400
    
    db.session.commit()
    return jsonify({'success': True})

@tasks.route('/tasks/<int:task_id>/add-to-mindmap', methods=['POST'])
@login_required
def add_to_mindmap(task_id):
    """タスクをマインドマップに追加"""
    from models import Mindmap, MindmapNode
    
    task = Task.query.get_or_404(task_id)
    
    # 自分のタスクか確認
    if task.user_id != current_user.id:
        flash('このタスクを変更する権限がありません', 'error')
        return redirect(url_for('tasks.list_tasks'))
    
    # 既にマインドマップに追加されている場合はスキップ
    if task.mindmap_node:
        flash('このタスクは既にマインドマップに追加されています', 'info')
        return redirect(url_for('tasks.list_tasks'))
    
    # 個人マインドマップを取得または作成
    mindmap_obj = Mindmap.query.filter_by(user_id=current_user.id).first()
    if not mindmap_obj:
        mindmap_obj = Mindmap(
            user_id=current_user.id,
            name='個人マインドマップ',
            description='個人用マインドマップ',
            created_by=current_user.id
        )
        db.session.add(mindmap_obj)
        db.session.flush()
    
    # マインドマップノードを作成（ルートノード）
    new_node = MindmapNode(
        mindmap_id=mindmap_obj.id,
        parent_id=None,
        title=task.title,
        description=task.description or '',
        position_x=0,
        position_y=0,
        is_task=True,
        task_id=task.id
    )
    
    db.session.add(new_node)
    db.session.commit()
    
    flash('タスクをマインドマップに追加しました', 'success')
    return redirect(url_for('tasks.list_tasks'))
