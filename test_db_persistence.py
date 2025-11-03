"""
データベース永続化テストスクリプト
Railway.app のデプロイ環境をシミュレート
"""

from app import create_app
from models import db, User
from config import Config

def test_database_persistence():
    """データベースの永続化をテスト"""
    print("=" * 60)
    print("🧪 データベース永続化テスト")
    print("=" * 60)
    
    # アプリケーションを作成
    app = create_app(Config)
    
    with app.app_context():
        print("\n1️⃣ 既存のユーザーを確認...")
        users = User.query.all()
        print(f"   現在のユーザー数: {len(users)}")
        for user in users:
            print(f"   - {user.username} (管理者: {user.is_admin}, ID: {user.id})")
        
        print("\n2️⃣ テストユーザーを追加...")
        # 既に存在するか確認
        test_user = User.query.filter_by(username='テストユーザー').first()
        if test_user:
            print("   テストユーザーは既に存在します")
        else:
            test_user = User(
                username='テストユーザー',
                email='test@example.com',
                is_admin=False
            )
            test_user.set_password('test123')
            db.session.add(test_user)
            db.session.commit()
            print("   ✅ テストユーザーを作成しました")
        
        print("\n3️⃣ 再確認...")
        users = User.query.all()
        print(f"   現在のユーザー数: {len(users)}")
        for user in users:
            print(f"   - {user.username} (管理者: {user.is_admin}, ID: {user.id})")
        
        print("\n" + "=" * 60)
        print("✅ テスト完了")
        print("=" * 60)
        print("\n説明:")
        print("- 再度このスクリプトを実行すると、「テストユーザー」が存在する場合は作成されません")
        print("- これで、同じコードが複数回実行されてもユーザーが消えないことが確認できます")

if __name__ == '__main__':
    test_database_persistence()

