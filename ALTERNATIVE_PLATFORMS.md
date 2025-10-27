# Flask アプリを無料でデプロイできるプラットフォーム

## ❌ Netlify は使えません
- Netlify は静的サイト用（HTML/CSS/JS のみ）
- Flask のような動的アプリは不可

## ✅ 推奨プラットフォーム

### 1. Railway.app（最推奨！）
**無料枠**: $5/月のクレジット（無料）
- 自動デプロイ
- データベース自動設定
- とても簡単

**セットアップ**:
1. https://railway.app にアクセス
2. GitHub でログイン
3. 「New Project」→ 「Deploy from GitHub」
4. `ATD` リポジトリを選択
5. 完了！

### 2. Fly.io
**無料枠**: 3VM まで無料
- 月150MB 転送無料
- 若干複雑

### 3. Render.com（現在使用中）
**無料枠**: あり
- 15分でスリープ
- PostgreSQL は $5/月必要（無料ならSQLite使用）

## 💡 最善の解決策

**Option A: SQLite を使用（完全無料）**
- データベースを Render のファイルシステムに保存
- 無料で使える
- ただし、スリープするとデータが消える可能性あり

**Option B: Railway に移行（完全無料）**
- 無料枠で十分に動く
- データベースも無料

**Option C: Render の PostgreSQL を有料にする**
- $5/月
- データベースが確実に残る

## 推奨
**Railway に移行** が最も簡単で確実です！
