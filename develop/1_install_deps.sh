#!/bin/bash
set -e  # 出错立即退出

# 检查是否为root用户
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ 错误：必须以root用户执行！"
    exit 1
fi

echo "=================================================="
echo "📦 开始安装系统依赖 - huisuobot项目..."
echo "=================================================="

# 更新系统
apt update -y && apt upgrade -y

# 安装核心依赖
apt install -y python3-pip python3-venv \
mysql-server nginx git supervisor redis-server \
gcc libmysqlclient-dev libssl-dev libffi-dev \
libxml2-dev libxslt1-dev zlib1g-dev

echo "=================================================="
echo "👤 开始创建项目专用系统用户..."
echo "=================================================="

# 创建系统用户huisuobot（无登录密码，仅用于运行项目）
if id -u "huisuobot" >/dev/null 2>&1; then
    echo "ℹ️ 用户huisuobot已存在，跳过创建"
else
    useradd -m -s /bin/bash huisuobot
    echo "✅ 用户huisuobot创建成功"
fi

# 创建项目目录结构
mkdir -p /var/www/huisuobot
mkdir -p /var/log/huisuobot
mkdir -p /etc/huisuobot

# 授权项目目录权限
chown -R huisuobot:huisuobot /var/www/huisuobot
chown -R huisuobot:huisuobot /var/log/huisuobot
chmod 755 /var/www/huisuobot

# 给huisuobot添加sudo权限（仅允许必要操作）
if [ ! -f "/etc/sudoers.d/huisuobot" ]; then
    echo "huisuobot ALL=(ALL) NOPASSWD:/usr/bin/systemctl,/usr/sbin/nginx,/usr/bin/supervisorctl" > /etc/sudoers.d/huisuobot
    chmod 440 /etc/sudoers.d/huisuobot  # 必须设置440权限，否则sudo报错
    echo "✅ 用户huisuobot sudo权限配置完成"
fi

# 启动并设置Redis开机自启（Django-Q队列用）
systemctl start redis-server
systemctl enable redis-server
echo "✅ Redis服务启动成功"

# 启动并设置MySQL开机自启
systemctl start mysql
systemctl enable mysql
echo "✅ MySQL服务启动成功"

echo "=================================================="
echo "📁 项目目录结构："
echo "   /var/www/huisuobot      - 项目代码目录"
echo "   /var/log/huisuobot      - 项目日志目录"
echo "   /etc/huisuobot          - 项目配置文件目录"
echo "=================================================="

echo "=================================================="
echo "🎉 huisuobot项目系统环境配置完成！"
echo "下一步：切换到huisuobot用户执行 2_init_database.sh.sh"
echo "=================================================="