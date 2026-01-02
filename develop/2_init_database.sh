#!/bin/bash
set -e

# 配置参数（使用huisubot项目相关命名）
DB_NAME="huisuobot_db"
DB_USER="huisuobot_user"
DB_PASSWORD="HuisuoBot@2026"  # 动态生成带月份后缀的密码
ALLOW_REMOTE="false"  # 是否允许远程访问（true/false，按需修改）

echo "=================================================="
echo "🗄️  开始初始化MySQL数据库 - huisuobot项目..."
echo "=================================================="

# 检查是否为root用户
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ 错误：必须以root用户执行！"
    exit 1
fi

# 启动MySQL并设置开机自启
systemctl start mysql
systemctl enable mysql
echo "✅ MySQL服务启动成功"

# 检查MySQL root密码是否需要设置
echo "ℹ️ 检查MySQL安全配置..."
if mysql -u root -e "SELECT 1;" 2>/dev/null; then
    echo "✅ MySQL root用户可访问"
else
    echo "⚠️ MySQL root需要密码，请先运行 mysql_secure_installation"
    echo "📝 或者使用临时命令设置密码："
    echo "   sudo mysql -e \"ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '新密码';\""
    exit 1
fi

# 检查数据库是否已存在
if mysql -u root -e "USE ${DB_NAME};" 2>/dev/null; then
    echo "ℹ️ 数据库 ${DB_NAME} 已存在，跳过创建"
else
    # 创建数据库和用户（指定认证方式+密码转义）
    echo "ℹ️ 创建数据库和用户..."
    mysql -u root <<EOF
-- 创建数据库
CREATE DATABASE IF NOT EXISTS ${DB_NAME}
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

-- 创建本地用户（显式指定 mysql_native_password 认证，兼容 pymysql）
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost'
IDENTIFIED WITH mysql_native_password BY '${DB_PASSWORD}';

-- 授予数据库权限（最小化原则）
GRANT ALL PRIVILEGES ON ${DB_NAME}.*
TO '${DB_USER}'@'localhost';

-- 如果允许远程访问，创建远程用户
$(if [ "${ALLOW_REMOTE}" = "true" ]; then
    echo "CREATE USER IF NOT EXISTS '${DB_USER}'@'%'"
    echo "IDENTIFIED WITH mysql_native_password BY '${DB_PASSWORD}';"
    echo "GRANT ALL PRIVILEGES ON ${DB_NAME}.*"
    echo "TO '${DB_USER}'@'%';"
    echo "FLUSH PRIVILEGES;"
fi)

FLUSH PRIVILEGES;
EOF
    echo "✅ 数据库 ${DB_NAME} 和用户 ${DB_USER} 创建成功"
fi

# 验证数据库连接
echo "ℹ️ 验证数据库连接..."
if mysql -u "${DB_USER}" -p"${DB_PASSWORD}" -e "USE ${DB_NAME};" 2>/dev/null; then
    echo "✅ 数据库连接测试成功"
else
    echo "❌ 数据库连接测试失败！"
    exit 1
fi

# 显示数据库信息
echo "=================================================="
echo "🎉 huisuobot项目数据库初始化完成！"
echo "=================================================="
echo "📋 数据库配置信息："
echo "   数据库名：${DB_NAME}"
echo "   用户名：${DB_USER}"
echo "   密码：${DB_PASSWORD}"
echo "   主机：localhost"
echo "   端口：3306"
echo "   字符集：utf8mb4"
echo "   权限：$(if [ "${ALLOW_REMOTE}" = "true" ]; then echo "本地+远程"; else echo "仅本地"; fi)"
echo "   认证方式：mysql_native_password（兼容pymysql）"
echo ""
echo "🔧 Django数据库配置建议："
echo "   DATABASES = {"
echo "       'default': {"
echo "           'ENGINE': 'django.db.backends.mysql',"
echo "           'NAME': '${DB_NAME}',"
echo "           'USER': '${DB_USER}',"
echo "           'PASSWORD': '${DB_PASSWORD}',"
echo "           'HOST': 'localhost',"
echo "           'PORT': '3306',"
echo "           'OPTIONS': {"
echo "               'charset': 'utf8mb4',"
echo "           },"
echo "       }"
echo "   }"
echo "=================================================="

# 生成配置文件（可选）
CONFIG_FILE="/etc/huisuobot/database.conf"
mkdir -p /etc/huisuobot
cat > ${CONFIG_FILE} <<EOF
# huisuobot项目数据库配置
# 生成时间: $(date)
DB_NAME="${DB_NAME}"
DB_USER="${DB_USER}"
DB_PASSWORD="${DB_PASSWORD}"
DB_HOST="localhost"
DB_PORT="3306"
DB_CHARSET="utf8mb4"
EOF
chmod 600 ${CONFIG_FILE}
chown huisuobot:huisuobot ${CONFIG_FILE}
echo "📄 配置文件已保存至: ${CONFIG_FILE}"