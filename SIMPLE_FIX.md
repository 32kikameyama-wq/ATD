# 🎯 超簡単な修正方法

## 現在の状態
- ✅ データベース: 作成済み（緑チェック）
- ❌ Web サービス: 失敗（赤 X）

## 解決方法（3ステップ）

### Step 1: 失敗した Web サービスを削除
1. 左側「リソース」から「atd タスクマネージャー」をクリック
2. 「Settings」タブを開く
3. 一番下の「Delete Service」をクリック

### Step 2: 新しい Web サービスを作成
1. 「New +」→ 「Web Service」
2. GitHub リポジトリ `ATD` を選択
3. 設定を入力：
   - Name: `atd-task-manager`
   - Region: `Singapore` または `Oregon`
   - Branch: `main`
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. 「Create Web Service」をクリック

### Step 3: データベースに接続
1. Web サービスが作成されたら「Environment」タブを開く
2. 既存の「atd データベース」の情報を使用:
   - 「atd データベース」を開く
   - 「接続」タブで「内部データベースURL」をコピー
   - Web サービスの「Environment」に追加:
     - Key: `DATABASE_URL`
     - Value: コピーしたURL
3. 自動的に再デプロイが開始されます

## これだけ！
データベースは再利用できます！

