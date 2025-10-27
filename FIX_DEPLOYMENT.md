# デプロイエラー修正手順

## 問題
- データベースは既に作成済み（緑チェック）
- Web サービスが作成に失敗（赤 X）

## 解決策

### 方法1: 既存のWebサービスを削除して再作成（簡単）

1. **「atd タスクマネージャー」を削除**
   - サービス名をクリック
   - 「Settings」→ 下部の「Delete」で削除

2. **新しくWebサービスを作成**
   - 「New +」→ 「Web Service」
   - GitHub リポジトリ `32kikameyama-wq/ATD` を選択
   - 設定：
     - Name: `atd-task-manager`
     - Region: `Singapore` または `Oregon`
     - Branch: `main`
     - Runtime: `Python 3`
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `gunicorn app:app`
   - **Environment Variables を追加**：
     - `FLASK_APP`: `app.py`
     - `FLASK_ENV`: `production`
   - 「Create Web Service」をクリック

3. **データベース接続**
   - Web サービスが作成されたら「Environment」タブを開く
   - `DATABASE_URL` を追加
   - 値: 既存の「atd データベース」の Internal Database URL をコピー

### 方法2: 既存のWebサービスを修正（既に作っている場合）

1. 「atd タスクマネージャー」をクリック
2. 「Settings」タブ
3. 「Manual Deploy」で再デプロイ
4. または「Events」タブでエラーログを確認

## 推奨
**方法1** が確実です！
