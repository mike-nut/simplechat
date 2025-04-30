# lambda/index.py
import json
import os
import boto3
import re  # 正規表現モジュールをインポート
from botocore.exceptions import ClientError
import requests


# Lambda コンテキストからリージョンを抽出する関数
def extract_region_from_arn(arn):
    # ARN 形式: arn:aws:lambda:region:account-id:function:function-name
    match = re.search('arn:aws:lambda:([^:]+):', arn)
    if match:
        return match.group(1)
    return "us-east-1"  # デフォルト値

# FastAPI推論サービスのエンドポイント
FASTAPI_ENDPOINT = os.environ.get("FASTAPI_ENDPOINT", "https://a403-35-188-241-50.ngrok-free.app")


def lambda_handler(event, context):
    try:
        
        print("Received event:", json.dumps(event))
        
        # Cognitoで認証されたユーザー情報を取得
        user_info = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            user_info = event['requestContext']['authorizer']['claims']
            print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")
        
        # リクエストボディの解析
        body = json.loads(event['body'])
        message = body['message']
        conversation_history = body.get('conversationHistory', [])
        
        print("Processing message:", message)
        print("Using FastAPI endpoint:", FASTAPI_ENDPOINT)
        
        # 会話履歴を使用してプロンプトを構築
        prompt = message
        if conversation_history:
            # 簡易的な会話履歴の組み込み (必要に応じてカスタマイズ)
            context_messages = []
            for msg in conversation_history:
                if msg["role"] == "user":
                    context_messages.append(f"ユーザー: {msg['content']}")
                elif msg["role"] == "assistant":
                    context_messages.append(f"アシスタント: {msg['content']}")
            
            # 会話の文脈をプロンプトに追加（必要に応じて調整）
            if context_messages:
                prompt = "\n".join(context_messages) + f"\nユーザー: {message}"
        
        # FastAPI推論サービスへのリクエストを構築
        request_payload = {
            "prompt": prompt,
            "max_new_tokens": 512,
            "temperature": 0.7,
            "top_p": 0.9,
            "do_sample": True
        }
        
        print("Calling FastAPI service with payload:", json.dumps(request_payload))
        
        # FastAPI推論サービスへのリクエスト
        response = requests.post(
            f"{FASTAPI_ENDPOINT}/generate",
            json=request_payload,
            timeout=60  # タイムアウトを60秒に設定
        )
        
        # エラーチェック
        if response.status_code != 200:
            raise Exception(f"FastAPI service returned error: {response.status_code} - {response.text}")
        
        # レスポンスを解析
        response_body = response.json()
        print("FastAPI response:", json.dumps(response_body, default=str))
        
        # 応答の検証
        if not response_body.get('generated_text'):
            raise Exception("No response content from the model")
        
        # アシスタントの応答を取得
        assistant_response = response_body['generated_text']
        
        # アシスタントの応答を会話履歴に追加
        messages = conversation_history.copy()
        messages.append({
            "role": "user",
            "content": message
        })
        messages.append({
            "role": "assistant",
            "content": assistant_response
        })
        
        # 成功レスポンスの返却
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": assistant_response,
                "conversationHistory": messages
            })
        }
        
    except Exception as error:
        print("Error:", str(error))
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": False,
                "error": str(error)
            })
        }
