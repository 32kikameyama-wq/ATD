#!/usr/bin/env python3
"""
データベースバックアップスクリプト
使用方法: python backup_db.py
"""

import shutil
import os
from datetime import datetime

def backup_database():
    """データベースをバックアップ"""
    source_db = "instance/atd.db"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = "backups"
    backup_file = f"{backup_dir}/atd_backup_{timestamp}.db"
    
    # バックアップディレクトリ作成
    os.makedirs(backup_dir, exist_ok=True)
    
    # データベースファイルをコピー
    if os.path.exists(source_db):
        shutil.copy2(source_db, backup_file)
        print(f"✅ バックアップ完了: {backup_file}")
        return backup_file
    else:
        print("❌ データベースファイルが見つかりません")
        return None

def restore_database(backup_file):
    """データベースを復元"""
    source_db = "instance/atd.db"
    
    if os.path.exists(backup_file):
        shutil.copy2(backup_file, source_db)
        print(f"✅ 復元完了: {backup_file}")
    else:
        print("❌ バックアップファイルが見つかりません")

if __name__ == "__main__":
    backup_database()
