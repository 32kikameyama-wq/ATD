"""壁打ちタスク提案ロジック"""
import re
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta

def extract_date_from_text(text):
    """テキストから日付を抽出"""
    today = date.today()
    current_year = today.year
    current_month = today.month
    
    # パターン1: "11/4" や "11/04" 形式（月/日）
    pattern1 = r'(\d{1,2})/(\d{1,2})'
    match = re.search(pattern1, text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        try:
            return date(current_year, month, day)
        except ValueError:
            pass
    
    # パターン2: "11月4日" 形式
    pattern2 = r'(\d{1,2})月(\d{1,2})日'
    match = re.search(pattern2, text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        try:
            return date(current_year, month, day)
        except ValueError:
            pass
    
    # パターン3: "来週" "来月" など
    if '来週' in text:
        return today + timedelta(days=7)
    if '来月' in text:
        return today + relativedelta(months=1)
    if '来年' in text:
        return today + relativedelta(years=1)
    
    # パターン4: "○日後" 形式
    pattern4 = r'(\d+)日後'
    match = re.search(pattern4, text)
    if match:
        days = int(match.group(1))
        return today + timedelta(days=days)
    
    return None


def parse_duration(text):
    """期間を解析（1ヶ月分日割りなど）"""
    # "1ヶ月分日割り" を検出
    if '1ヶ月分' in text or '1か月分' in text or '1ヵ月分' in text:
        if '日割り' in text:
            return 'monthly_daily'
    
    # "1週間分" など
    if '1週間分' in text:
        if '日割り' in text:
            return 'weekly_daily'
    
    return None


def suggest_tasks_from_conversation(messages, goal=None):
    """会話履歴からタスクを提案"""
    suggested_tasks = []
    
    # 会話全体を結合
    conversation_text = ' '.join([msg.content for msg in messages if msg.role == 'user'])
    full_text = (goal or '') + ' ' + conversation_text
    
    # 数値目標の抽出（例：50件、100個など）
    number_pattern = r'(\d+)(?:件|個|回|人|本|枚|%|万円|万円)'
    number_matches = list(re.finditer(number_pattern, full_text))
    
    # 営業・セールス関連のキーワード
    sales_keywords = ['営業', 'セールス', '制約', '成約', '獲得', '契約', '商談', '顧客', '見込み客', 'リスト']
    
    # 営業目標の場合の具体的なタスク
    if any(keyword in full_text for keyword in sales_keywords) and number_matches:
        # 数値目標を取得
        target_number = None
        for match in number_matches:
            if '件' in match.group(0) or '個' in match.group(0) or '人' in match.group(0):
                target_number = int(match.group(1))
                break
        
        if target_number:
            # 営業活動の典型的なタスクを提案
            daily_target = max(1, target_number // 30)  # 月間目標を日割り
            
            suggested_tasks.extend([
                {
                    'title': '見込み客リストの作成',
                    'description': f'{target_number}件達成のための見込み客リストを作成',
                    'priority': 'high',
                    'suggested_date': None
                },
                {
                    'title': 'アポイント獲得活動',
                    'description': f'1日{daily_target}件のアポイント獲得を目標',
                    'priority': 'high',
                    'suggested_date': None
                },
                {
                    'title': '商談実施',
                    'description': f'1日{daily_target}件の商談を実施',
                    'priority': 'high',
                    'suggested_date': None
                },
                {
                    'title': 'フォローアップ・クロージング',
                    'description': '商談後のフォローアップとクロージング活動',
                    'priority': 'high',
                    'suggested_date': None
                },
            ])
    
    # キーワードベースのタスク提案
    task_keywords = [
        ('作成', ['作成', '作る', '開発', '実装']),
        ('調査', ['調査', '調べる', '研究', 'リサーチ']),
        ('確認', ['確認', 'チェック', '検証']),
        ('修正', ['修正', '直す', '改善', 'リファクタ']),
        ('テスト', ['テスト', '検証', '試す']),
        ('レビュー', ['レビュー', '確認', '見直し']),
        ('デザイン', ['デザイン', '設計', 'レイアウト']),
        ('ドキュメント', ['ドキュメント', '資料', '文書']),
        ('ミーティング', ['ミーティング', '会議', '打ち合わせ']),
        ('連絡', ['連絡', '報告', '共有']),
    ]
    
    # 目標・目的からタスクを提案
    if goal:
        # 目標を分析して具体的なタスクを提案
        goal_lower = goal.lower()
        
        # 各キーワードパターンとマッチするかチェック
        for keyword, patterns in task_keywords:
            for pattern in patterns:
                if pattern in goal_lower or pattern in conversation_text.lower():
                    # 既に追加されていないかチェック
                    if not any(s.get('title', '').startswith(keyword) for s in suggested_tasks):
                        suggested_tasks.append({
                            'title': f'{keyword}タスク',
                            'description': goal if goal else f'{keyword}に関する作業',
                            'priority': 'medium',
                            'suggested_date': None
                        })
                    break
    
    # 会話から具体的なタスクを抽出
    # 「○○を○○する」のようなパターンを探す
    action_patterns = [
        r'([^。、]+)(?:を|が)(?:する|作成|実装|開発|調査|確認|修正|テスト|レビュー|デザイン|作成する|実装する|開発する|調査する|確認する|修正する|テストする|レビューする|デザインする)',
        r'([^。、]+)(?:を|が)(?:やる|やった|完了)',
    ]
    
    for pattern in action_patterns:
        matches = re.finditer(pattern, conversation_text)
        for match in matches:
            task_desc = match.group(0).strip()
            # 短すぎる、長すぎるものは除外
            if 5 <= len(task_desc) <= 100:
                # 重複チェック
                if not any(s.get('title', '') == task_desc for s in suggested_tasks):
                    suggested_tasks.append({
                        'title': task_desc[:50],  # タイトルは50文字まで
                        'description': '',
                        'priority': 'medium',
                        'suggested_date': None
                    })
    
    # 日付が指定されている場合は追加
    for msg in messages:
        if msg.role == 'user':
            date_obj = extract_date_from_text(msg.content)
            if date_obj and suggested_tasks:
                # 最後の提案タスクに日付を追加
                suggested_tasks[-1]['suggested_date'] = date_obj
    
    # 提案がない場合は、目標から基本的なタスクを提案
    if not suggested_tasks and goal:
        suggested_tasks.append({
            'title': f'{goal[:30]}の実現',
            'description': goal,
            'priority': 'medium',
            'suggested_date': None
        })
    
    return suggested_tasks


def generate_response_message(user_message, goal=None, messages=None, has_suggested_tasks=False, suggested_task_count=0):
    """ユーザーメッセージに対する返信を生成（シンプルなルールベース）"""
    message_lower = user_message.lower()
    
    # タスクが提案された場合
    if has_suggested_tasks and suggested_task_count > 0:
        if suggested_task_count == 1:
            return f"タスクを1件提案しました。「タスクにする」ボタンからタスク化できます。"
        else:
            return f"タスクを{suggested_task_count}件提案しました。「タスクにする」ボタンからタスク化できます。"
    
    # タスクの提案を求める場合
    if any(word in message_lower for word in ['タスク', 'やること', 'やるべき', 'すべき', '候補', '提案']):
        if '候補' in message_lower or '提案' in message_lower:
            return "会話内容を分析してタスクを提案します。少しお待ちください..."
        return "会話内容からタスクを抽出します。右下の「タスクにする」ボタンからタスク化できます。"
    
    # 目標や目的に関する質問
    if any(word in message_lower for word in ['目標', '目的', '何をする', 'どうする']):
        if goal:
            return f"現在の目標は「{goal}」です。これを達成するために、どんな行動が必要でしょうか？"
        return "目標や目的を教えてください。それに基づいてタスクを提案します。"
    
    # 数値や具体的な目標が含まれている場合
    if any(word in message_lower for word in ['件', '個', '回', '日', '月', '年', '達成', '目標', '実現']):
        if '件' in message_lower or '制約' in message_lower or '達成' in message_lower:
            return "なるほど、具体的な数値目標ですね。それを達成するために必要なステップを考えましょう。どのようなアプローチを取りますか？"
        return "具体的な数値目標を設定されましたね。それに向けて、どんな行動が必要でしょうか？"
    
    # まだ何をするかわからない場合
    if any(word in message_lower for word in ['わからない', '不明', '不確実', '曖昧']):
        return "具体的に何をしたいかを教えてください。目標や目的から細かく分解してタスクを作成できます。"
    
    # 肯定・共感の返答
    if any(word in message_lower for word in ['いい', '良い', 'よさそう', '良いね', 'いいね']):
        return "素晴らしいですね！それを実現するために、具体的に何をすべきか考えましょう。"
    
    # 質問や聞きたいことがある場合
    if any(word in message_lower for word in ['教えて', '聞きたい', '知りたい', 'どうやって', 'どうすれば']):
        return "どのような情報が必要でしょうか？目標達成のために必要な情報を整理しましょう。"
    
    # 会話の長さと内容に応じた返答
    if messages and len(messages) > 0:
        # 会話が進んでいる場合、より具体的な質問をする
        if len(messages) >= 4:
            # 目標が設定されている場合
            if goal:
                return f"「{goal}」を達成するために、どのようなステップが必要でしょうか？例えば、情報収集、計画立案、実行、検証などが考えられます。"
            return "会話内容から、具体的なタスクを提案できそうです。何か追加で伝えたいことはありますか？"
        elif len(messages) >= 2:
            # 中間段階：もっと詳しく聞く
            return "もっと詳しく教えていただけますか？具体的な行動計画を立てるために、詳細な情報があると良いです。"
        else:
            # 最初の返答
            return "なるほど。もっと詳しく教えてください。"
    
    # デフォルト返答
    return "目標達成のために、どんなことが必要でしょうか？詳しく教えてください。"


def parse_task_instruction(user_message, messages, goal=None):
    """
    タスク作成指示を解析
    
    例:
    - "このタスクを10日間分入れてください"
    - "1ヶ月分日割りで入れて"
    - "30日間分カレンダーに入れて"
    
    Returns:
        dict: {
            'create_tasks': True/False,
            'task_title': 'タスク名',
            'days': 日数,
            'months': 月数,
            'start_date': 開始日
        }
    """
    message_lower = user_message.lower()
    
    # 「入れて」「入れてください」「追加して」などの指示を検出
    if not any(word in message_lower for word in ['入れて', '追加して', '作成して', '作って']):
        return None
    
    # タスクタイトルを抽出
    task_title = goal or 'タスク'
    
    # 現在のメッセージからタスク名を抽出
    # 「○○のタスク」「○○活動」「○○を」などのパターン
    task_patterns = [
        r'([^。、]+?)(?:のタスク|活動|作業|仕事)',
        r'([^。、]+?)(?:を|が|に)(?:入れて|追加して|作成して|作って)',
        r'この([^。、]+?)を',
        r'([^。、]+?)(?:を|が)(?:する|やる|行う)',
    ]
    
    for pattern in task_patterns:
        match = re.search(pattern, user_message)
        if match and len(match.group(1).strip()) > 2:
            task_title = match.group(1).strip()
            break
    
    # 会話履歴からもタスク名を抽出（現在のメッセージで見つからなかった場合）
    if task_title == 'タスク' and messages:
        for msg in reversed(messages):
            if hasattr(msg, 'role') and msg.role == 'user':
                content = msg.content
                # 「○○を」などのタスク名を抽出
                task_match = re.search(r'([^。、]+)(?:を|が|に)', content)
                if task_match and len(task_match.group(1)) > 3:
                    task_title = task_match.group(1).strip()
                    break
            elif isinstance(msg, dict) and msg.get('role') == 'user':
                content = msg.get('content', '')
                task_match = re.search(r'([^。、]+)(?:を|が|に)', content)
                if task_match and len(task_match.group(1)) > 3:
                    task_title = task_match.group(1).strip()
                    break
    
    # 日数を抽出
    days = 0
    months = 0
    
    # パターン1: "○日間分" "○日分" "○日"
    days_patterns = [
        r'(\d+)(?:日間|日|日分)',
        r'(\d+)日間分',
    ]
    for pattern in days_patterns:
        match = re.search(pattern, user_message)
        if match:
            days = int(match.group(1))
            break
    
    # パターン2: "○ヶ月分" "○か月分" "○ヵ月分"
    months_patterns = [
        r'(\d+)(?:ヶ月|か月|ヵ月|カ月)(?:分|間)',
        r'(\d+)ヶ月分',
    ]
    for pattern in months_patterns:
        match = re.search(pattern, user_message)
        if match:
            months = int(match.group(1))
            break
    
    # 「1ヶ月分日割り」などの特殊パターン
    if '1ヶ月分' in message_lower or '1か月分' in message_lower:
        months = 1
        days = 0  # 月指定の場合は日数を0に
    
    # 開始日を抽出
    start_date = extract_date_from_text(user_message)
    if not start_date:
        from datetime import date
        start_date = date.today()
    
    # 指示がある場合のみ返す
    if days > 0 or months > 0 or '入れて' in message_lower or '追加して' in message_lower:
        return {
            'create_tasks': True,
            'task_title': task_title,
            'days': days,
            'months': months,
            'start_date': start_date
        }
    
    return None

