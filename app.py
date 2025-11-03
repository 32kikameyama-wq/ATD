from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config
from models import db, User
from routes import main
from auth import auth
from tasks import tasks
import secrets

def create_app(config_class=Config):
    """アプリケーションファクトリー"""
    app = Flask(__name__)
    
    # 設定を読み込む
    app.config.from_object(config_class)
    
    # セキュリティ: デフォルトのSECRET_KEYがない場合はランダムに生成
    if app.config['SECRET_KEY'] == 'dev-secret-key-change-in-production':
        app.config['SECRET_KEY'] = secrets.token_hex(32)
    
    # データベース初期化
    db.init_app(app)
    
    # Flask-Migrate 初期化
    migrate = Migrate(app, db)
    
    # Flask-Login 初期化
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'ログインが必要です'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # テンプレートコンテキストプロセッサー（全ページ共通データ）
    @app.context_processor
    def inject_notification_count():
        """全てのテンプレートに未読通知数を渡す"""
        from flask_login import current_user
        if current_user.is_authenticated:
            from models import Notification
            unread_count = Notification.query.filter_by(
                user_id=current_user.id,
                read=False
            ).count()
            return {'unread_notifications': unread_count}
        return {'unread_notifications': 0}
    
    # ブループリント登録
    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(tasks, url_prefix='')
    
    # データベース作成と初期ユーザー作成
    with app.app_context():
        try:
            # データベースを作成（初回のみ、テーブルが存在しない場合）
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            # テーブルが存在しない場合のみ作成
            if not existing_tables:
                db.create_all()
                print('✅ データベーステーブルを作成しました')
            
            # 初期管理者ユーザーを作成（存在しない場合のみ）
            admin_user = User.query.filter_by(username='亀山瑞喜').first()
            if not admin_user:
                admin = User(
                    username='亀山瑞喜',
                    email='32ki.kameyama@gmail.com',
                    is_admin=True
                )
                admin.set_password('0418')
                db.session.add(admin)
                db.session.commit()
                print('✅ 初期管理者ユーザー「亀山瑞喜」を作成しました')
        except Exception as e:
            print(f'⚠️ データベース初期化エラー: {e}')
    
    return app

# Render デプロイ用の app オブジェクト
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
