"""LLM統合ヘルパー（Groq API使用）"""
import os
from config import Config

def generate_llm_response(user_message, goal=None, conversation_history=None, use_llm=True):
    """
    LLMを使って自然な返答を生成
    
    Args:
        user_message: ユーザーのメッセージ
        goal: 目標・目的
        conversation_history: 会話履歴（リスト）
        use_llm: LLMを使用するかどうか（Falseの場合はルールベース）
    
    Returns:
        アシスタントの返答
    """
    # APIキーがない場合、またはLLMを使用しない場合はルールベースにフォールバック
    if not use_llm or not Config.GROQ_API_KEY:
        from brainstorm import generate_response_message
        return generate_response_message(user_message, goal, conversation_history or [])
    
    try:
        from groq import Groq
        
        client = Groq(api_key=Config.GROQ_API_KEY)
        
        # システムプロンプトを構築
        system_prompt = """あなたは目標達成をサポートするアシスタントです。
ユーザーと会話しながら、目標を達成するための具体的なタスクを提案する役割を担っています。

以下の役割を果たしてください：
1. ユーザーの目標や意図を理解する
2. 目標達成のために必要なステップを考える
3. 具体的で実行可能なタスクを提案する
4. 自然で親しみやすい会話を心がける

返答は簡潔に（200文字以内）お願いします。
タスクを提案する場合は、「〜をする」「〜を確認する」などの具体的な行動を示してください。"""
        
        # 会話履歴を構築
        messages = []
        
        # システムメッセージを追加
        if goal:
            system_prompt += f"\n\n現在の目標: {goal}"
        messages.append({"role": "system", "content": system_prompt})
        
        # 会話履歴を追加（直近10件まで）
        if conversation_history:
            recent_history = conversation_history[-10:]  # 最新10件のみ
            for msg in recent_history:
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    messages.append({
                        "role": "user" if msg.role == "user" else "assistant",
                        "content": msg.content
                    })
                elif isinstance(msg, dict):
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
        
        # 現在のユーザーメッセージを追加
        messages.append({"role": "user", "content": user_message})
        
        # LLMにリクエスト
        response = client.chat.completions.create(
            model=Config.GROQ_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=300,
            top_p=1.0,
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        # エラーが発生した場合はルールベースにフォールバック
        print(f"LLM API Error: {e}")
        from brainstorm import generate_response_message
        return generate_response_message(user_message, goal, conversation_history or [])


def suggest_tasks_with_llm(user_message, goal=None, conversation_history=None, use_llm=True):
    """
    LLMを使ってタスクを提案
    
    Args:
        user_message: ユーザーのメッセージ
        goal: 目標・目的
        conversation_history: 会話履歴
        use_llm: LLMを使用するかどうか
    
    Returns:
        提案されたタスクのリスト
    """
    # APIキーがない場合、またはLLMを使用しない場合はルールベースにフォールバック
    if not use_llm or not Config.GROQ_API_KEY:
        from brainstorm import suggest_tasks_from_conversation
        return suggest_tasks_from_conversation(conversation_history or [], goal)
    
    try:
        from groq import Groq
        
        client = Groq(api_key=Config.GROQ_API_KEY)
        
        # 会話履歴を結合
        conversation_text = ""
        if conversation_history:
            for msg in conversation_history[-5:]:  # 最新5件のみ
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    role = "ユーザー" if msg.role == "user" else "アシスタント"
                    conversation_text += f"{role}: {msg.content}\n"
                elif isinstance(msg, dict):
                    role = "ユーザー" if msg.get("role") == "user" else "アシスタント"
                    conversation_text += f"{role}: {msg.get('content', '')}\n"
        
        # システムプロンプト
        system_prompt = f"""あなたは目標達成のためのタスク提案アシスタントです。

目標: {goal if goal else '未設定'}

会話内容を分析して、目標達成のために必要な具体的なタスクを提案してください。

以下の形式でJSON配列を返してください（各タスクは1行、タイトルのみ）:
[
  "タスク1のタイトル",
  "タスク2のタイトル",
  "タスク3のタイトル"
]

タスクは：
- 具体的で実行可能なもの
- 目標達成に直接関係するもの
- 3-8個程度
- 50文字以内

JSONのみを返してください（説明不要）。"""
        
        # ユーザーメッセージを構築
        user_prompt = f"""以下の会話内容から、目標達成のために必要なタスクを提案してください。

{conversation_text}

現在のメッセージ: {user_message}

上記の形式でタスクのJSON配列を返してください。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # LLMにリクエスト
        response = client.chat.completions.create(
            model=Config.GROQ_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )
        
        content = response.choices[0].message.content.strip()
        
        # JSONをパース（JSON形式でない場合も対応）
        import json
        import re
        
        # JSON配列を抽出
        json_match = re.search(r'\[.*?\]', content, re.DOTALL)
        if json_match:
            try:
                tasks = json.loads(json_match.group())
                return [
                    {
                        'title': task if isinstance(task, str) else task.get('title', str(task)),
                        'description': '',
                        'priority': 'medium',
                        'suggested_date': None
                    }
                    for task in tasks if task
                ]
            except (json.JSONDecodeError, AttributeError):
                pass
        
        # JSON形式でない場合は、行ごとに分割
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        tasks = []
        for line in lines:
            # 番号や記号を除去
            line = re.sub(r'^[-*•\d\.\)]+', '', line).strip()
            line = line.strip('"\'')
            # 不要な文字を除去
            line = re.sub(r'^["\']|["\']$', '', line)  # 前後の引用符を除去
            if line and 3 <= len(line) <= 50 and not line.startswith('[') and not line.startswith('{'):
                tasks.append({
                    'title': line,
                    'description': '',
                    'priority': 'medium',
                    'suggested_date': None
                })
        
        # タスクがない場合のフォールバック
        if not tasks:
            # 目標から基本的なタスクを提案
            if goal:
                return [
                    {
                        'title': f'{goal[:30]}の実現',
                        'description': goal,
                        'priority': 'medium',
                        'suggested_date': None
                    }
                ]
            # 会話から基本的なタスクを抽出
            from brainstorm import suggest_tasks_from_conversation
            return suggest_tasks_from_conversation(conversation_history or [], goal)
        
        return tasks[:8]  # 最大8個まで
    
    except Exception as e:
        # エラーが発生した場合はルールベースにフォールバック
        print(f"LLM Task Suggestion Error: {e}")
        from brainstorm import suggest_tasks_from_conversation
        return suggest_tasks_from_conversation(conversation_history or [], goal)

