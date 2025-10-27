from flask import Flask
from flask_login import LoginManager
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
    
    # Flask-Login 初期化
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'ログインが必要です'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # ブループリント登録
    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(tasks, url_prefix='')
    
    # データベース作成
    with app.app_context():
        db.create_all()
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5001)
