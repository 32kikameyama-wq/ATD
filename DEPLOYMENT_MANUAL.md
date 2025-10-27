# Render.com 手動デプロイ手順（簡単版）

## Step 1: Render.com にアクセス
https://render.com にアクセス

## Step 2: アカウント作成
1. "Sign Up" をクリック
2. GitHub アカウントで登録（推奨）

## Step 3: アカウントが作成できたら以下を実行

### 3-1. Web サービスを作成
1. Render ダッシュボードで **"New +"** をクリック
2. **"Web Service"** を選択
3. **"Connect account"** または **"Configure account"** でGitHubアカウントを連携
4. **リポジトリ `32kikameyama-wq/ATD` を選択**

### 3-2. 設定を入力
以下の設定を入力：

| 項目 | 値 |
|------|---|
| **Name** | `atd-task-manager` |
| **Region** | `Singapore` (またはJapan) |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app` |

### 3-3. 環境変数を追加
**Environment Variables** セクションで以下を追加：

| Key | Value |
|-----|-------|
| `FLASK_APP` | `app.py` |
| `FLASK_ENV` | `production` |
| `SECRET_KEY` | (何も入力しない - 自動生成される) |

### 3-4. デプロイ開始
**"Create Web Service"** をクリック

## Step 4: データベースを作成（別途）
1. "New +" → **"PostgreSQL"** を選択
2. 設定：
   - **Name**: `atd-database`
   - **Plan**: `Free`
3. "Create Database" をクリック

## Step 5: データベース接続
1. 作成したデータベースを開く
2. **"Connections"** タブ
3. **"Internal Database URL"** をコピー
4. Web サービスの **Environment** セクションに追加：
   - Key: `DATABASE_URL`
   - Value: (コピーしたURL)
5. サービスを再デプロイ

## トラブルシューティング

### 空白画面が出る場合
1. **ブラウザをリロード** (F5)
2. **別のブラウザで試す** (Chrome → Safari)
3. **VPN やプロキシをオフにする**
4. **キャッシュをクリア** (Ctrl+Shift+Delete)

### GitHub が連携できない場合
- GitHub の設定で Render にアクセス許可を付与

## 完了
数分後に URL が発行されます！
例: `https://atd-task-manager.onrender.com`
