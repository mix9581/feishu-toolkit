#!/usr/bin/env python3
"""
Feishu/Lark API Toolkit — 补齐官方 MCP 无法覆盖的能力。

核心能力:
  - 图片上传（官方 MCP 不支持）
  - 富文本消息构建（含 @用户、图片、超链接）
  - 飞书文档创建与 Block 内容写入
  - 交互卡片消息构建
  - 通讯录查询（邮箱/手机号 → open_id）

用法 - 作为模块:
    from feishu_toolkit import FeishuClient
    client = FeishuClient(app_id="cli_xxx", app_secret="xxx")
    client.send_text("oc_xxx", "Hello!")

用法 - 作为 CLI:
    export FEISHU_APP_ID=cli_xxx
    export FEISHU_APP_SECRET=xxx
    python feishu_toolkit.py auth
    python feishu_toolkit.py list-chats
    python feishu_toolkit.py send-text oc_xxx "Hello"
    python feishu_toolkit.py upload-image /path/to/img.png
    python feishu_toolkit.py send-image oc_xxx /path/to/img.png
    python feishu_toolkit.py create-doc "Report Title"

依赖: requests (pip install requests)
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: 'requests' package required. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuAPIError(Exception):
    """飞书 API 返回的业务错误"""
    def __init__(self, code: int, msg: str, data: dict = None):
        self.code = code
        self.msg = msg
        self.data = data or {}
        super().__init__(f"[{code}] {msg}")


class FeishuClient:
    """飞书开放平台 API 客户端"""

    def __init__(self, app_id: str = None, app_secret: str = None, base_url: str = None):
        self.app_id = app_id or os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET", "")
        self.base_url = (base_url or os.environ.get("FEISHU_BASE_URL", BASE_URL)).rstrip("/")
        if not self.app_id or not self.app_secret:
            raise ValueError(
                "app_id/app_secret required. "
                "Pass directly or set FEISHU_APP_ID / FEISHU_APP_SECRET env vars."
            )
        self._token: Optional[str] = None
        self._token_expires_at: float = 0

    @property
    def token(self) -> str:
        """获取 tenant_access_token，自动缓存和续期"""
        if self._token and time.time() < self._token_expires_at:
            return self._token
        resp = requests.post(
            f"{self.base_url}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise FeishuAPIError(data.get("code", -1), data.get("msg", "Auth failed"))
        self._token = data["tenant_access_token"]
        self._token_expires_at = time.time() + data.get("expire", 7200) - 300
        return self._token

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers.setdefault("Authorization", f"Bearer {self.token}")
        resp = requests.request(method, url, headers=headers, **kwargs)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise FeishuAPIError(data.get("code", -1), data.get("msg", "Unknown"), data.get("data"))
        return data

    @staticmethod
    def text(content: str) -> dict:
        return {"tag": "text", "text": content}

    @staticmethod
    def at(user_id: str, user_name: str = "") -> dict:
        return {"tag": "at", "user_id": user_id, "user_name": user_name}

    @staticmethod
    def at_all() -> dict:
        return {"tag": "at", "user_id": "all", "user_name": "所有人"}

    @staticmethod
    def link(text: str, href: str) -> dict:
        return {"tag": "a", "text": text, "href": href}

    @staticmethod
    def img(image_key: str) -> dict:
        return {"tag": "img", "image_key": image_key}

    @staticmethod
    def emotion(emoji_type: str) -> dict:
        return {"tag": "emotion", "emoji_type": emoji_type}

    @staticmethod
    def media(file_key: str, image_key: str) -> dict:
        return {"tag": "media", "file_key": file_key, "image_key": image_key}

    def _send_message(self, receive_id: str, msg_type: str, content: dict, receive_id_type: str = "chat_id") -> dict:
        return self._request(
            "POST",
            f"/im/v1/messages?receive_id_type={receive_id_type}",
            json={
                "receive_id": receive_id,
                "msg_type": msg_type,
                "content": json.dumps(content, ensure_ascii=False),
            },
        )

    def send_text(self, receive_id: str, text: str, receive_id_type: str = "chat_id") -> dict:
        return self._send_message(receive_id, "text", {"text": text}, receive_id_type)

    def send_rich_text(self, receive_id: str, title: str, content: list[list[dict]], receive_id_type: str = "chat_id", lang: str = "zh_cn") -> dict:
        return self._send_message(
            receive_id, "post", {lang: {"title": title, "content": content}}, receive_id_type
        )

    def send_image(self, receive_id: str, image_key: str, receive_id_type: str = "chat_id") -> dict:
        return self._send_message(receive_id, "image", {"image_key": image_key}, receive_id_type)

    def send_card(self, receive_id: str, card: dict, receive_id_type: str = "chat_id") -> dict:
        return self._send_message(receive_id, "interactive", card, receive_id_type)

    def upload_image(self, image_path: str) -> str:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        with open(path, "rb") as f:
            resp = requests.post(
                f"{self.base_url}/im/v1/images",
                headers={"Authorization": f"Bearer {self.token}"},
                data={"image_type": "message"},
                files={"image": (path.name, f)},
            )
        data = resp.json()
        if data.get("code") != 0:
            raise FeishuAPIError(data.get("code", -1), data.get("msg", "Upload failed"))
        return data["data"]["image_key"]

    def get_user_ids(self, emails: list[str] = None, mobiles: list[str] = None) -> list[dict]:
        body = {}
        if emails:
            body["emails"] = emails
        if mobiles:
            body["mobiles"] = mobiles
        data = self._request(
            "POST",
            "/contact/v3/users/batch_get_id?user_id_type=open_id",
            json=body,
        )
        return data.get("data", {}).get("user_list", [])

    def get_user_id_by_email(self, email: str) -> Optional[str]:
        users = self.get_user_ids(emails=[email])
        return users[0].get("user_id") if users else None

    def get_user_id_by_mobile(self, mobile: str) -> Optional[str]:
        users = self.get_user_ids(mobiles=[mobile])
        return users[0].get("user_id") if users else None

    def list_chats(self, page_size: int = 50) -> list[dict]:
        data = self._request("GET", f"/im/v1/chats?page_size={page_size}")
        return data.get("data", {}).get("items", [])

    def create_document(self, title: str, folder_token: str = None) -> dict:
        body = {"title": title}
        if folder_token:
            body["folder_token"] = folder_token
        data = self._request("POST", "/docx/v1/documents", json=body)
        return data["data"]["document"]

    def get_document_root_block(self, document_id: str) -> str:
        data = self._request("GET", f"/docx/v1/documents/{document_id}/blocks")
        items = data.get("data", {}).get("items", [])
        for item in items:
            if item.get("block_type") == 1:
                return item["block_id"]
        return document_id

    def add_document_blocks(self, document_id: str, parent_block_id: str, children: list[dict], index: int = -1) -> dict:
        body = {"children": children}
        if index >= 0:
            body["index"] = index
        return self._request(
            "POST",
            f"/docx/v1/documents/{document_id}/blocks/{parent_block_id}/children",
            json=body,
        )

    def create_document_with_content(self, title: str, blocks: list[dict], folder_token: str = None) -> dict:
        doc = self.create_document(title, folder_token)
        doc_id = doc["document_id"]
        root_block = self.get_document_root_block(doc_id)
        if blocks:
            self.add_document_blocks(doc_id, root_block, blocks)
        return {"document_id": doc_id, "url": f"https://feishu.cn/docx/{doc_id}"}

    @staticmethod
    def text_block(content: str) -> dict:
        return {"block_type": 2, "text": {"elements": [{"text_run": {"content": content}}], "style": {}}}

    @staticmethod
    def heading_block(content: str, level: int = 1) -> dict:
        level = max(1, min(9, level))
        block_type = 2 + level
        field = f"heading{level}"
        return {"block_type": block_type, field: {"elements": [{"text_run": {"content": content}}]}}

    @staticmethod
    def code_block(code: str, language: int = 49) -> dict:
        return {
            "block_type": 14,
            "code": {"elements": [{"text_run": {"content": code}}], "style": {"language": language}},
        }

    @staticmethod
    def bullet_block(content: str) -> dict:
        return {"block_type": 12, "bullet": {"elements": [{"text_run": {"content": content}}]}}

    @staticmethod
    def ordered_block(content: str) -> dict:
        return {"block_type": 13, "ordered": {"elements": [{"text_run": {"content": content}}]}}

    @staticmethod
    def quote_block(content: str) -> dict:
        return {"block_type": 15, "quote": {"elements": [{"text_run": {"content": content}}]}}

    @staticmethod
    def divider_block() -> dict:
        return {"block_type": 22}

    @staticmethod
    def build_card(title: str, elements: list[dict], color: str = "blue") -> dict:
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"content": title, "tag": "plain_text"}, "template": color},
            "elements": elements,
        }

    @staticmethod
    def card_markdown(content: str) -> dict:
        return {"tag": "div", "text": {"content": content, "tag": "lark_md"}}

    @staticmethod
    def card_fields(fields: list[tuple[str, bool]]) -> dict:
        return {
            "tag": "div",
            "fields": [
                {"is_short": short, "text": {"content": text, "tag": "lark_md"}}
                for text, short in fields
            ],
        }

    @staticmethod
    def card_button(text: str, url: str, button_type: str = "primary") -> dict:
        return {
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"content": text, "tag": "plain_text"},
                "type": button_type,
                "url": url,
            }],
        }

    @staticmethod
    def card_divider() -> dict:
        return {"tag": "hr"}

    def create_bitable(self, name: str, folder_token: str = None) -> dict:
        body = {"name": name}
        if folder_token:
            body["folder_token"] = folder_token
        return self._request("POST", "/bitable/v1/apps", json=body)

    def list_bitable_tables(self, app_token: str) -> list[dict]:
        data = self._request("GET", f"/bitable/v1/apps/{app_token}/tables")
        return data.get("data", {}).get("items", [])

    def create_bitable_records(self, app_token: str, table_id: str, records: list[dict]) -> dict:
        return self._request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            json={"records": records},
        )

    def search_bitable_records(self, app_token: str, table_id: str, filter_: dict = None, sort: list = None, page_size: int = 20) -> dict:
        body = {"page_size": page_size}
        if filter_:
            body["filter"] = filter_
        if sort:
            body["sort"] = sort
        return self._request(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
            json=body,
        )


def _print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Feishu Toolkit CLI", formatter_class=argparse.RawDescriptionHelpFormatter, epilog="Environment variables: FEISHU_APP_ID, FEISHU_APP_SECRET")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("auth", help="测试认证，获取 tenant_access_token")
    sub.add_parser("list-chats", help="列出机器人已加入的群组")

    p = sub.add_parser("send-text", help="发送文本消息")
    p.add_argument("chat_id", help="群组 chat_id 或用户 open_id")
    p.add_argument("text", help="消息文本")
    p.add_argument("--type", default="chat_id", dest="id_type", choices=["chat_id", "open_id", "union_id", "email"], help="receive_id 类型 (默认 chat_id)")

    p = sub.add_parser("upload-image", help="上传图片，返回 image_key")
    p.add_argument("image_path", help="图片文件路径")

    p = sub.add_parser("send-image", help="上传并发送图片消息")
    p.add_argument("chat_id", help="群组 chat_id")
    p.add_argument("image_path", help="图片文件路径")

    p = sub.add_parser("get-user-id", help="通过邮箱/手机号查询 open_id")
    p.add_argument("--email", help="用户邮箱")
    p.add_argument("--mobile", help="用户手机号")

    p = sub.add_parser("create-doc", help="创建飞书文档")
    p.add_argument("title", help="文档标题")
    p.add_argument("--folder", help="目标文件夹 token", default=None)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    try:
        client = FeishuClient()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.command == "auth":
            token = client.token
            print(f"Auth OK. Token: {token[:20]}...{token[-6:]}")
            print(f"App ID: {client.app_id}")
        elif args.command == "list-chats":
            chats = client.list_chats()
            if not chats:
                print("No chats found. Make sure the bot has been added to at least one group.")
            for c in chats:
                print(f"  {c.get('chat_id')}  |  {c.get('name', 'N/A')}  |  owner: {c.get('owner_id', 'N/A')}")
        elif args.command == "send-text":
            result = client.send_text(args.chat_id, args.text, args.id_type)
            _print_json(result)
            print("Message sent successfully.")
        elif args.command == "upload-image":
            key = client.upload_image(args.image_path)
            print(f"image_key: {key}")
        elif args.command == "send-image":
            key = client.upload_image(args.image_path)
            result = client.send_image(args.chat_id, key)
            _print_json(result)
            print("Image sent successfully.")
        elif args.command == "get-user-id":
            emails = [args.email] if args.email else None
            mobiles = [args.mobile] if args.mobile else None
            if not emails and not mobiles:
                print("Error: --email or --mobile required", file=sys.stderr)
                sys.exit(1)
            users = client.get_user_ids(emails=emails, mobiles=mobiles)
            _print_json(users)
        elif args.command == "create-doc":
            doc = client.create_document(args.title, args.folder)
            doc_id = doc["document_id"]
            print(f"Document created: {doc_id}")
            print(f"URL: https://feishu.cn/docx/{doc_id}")
    except FeishuAPIError as e:
        print(f"Feishu API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.HTTPError as e:
        print(f"HTTP Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
