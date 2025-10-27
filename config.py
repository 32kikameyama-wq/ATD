import os
from dotenv import load_dotenv

# 環境変数を読み込む
load_dotenv()

class Config:
    """アプリケーション設定"""
    
    # セキュリティ
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # データベース
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///atd.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # その他
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
