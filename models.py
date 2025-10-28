from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """ユーザーモデル"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
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
    due_date = db.Column(db.Date)
    start_date = db.Column(db.Date)  # 開始期間
    end_date = db.Column(db.Date)    # 終了期間
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    category = db.Column(db.String(20), default='other')  # today, tomorrow, other
    order_index = db.Column(db.Integer, default=0)  # 優先順位用
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 外部キー
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    def __repr__(self):
        return f'<Task {self.title}>'


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 複合インデックス（ユーザーIDと日付の組み合わせでユニーク）
    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='unique_user_date'),)
    
    def __repr__(self):
        return f'<UserPerformance {self.user_id} {self.date}>'
    
    @staticmethod
    def update_daily_performance(user_id, date=None):
        """日次パフォーマンスデータを更新"""
        if date is None:
            date = datetime.now().date()
        
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
            db.func.date(Task.updated_at) == date
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
        
        # データを更新
        performance.tasks_completed = completed_today
        performance.tasks_created = created_today
        performance.completion_rate = completion_rate
        performance.streak_days = streak_days
        
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
    
    def __repr__(self):
        return f'<TeamTask {self.title}>'
