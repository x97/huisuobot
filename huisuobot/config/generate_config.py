import os
import json
import secrets
from pathlib import Path


def generate_secret_key():
    """生成安全的密钥"""
    return secrets.token_urlsafe(50)


def get_input_with_default(prompt, default):
    """获取用户输入，提供默认值"""
    user_input = input(f"{prompt} [{default}]: ").strip()
    return user_input if user_input else default


def generate_config_file():
    """生成 config.json 文件"""
    base_dir = Path(__file__).resolve().parent.parent
    config_file = base_dir / "config.json"

    print("🎯 开始生成 Django 配置文件 config.json")
    print("=" * 50)

    # Django 基础配置
    print("\n📝 请输入 Django 配置:")
    secret_key = get_input_with_default("SECRET_KEY (留空自动生成)", "")
    if not secret_key:
        secret_key = generate_secret_key()
        print("🔑 已自动生成 SECRET_KEY")

    #REPORT_DEFAULT_USER_ID
    report_user_id =  get_input_with_default("REPORT_DEFAULT_USER_ID (默认报告提交者id)",
6809648292)
    # -----------------------------
    # ALLOWED_HOSTS
    # -----------------------------
    print("\n🌐 请输入 ALLOWED_HOSTS（多个用逗号分隔）")
    allowed_hosts_raw = get_input_with_default("ALLOWED_HOSTS", "")
    if allowed_hosts_raw:
        allowed_hosts = [h.strip() for h in allowed_hosts_raw.split(",") if h.strip()]
    else:
        allowed_hosts = []
    print(f"➡️ ALLOWED_HOSTS = {allowed_hosts}")

    # -----------------------------
    # 数据库配置（增强版）
    # -----------------------------
    print("\n🗄️ 请选择数据库类型:")
    print("1) sqlite")
    print("2) mysql")
    print("3) postgres")

    db_choice = get_input_with_default("请选择数据库类型 (1/2/3)", "1")

    if db_choice == "1":
        db_engine = "django.db.backends.sqlite3"
        db_name = get_input_with_default("数据库文件名", "db.sqlite3")
        db_user = ""
        db_password = ""
        db_host = ""
        db_port = ""
    elif db_choice == "2":
        db_engine = "django.db.backends.mysql"
        db_name = get_input_with_default("数据库名", "mydb")
        db_user = get_input_with_default("数据库用户", "root")
        db_password = get_input_with_default("数据库密码", "123456")
        db_host = get_input_with_default("数据库主机", "localhost")
        db_port = get_input_with_default("数据库端口", "3306")
    elif db_choice == "3":
        db_engine = "django.db.backends.postgresql"
        db_name = get_input_with_default("数据库名", "mydb")
        db_user = get_input_with_default("数据库用户", "postgres")
        db_password = get_input_with_default("数据库密码", "123456")
        db_host = get_input_with_default("数据库主机", "localhost")
        db_port = get_input_with_default("数据库端口", "5432")
    else:
        print("❌ 输入无效，默认使用 sqlite3")
        db_engine = "django.db.backends.sqlite3"
        db_name = "db.sqlite3"
        db_user = ""
        db_password = ""
        db_host = ""
        db_port = ""

    # -----------------------------
    # 存储配置（增强版）
    # -----------------------------
    print("\n📦 请输入存储模式:")
    storage_mode = get_input_with_default("存储模式 (local/cos/s3)", "local")

    cos_config = {}
    aws_config = {}

    if storage_mode == "cos":
        print("\n🔵 COS 配置:")
        cos_config = {
            "SECRET_ID": get_input_with_default("COS_SECRET_ID", ""),
            "SECRET_KEY": get_input_with_default("COS_SECRET_KEY", ""),
            "BUCKET": get_input_with_default("COS_BUCKET", ""),
            "ENDPOINT": get_input_with_default("COS_ENDPOINT", ""),
        }

    elif storage_mode == "s3":
        print("\n🟦 AWS S3 配置:")
        aws_config = {
            "ACCESS_KEY_ID": get_input_with_default("AWS_ACCESS_KEY_ID", ""),
            "SECRET_ACCESS_KEY": get_input_with_default("AWS_SECRET_ACCESS_KEY", ""),
            "BUCKET": get_input_with_default("AWS_BUCKET", ""),
            "REGION": get_input_with_default("AWS_REGION", ""),
        }

    # Telegram Bot
    print("\n🤖 Telegram Bot 配置:")
    telegram_token = get_input_with_default("TELEGRAM_BOT_TOKEN", "")

    # 构建配置 dict
    config = {
        "SECRET_KEY": secret_key,
        "ALLOWED_HOSTS": allowed_hosts,

        "DATABASE": {
            "ENGINE": db_engine,
            "NAME": db_name,
            "USER": db_user,
            "PASSWORD": db_password,
            "HOST": db_host,
            "PORT": db_port,
        },

        "STORAGE_MODE": storage_mode,
        "COS": cos_config,
        "AWS": aws_config,

        "TELEGRAM_BOT_TOKEN": telegram_token,
        "REPORT_DEFAULT_USER_ID":report_user_id
    }

    # 写入文件
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

    print(f"\n✅ 配置文件已生成: {config_file}")
    return config_file


if __name__ == "__main__":
    generate_config_file()
