# ATD システム

## 概要
ATD システムのプロジェクトリポジトリです。

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

### 仮想環境の使い方
- 開発を開始する前に `source venv/bin/activate` で仮想環境をアクティベート
- 開発終了時は `deactivate` で仮想環境を終了

### 新しいパッケージのインストール
```bash
pip install <パッケージ名>
pip freeze > requirements.txt
```

## Git 運用

### 初回セットアップ後のコミット
```bash
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/32kikameyama-wq/ATD.git
git push -u origin main
```

### 通常のワークフロー
```bash
# 変更をステージング
git add .

# コミット
git commit -m "コミットメッセージ"

# プッシュ
git push
```

## ライセンス
MIT License
