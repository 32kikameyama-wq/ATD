# Groq API設定ガイド（無料LLM統合）

## Groq APIとは？

Groq APIは高速で無料枠の大きいLLM APIサービスです。
- **完全無料**: 毎月かなり大きな無料枠
- **高速**: Llama 3などのモデルを高速で実行
- **簡単**: APIキーを取得するだけですぐ使える

## 設定手順

### 1. Groq APIキーを取得

1. **Groq Consoleにアクセス**
   - https://console.groq.com/ にアクセス
   - GitHubまたはGoogleアカウントでサインアップ

2. **APIキーを作成**
   - ダッシュボード → "API Keys" をクリック
   - "Create API Key" をクリック
   - キーをコピー（**この時だけ表示されます**）

### 2. 環境変数に設定

#### ローカル環境（.envファイル）

プロジェクトのルートディレクトリに `.env` ファイルを作成：

```bash
# .env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### 本番環境（Render.comなど）

デプロイ環境の環境変数に追加：

| Key | Value |
|-----|-------|
| `GROQ_API_KEY` | `gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |

### 3. 依存関係をインストール

```bash
pip install groq==0.4.1
```

または

```bash
pip install -r requirements.txt
```

### 4. 動作確認

1. アプリを起動
2. 壁打ちページにアクセス
3. 会話を開始
4. 自然な返答が返ってくることを確認

## 注意事項

- **APIキーがない場合**: 既存のルールベースシステムが自動的に使用されます
- **エラー発生時**: 自動的にルールベースにフォールバックします
- **無料枠**: 個人利用なら十分すぎるほどの無料枠があります

## 使用モデル

デフォルトでは以下のモデルを使用します：
- `llama-3.1-8b-instant`: 高速で無料枠が大きい（推奨）

他のモデルも使用可能：
- `llama-3.1-70b-versatile`: より高性能（無料枠は小さい）
- `mixtral-8x7b-32768`: 長い会話に適している

`.env`で変更可能：
```
GROQ_MODEL=llama-3.1-70b-versatile
```

## トラブルシューティング

### LLMが動作しない

1. **APIキーを確認**
   ```bash
   # .envファイルに正しく設定されているか確認
   cat .env | grep GROQ
   ```

2. **エラーログを確認**
   - アプリのコンソール出力を確認
   - エラーが表示されている場合は自動的にルールベースにフォールバック

3. **フォールバック確認**
   - APIキーがない場合、自動的にルールベースシステムが動作します
   - エラーが発生してもアプリは正常に動作します

## 参考リンク

- Groq Console: https://console.groq.com/
- Groq API ドキュメント: https://console.groq.com/docs
- 無料枠の詳細: Groq Consoleで確認

