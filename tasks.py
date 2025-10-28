from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models import db, Task
from datetime import datetime

tasks = Blueprint('tasks', __name__)

@tasks.route('/tasks')
@login_required
def list_tasks():
    """タスク一覧"""
    # 分類別にタスクを取得
    today_tasks = Task.query.filter_by(user_id=current_user.id, category='today').order_by(Task.order_index).all()
    tomorrow_tasks = Task.query.filter_by(user_id=current_user.id, category='tomorrow').order_by(Task.order_index).all()
    other_tasks = Task.query.filter_by(user_id=current_user.id, category='other').order_by(Task.order_index).all()
    
    return render_template('tasks/list.html', 
                         today_tasks=today_tasks,
                         tomorrow_tasks=tomorrow_tasks,
                         other_tasks=other_tasks)

@tasks.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create_task():
    """タスク作成"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        due_date_str = request.form.get('due_date')
        priority = request.form.get('priority')
        category = request.form.get('category')
        
        # バリデーション
        if not title or not due_date_str or not priority or not category:
            flash('必須項目を入力してください', 'error')
            return render_template('tasks/create.html')
        
        # 日付の変換
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('有効な日付を入力してください', 'error')
                return render_template('tasks/create.html')
        
        # 同じタイトルと期限のタスクが既に存在するかチェック
        existing_task = Task.query.filter_by(
            title=title,
            due_date=due_date,
            user_id=current_user.id
        ).first()
        
        if existing_task:
            flash('同じタイトルと期限のタスクが既に存在します', 'error')
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
            due_date=due_date,
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
        due_date_str = request.form.get('due_date')
        task.priority = request.form.get('priority')
        task.category = request.form.get('category')
        
        # バリデーション
        if not task.title or not due_date_str or not task.priority or not task.category:
            flash('必須項目を入力してください', 'error')
            return render_template('tasks/edit.html', task=task)
        
        # 日付の変換
        if due_date_str:
            try:
                task.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('有効な日付を入力してください', 'error')
                return render_template('tasks/edit.html', task=task)
        else:
            task.due_date = None
        
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
    
    task = Task.query.get_or_404(task_id)
    
    # 自分のタスクか確認
    if task.user_id != current_user.id:
        flash('このタスクを変更する権限がありません', 'error')
        return redirect(url_for('tasks.list_tasks'))
    
    task.completed = not task.completed
    db.session.commit()
    
    # パフォーマンスデータを更新
    UserPerformance.update_daily_performance(current_user.id)
    
    flash(f'タスクを{"完了" if task.completed else "未完了"}に変更しました', 'success')
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
