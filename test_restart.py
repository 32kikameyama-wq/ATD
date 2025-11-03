"""
サーバー再起動をシミュレートするテスト
"""

from app import create_app
from models import db, User
from config import Config

def test_restart_simulation():
    """サーバー再起動をシミュレート"""
    print("=" * 60)
    print("🔄 サーバー再起動シミュレーションテスト")
    print("=" * 60)
    
    # 1回目の起動（アプリケーション作成）
    print("\n1️⃣ サーバー起動1回目...")
    app = create_app(Config)
    
    with app.app_context():
        users = User.query.all()
        print(f"   起動時点でのユーザー数: {len(users)}")
        for user in users:
            print(f"   - {user.username} (ID: {user.id})")
    
    # 2回目の起動（再起動をシミュレート）
    print("\n2️⃣ サーバー再起動（2回目）...")
    app2 = create_app(Config)
    
    with app2.app_context():
        users = User.query.all()
        print(f"   再起動時点でのユーザー数: {len(users)}")
        for user in users:
            print(f"   - {user.username} (ID: {user.id})")
        
        if len(users) >= 3:
            print("\n   ✅ データが保持されています！")
        else:
            print("\n   ❌ データが消えています！")
    
    print("\n" + "=" * 60)
    print("✅ テスト完了")
    print("=" * 60)

if __name__ == '__main__':
    test_restart_simulation()

