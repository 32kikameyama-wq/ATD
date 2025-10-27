# ATD システム

## 概要
WEB SaaS 型のタスク管理アプリケーション

## セットアップ手順

### 1. リポジトリのクローン
```bash
git clone https://github.com/32kikameyama-wq/ATD.git
cd ATD
```

### 2. 仮想環境の作成
```bash
# 仮想環境を作成
python3 -m venv venv

# 仮想環境をアクティベート
# macOS/Linux:
source venv/bin/activate

# Windows:
# venv\Scripts\activate
```

### 3. 依存パッケージのインストール
```bash
pip install -r requirements.txt
```

## 開発

### アプリケーションの起動
```bash
# 仮想環境をアクティベート
source venv/bin/activate

# Flask アプリを起動
python app.py

# ブラウザで http://localhost:5001 にアクセス
```

### 仮想環境の使い方
- 開発を開始する前に `source venv/bin/activate` で仮想環境をアクティベート
- 開発終了時は `deactivate` で仮想環境を終了

### 新しいパッケージのインストール
```bash
pip install <パッケージ名>
pip freeze > requirements.txt
```
