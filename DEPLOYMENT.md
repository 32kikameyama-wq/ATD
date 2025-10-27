# Render.com へのデプロイ手順

## ✅ 準備が完了していること

- ✅ `Procfile` 作成済み
- ✅ `render.yaml` 作成済み
- ✅ プロジェクト構造を整備済み
- ✅ データベースモデル作成済み

## 🚀 デプロイ手順

### Step 1: Render.com に登録（初回のみ）

1. https://render.com にアクセス
2. "Sign Up" をクリック
3. GitHub アカウントで登録（推奨）

### Step 2: GitHub にコミット・プッシュ

```bash
# 変更をステージング
git add .

# コミット
git commit -m "プロジェクト構造を整備"

# GitHub にプッシュ
git push
```

### Step 3: Render.com でサービスを作成

**方法A: render.yaml を使用（自動デプロイ）**

1. Render Dashboard で "New +" → "Blueprint"
2. GitHub リポジトリを選択
3. "Apply" をクリック
4. 自動的にサービスが作成されます

**方法B: 手動で作成**

1. Render Dashboard で "New +" → "Web Service"
2. GitHub リポジトリを選択
3. 以下の設定:
   - **Name**: atd-task-manager
   - **Region**: Singapore (or nearest)
   - **Branch**: main
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
4. "Create Web Service" をクリック

### Step 4: 環境変数の設定

以下の環境変数を追加：

- `FLASK_APP`: `app.py`
- `FLASK_ENV`: `production`
- `SECRET_KEY`: (Render が自動生成)

### Step 5: データベースの作成

1. Render Dashboard で "New +" → "PostgreSQL"
2. 設定:
   - **Name**: atd-database
   - **Plan**: Free
   - **Database**: atd
   - **User**: atd_user
3. "Create Database" をクリック

### Step 6: データベース接続

環境変数に `DATABASE_URL` を追加：
- Database → "Connect" → "Internal Database URL" をコピー
- Web Service → "Environment" → "Add Environment Variable"
- Key: `DATABASE_URL`, Value: (コピーしたURL)

## 🎉 デプロイ完了

自動的にビルドが開始され、数分でアプリが公開されます！

URL は `https://atd-task-manager.onrender.com` のような形になります。

## 🔄 今後の更新方法

```bash
git add .
git commit -m "機能追加"
git push  # Render が自動的にデプロイ
```

## ⚠️ 注意事項

- 無料プランは15分間非アクティブでスリープします
- 初回アクセス時に起動に時間がかかります
- データは無料プランで保持されます
