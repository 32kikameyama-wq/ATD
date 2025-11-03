#!/bin/bash
# ATDシステム データバックアップスクリプト

# カラーコード
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 設定
BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE="instance/atd.db"

echo "============================================="
echo "ATDシステム データバックアップスクリプト"
echo "============================================="
echo ""

# データベースファイルの存在確認
if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}❌ エラー: データベースファイルが見つかりません${NC}"
    echo "   ファイル: $DB_FILE"
    exit 1
fi

# バックアップディレクトリ作成
mkdir -p "$BACKUP_DIR"
if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}❌ エラー: バックアップディレクトリの作成に失敗しました${NC}"
    exit 1
fi

# バックアップファイル名
BACKUP_FILE="$BACKUP_DIR/atd_$DATE.db"

# バックアップ実行
echo "📦 バックアップを実行しています..."
cp "$DB_FILE" "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    # バックアップサイズを取得
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}✅ バックアップ完了！${NC}"
    echo "   ファイル: $BACKUP_FILE"
    echo "   サイズ: $BACKUP_SIZE"
    
    # バックアップ数のカウント
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/atd_*.db 2>/dev/null | wc -l | xargs)
    echo "   保持バックアップ数: $BACKUP_COUNT個"
    
    # 古いバックアップ（30日以上）を削除
    echo ""
    echo "🧹 古いバックアップを削除しています..."
    DELETED=$(find "$BACKUP_DIR" -name "atd_*.db" -mtime +30 -delete -print | wc -l | xargs)
    
    if [ "$DELETED" -gt 0 ]; then
        echo -e "${YELLOW}   削除されたバックアップ: ${DELETED}個${NC}"
    else
        echo "   削除されたバックアップ: なし"
    fi
    
    # データベースの整合性チェック
    echo ""
    echo "🔍 データベースの整合性を確認しています..."
    if command -v sqlite3 &> /dev/null; then
        INTEGRITY_CHECK=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" 2>/dev/null)
        if [ "$INTEGRITY_CHECK" = "ok" ]; then
            echo -e "${GREEN}✅ データベースの整合性: OK${NC}"
        else
            echo -e "${RED}⚠️  データベースの整合性に問題がある可能性があります${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  sqlite3コマンドが見つかりません（整合性チェックをスキップ）${NC}"
    fi
    
    echo ""
    echo "============================================="
    echo -e "${GREEN}🎉 バックアップ処理が正常に完了しました！${NC}"
    echo "============================================="
else
    echo -e "${RED}❌ エラー: バックアップに失敗しました${NC}"
    exit 1
fi

