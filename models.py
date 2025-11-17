from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
from zoneinfo import ZoneInfo

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """ユーザーモデル"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)  # 管理者フラグ
    display_name = db.Column(db.String(80), nullable=True)  # 表示名
    bio = db.Column(db.Text, nullable=True)  # 自己紹介
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーションシップ
    tasks = db.relationship('Task', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """パスワードをハッシュ化して設定"""
        # macOS の Python 3.9 で scrypt が使えない場合に備えて pbkdf2 を指定
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """パスワードを確認"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Task(db.Model):
    """タスクモデル"""
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.Date)
    start_date = db.Column(db.Date)  # 開始期間
    end_date = db.Column(db.Date)    # 終了期間
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    category = db.Column(db.String(20), default='other')  # today, tomorrow, other
    order_index = db.Column(db.Integer, default=0)  # 優先順位用
    archived = db.Column(db.Boolean, default=False, nullable=False)  # アーカイブフラグ
    archived_at = db.Column(db.Date)  # アーカイブされた日付
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 時間計測関連
    is_tracking = db.Column(db.Boolean, default=False, nullable=False)  # 計測中かどうか
    tracking_start_time = db.Column(db.DateTime, nullable=True)  # 計測開始時刻
    total_seconds = db.Column(db.Integer, default=0, nullable=False)  # 累計時間（秒）
    
    # 外部キー
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    team_task_id = db.Column(db.Integer, db.ForeignKey('team_tasks.id'), nullable=True)  # チームタスクとの紐付け
    task_card_node_id = db.Column(db.Integer, db.ForeignKey('mindmap_nodes.id'), nullable=True, index=True)  # 個人タスクカードとの紐付け
    
    def __repr__(self):
        return f'<Task {self.title}>'
    
    def format_time(self):
        """累計時間をフォーマット（HH:MM:SS）"""
        hours = self.total_seconds // 3600
        minutes = (self.total_seconds % 3600) // 60
        seconds = self.total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def get_current_elapsed_time(self):
        """現在の経過時間を取得（計測中の場合のみ）"""
        if not self.is_tracking or not self.tracking_start_time:
            return self.total_seconds
        
        elapsed = (datetime.utcnow() - self.tracking_start_time).total_seconds()
        return int(self.total_seconds + elapsed)


class UserPerformance(db.Model):
    """ユーザーパフォーマンスモデル"""
    __tablename__ = 'user_performance'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    tasks_completed = db.Column(db.Integer, default=0)
    tasks_created = db.Column(db.Integer, default=0)
    completion_rate = db.Column(db.Float, default=0.0)
    streak_days = db.Column(db.Integer, default=0)
    total_work_seconds = db.Column(db.Integer, default=0)  # 本日の総作業時間（秒）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 複合インデックス（ユーザーIDと日付の組み合わせでユニーク）
    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='unique_user_date'),)
    
    def __repr__(self):
        return f'<UserPerformance {self.user_id} {self.date}>'
    
    def format_work_time(self):
        """作業時間をフォーマット（HH:MM:SS）"""
        hours = self.total_work_seconds // 3600
        minutes = (self.total_work_seconds % 3600) // 60
        seconds = self.total_work_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    @staticmethod
    def update_daily_performance(user_id, date=None):
        """日次パフォーマンスデータを更新"""
        if date is None:
            date = datetime.now(ZoneInfo('Asia/Tokyo')).date()
        
        # 既存のレコードを取得または作成
        performance = UserPerformance.query.filter_by(
            user_id=user_id, 
            date=date
        ).first()
        
        if not performance:
            performance = UserPerformance(user_id=user_id, date=date)
            db.session.add(performance)
        
        # その日のタスク完了数
        completed_today = Task.query.filter(
            Task.user_id == user_id,
            Task.completed == True,
            Task.completed_at.isnot(None),
            db.func.date(Task.completed_at) == date
        ).count()
        
        # その日のタスク作成数
        created_today = Task.query.filter(
            Task.user_id == user_id,
            db.func.date(Task.created_at) == date
        ).count()
        
        # 完了率の計算
        completion_rate = (completed_today / created_today * 100) if created_today > 0 else 0
        
        # 連続日数の計算
        streak_days = UserPerformance.calculate_streak(user_id)
        
        # その日の総作業時間を計算（完了済みタスクのみ）
        total_work_seconds = db.session.query(db.func.sum(Task.total_seconds)).filter(
            Task.user_id == user_id,
            Task.completed == True,
            Task.archived == False,
            Task.completed_at.isnot(None),
            db.func.date(Task.completed_at) == date
        ).scalar() or 0
        
        # データを更新
        performance.tasks_completed = completed_today
        performance.tasks_created = created_today
        performance.completion_rate = completion_rate
        performance.streak_days = streak_days
        performance.total_work_seconds = int(total_work_seconds)
        
        db.session.commit()
        return performance
    
    @staticmethod
    def calculate_streak(user_id):
        """連続完了日数を計算"""
        from datetime import timedelta
        
        streak = 0
        current_date = datetime.now().date()
        
        while True:
            # その日に完了したタスクがあるかチェック
            has_completed = UserPerformance.query.filter_by(
                user_id=user_id,
                date=current_date
            ).filter(UserPerformance.tasks_completed > 0).first()
            
            if has_completed:
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return streak


class Team(db.Model):
    """チームモデル"""
    __tablename__ = 'teams'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    members = db.relationship('TeamMember', backref='team', lazy='dynamic')
    tasks = db.relationship('TeamTask', backref='team', lazy='dynamic')
    
    def __repr__(self):
        return f'<Team {self.name}>'


class TeamMember(db.Model):
    """チームメンバーモデル"""
    __tablename__ = 'team_members'
    
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # admin, member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 複合インデックス（チームIDとユーザーIDの組み合わせでユニーク）
    __table_args__ = (db.UniqueConstraint('team_id', 'user_id', name='unique_team_user'),)
    
    def __repr__(self):
        return f'<TeamMember {self.team_id} {self.user_id}>'


class TeamTask(db.Model):
    """チームタスクモデル"""
    __tablename__ = 'team_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    due_date = db.Column(db.Date)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    category = db.Column(db.String(20), default='other')  # today, tomorrow, other
    order_index = db.Column(db.Integer, default=0)  # 優先順位用
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # マインドマップノードとの関連（カードごとのタスク用）
    parent_node_id = db.Column(db.Integer, db.ForeignKey('mindmap_nodes.id'), nullable=True)
    
    # リレーション
    assigned_user = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_tasks')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_tasks')
    
    def __repr__(self):
        return f'<TeamTask {self.title}>'
    
    def calculate_completion_rate(self):
        """完了率を計算"""
        from models import TaskAssignee
        assignees = TaskAssignee.query.filter_by(team_task_id=self.id).all()
        if not assignees:
            return 0
        completed_count = sum(1 for a in assignees if a.completed)
        return int(completed_count / len(assignees) * 100)


class TaskAssignee(db.Model):
    """タスク担当者モデル（複数担当者対応）"""
    __tablename__ = 'task_assignees'
    
    id = db.Column(db.Integer, primary_key=True)
    team_task_id = db.Column(db.Integer, db.ForeignKey('team_tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    team_task = db.relationship('TeamTask', backref='assignees_rel')
    user = db.relationship('User', backref='task_assignments')
    
    def __repr__(self):
        return f'<TaskAssignee task_id={self.team_task_id} user_id={self.user_id}>'


class Mindmap(db.Model):
    """マインドマップモデル"""
    __tablename__ = 'mindmaps'
    
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)  # 個人の場合はNULL
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # 個人マインドマップ用
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    date = db.Column(db.Date, nullable=True)  # マップの日付（例: 11/1のマップ）
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    nodes = db.relationship('MindmapNode', backref='mindmap', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Mindmap {self.name}>'
    
    def calculate_progress(self):
        """マインドマップ全体の達成度を計算"""
        all_nodes = self.nodes
        if not all_nodes:
            return 0
        
        total_weight = 0
        completed_weight = 0
        
        for node in all_nodes:
            # リーフノード（子ノードがない）のみカウント
            if not node.children:
                node_progress = node.calculate_progress()
                total_weight += 1
                completed_weight += node_progress / 100
        
        return int((completed_weight / total_weight * 100)) if total_weight > 0 else 0


class MindmapNode(db.Model):
    """マインドマップノードモデル"""
    __tablename__ = 'mindmap_nodes'
    
    id = db.Column(db.Integer, primary_key=True)
    mindmap_id = db.Column(db.Integer, db.ForeignKey('mindmaps.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('mindmap_nodes.id'), nullable=True)
    
    # ノード情報
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # 位置情報（保存用）
    position_x = db.Column(db.Float, default=0.0)
    position_y = db.Column(db.Float, default=0.0)
    
    # 進捗情報
    completed = db.Column(db.Boolean, default=False, nullable=False)
    progress = db.Column(db.Integer, default=0)  # 0-100の達成度
    due_date = db.Column(db.Date, nullable=True)  # 完了予定日
    
    # タスク情報
    is_task = db.Column(db.Boolean, default=False)  # タスクとして扱うかどうか
    team_task_id = db.Column(db.Integer, db.ForeignKey('team_tasks.id'), nullable=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)  # 個人タスクへのリンク
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    children = db.relationship('MindmapNode', backref=db.backref('parent', remote_side=[id]), lazy=True, cascade='all, delete-orphan')
    subtasks = db.relationship('TeamTask', primaryjoin='TeamTask.parent_node_id==MindmapNode.id', backref=db.backref('parent_node'), lazy=True, cascade='all, delete-orphan')
    linked_task = db.relationship('Task', foreign_keys=[task_id], backref=db.backref('mindmap_node', uselist=False))
    card_tasks = db.relationship('Task', foreign_keys='Task.task_card_node_id', backref=db.backref('task_card_node', lazy=True), lazy='dynamic')
    
    def __repr__(self):
        return f'<MindmapNode {self.title}>'
    
    def calculate_progress(self):
        """ノードの達成度を計算（再帰的）"""
        # サブタスクがある場合は、サブタスクの完了率を計算
        if self.subtasks:
            total_progress = 0
            for task in self.subtasks:
                # 各タスクの完了率を計算（TaskAssigneeベース）
                task_completion_rate = task.calculate_completion_rate()
                total_progress += task_completion_rate
            return int(total_progress / len(self.subtasks)) if self.subtasks else 0
        
        # タスクノードの場合
        if self.is_task and hasattr(self, 'team_task_id') and self.team_task_id:
            # チームタスクの完了率を計算
            from models import TeamTask
            team_task = TeamTask.query.get(self.team_task_id)
            if team_task:
                return team_task.calculate_completion_rate()
            return self.progress
        
        # 親ノードの場合、子ノードの平均を計算
        if self.children:
            total_progress = sum(child.calculate_progress() for child in self.children)
            return int(total_progress / len(self.children)) if self.children else 0
        
        return self.progress


class TaskTemplate(db.Model):
    """タスクテンプレートモデル（固定タスク・繰り返しタスク用）"""
    __tablename__ = 'task_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    category = db.Column(db.String(20), default='today')  # today, tomorrow, other
    repeat_type = db.Column(db.String(20), nullable=True)  # daily, weekly, monthly, none
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 外部キー
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    def __repr__(self):
        return f'<TaskTemplate {self.title}>'
    
    def create_task_from_template(self, target_date=None):
        """テンプレートからタスクを作成"""
        from datetime import date
        if target_date is None:
            target_date = date.today()
        
        new_task = Task(
            title=self.title,
            description=self.description,
            priority=self.priority,
            category=self.category or 'other',  # カテゴリがNoneの場合は'other'を使用
            user_id=self.user_id,
            start_date=target_date,
            end_date=target_date,
            archived=False  # 明示的にアーカイブされていない状態を設定
        )
        return new_task


class Notification(db.Model):
    """通知モデル"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), default='info')  # info, warning, success, error
    read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    related_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)  # 関連チーム
    related_task_id = db.Column(db.Integer, nullable=True)  # 関連タスクID
    
    def __repr__(self):
        return f'<Notification {self.title}>'


class ConversationSession(db.Model):
    """壁打ち会話セッションモデル"""
    __tablename__ = 'conversation_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=True)  # 会話のタイトル（自動生成）
    goal = db.Column(db.Text, nullable=True)  # 目標・目的
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    messages = db.relationship('ConversationMessage', backref='session', lazy=True, cascade='all, delete-orphan', order_by='ConversationMessage.created_at')
    suggested_tasks = db.relationship('SuggestedTask', backref='session', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ConversationSession {self.id}>'


class ConversationMessage(db.Model):
    """会話メッセージモデル"""
    __tablename__ = 'conversation_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('conversation_sessions.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ConversationMessage {self.id}>'


class SuggestedTask(db.Model):
    """提案されたタスクモデル"""
    __tablename__ = 'suggested_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('conversation_sessions.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    suggested_date = db.Column(db.Date, nullable=True)  # 提案された日付
    is_created = db.Column(db.Boolean, default=False, nullable=False)  # タスク化されたかどうか
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SuggestedTask {self.title}>'
