import os
from dotenv import load_dotenv

# 環境変数を読み込む
load_dotenv()

class Config:
    """アプリケーション設定"""
    
    # セキュリティ
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # データベース
    basedir = os.path.abspath(os.path.dirname(__file__))
    # instanceフォルダを作成
    instance_path = os.path.join(basedir, 'instance')
    os.makedirs(instance_path, exist_ok=True)
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f'sqlite:///{os.path.join(instance_path, "atd.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # その他
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
