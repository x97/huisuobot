#!/bin/bash
set -e

# 配置参数（根据实际情况修改！）
GIT_REPO="https://github.com/x97/huisuobot.git"  # 你的Git仓库地址
GIT_BRANCH="main"                                         # Git分支
PROJECT_DIR="/var/www/huisuobot"                          # 项目部署路径
VENV_DIR="${PROJECT_DIR}/venv"                            # 虚拟环境路径
SERVER_IP="192.168.1.100"                                 # 服务器IP/域名
DJANGO_APP_NAME="huisuobot"                               # Django应用名
DB_NAME="huisuobot_db"                                    # 数据库名（与数据库脚本一致）
DB_USER="huisuobot_user"                                  # 数据库用户（与数据库脚本一致）
DB_PASSWORD="HuisuoBot@$(date +%Y%m)"                     # 数据库密码（与数据库脚本一致）
DJANGO_SECRET_KEY="n6l*^t6n8dg(!^c0ay*9)^jwvv_u6x^g_3=8tfoijtvwt0tuz9"  # Django密钥

echo "=================================================="
echo "📥 开始部署huisuobot项目代码..."
echo "=================================================="

# 检查是否为huisuobot用户
if [ "$(whoami)" != "huisuobot" ]; then
    echo "❌ 错误：必须以huisuobot用户执行！"
    exit 1
fi

# 确保项目目录存在
mkdir -p "${PROJECT_DIR}"

# 克隆/更新项目代码
if [ -d "${PROJECT_DIR}/.git" ]; then
    echo "ℹ️ 项目已存在，拉取最新代码..."
    cd "${PROJECT_DIR}"
    git stash  # 暂存本地修改
    git checkout "${GIT_BRANCH}"
    git pull origin "${GIT_BRANCH}"
else
    echo "ℹ️ 克隆项目代码..."
    git clone -b "${GIT_BRANCH}" "${GIT_REPO}" "${PROJECT_DIR}"
    cd "${PROJECT_DIR}"
fi

echo "✅ 代码同步完成"

# 创建虚拟环境
echo "=================================================="
echo "🐍 配置Python虚拟环境..."
echo "=================================================="
if [ -d "${VENV_DIR}" ]; then
    echo "ℹ️ 虚拟环境已存在，激活并更新依赖..."
    source "${VENV_DIR}/bin/activate"
else
    echo "ℹ️ 创建虚拟环境..."
    python3 -m venv "${VENV_DIR}"
    source "${VENV_DIR}/bin/activate"
    pip install --upgrade pip setuptools wheel
    echo "✅ 虚拟环境创建成功"
fi

# 安装项目依赖
cd "${PROJECT_DIR}"
if [ -f "requirements.txt" ]; then
    echo "ℹ️ 安装requirements.txt中的依赖..."
    pip install -r requirements.txt
else
    echo "⚠️ 未找到requirements.txt，安装基础依赖..."
    pip install django gunicorn
    echo "✅ 基础依赖安装完成"
fi

# 检查并安装额外依赖
echo "ℹ️ 检查并安装可选依赖..."
if [ -f "requirements-extra.txt" ]; then
    pip install -r requirements-extra.txt
fi

# 安装项目管理依赖
pip install supervisor django-q redis django-redis
echo "✅ 所有依赖安装完成"

# 配置Django项目
echo "=================================================="
echo "⚙️ 配置Django项目..."
echo "=================================================="

# 检查Django项目结构
if [ ! -f "manage.py" ]; then
    echo "❌ 错误：未找到manage.py文件"
    exit 1
fi

# 创建环境变量文件
ENV_FILE="${PROJECT_DIR}/.env"
cat > "${ENV_FILE}" <<EOF
# huisuobot项目环境配置
# 生成时间: $(date)

# Django设置
DJANGO_SETTINGS_MODULE="${DJANGO_APP_NAME}.settings"
DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY}"
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=${SERVER_IP},localhost,127.0.0.1

# 数据库设置
DB_ENGINE=django.db.backends.mysql
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=localhost
DB_PORT=3306

# 静态文件设置
STATIC_ROOT=${PROJECT_DIR}/staticfiles
MEDIA_ROOT=${PROJECT_DIR}/media

# Redis设置
REDIS_URL=redis://127.0.0.1:6379/1
REDIS_CACHE_LOCATION=redis://127.0.0.1:6379/2

# 其他设置
DJANGO_TIME_ZONE=Asia/Shanghai
DJANGO_LANGUAGE_CODE=zh-hans
EOF

chmod 600 "${ENV_FILE}"
echo "✅ 环境配置文件创建成功: ${ENV_FILE}"

# 检查是否有配置生成脚本
if [ -f "scripts/generate_config.py" ]; then
    echo "ℹ️ 使用配置生成脚本..."
    python scripts/generate_config.py --env prod
elif [ -f "generate_config.py" ]; then
    echo "ℹ️ 使用配置生成脚本..."
    python generate_config.py --env prod
else
    echo "⚠️ 未找到配置生成脚本，使用手动配置..."
    # 如果settings.py不存在，创建基础配置
    if [ ! -f "${DJANGO_APP_NAME}/settings.py" ]; then
        echo "❌ 错误：未找到Django配置文件 ${DJANGO_APP_NAME}/settings.py"
        exit 1
    fi
fi

# 创建必要的目录
echo "ℹ️ 创建项目目录..."
mkdir -p "${PROJECT_DIR}/staticfiles"
mkdir -p "${PROJECT_DIR}/media"
mkdir -p "${PROJECT_DIR}/logs"
mkdir -p "${PROJECT_DIR}/data"

# 设置目录权限
chmod 755 "${PROJECT_DIR}/staticfiles" "${PROJECT_DIR}/media"
chmod 700 "${PROJECT_DIR}/logs" "${PROJECT_DIR}/data"

echo "✅ 目录创建完成"

# 数据库迁移
echo "=================================================="
echo "🗄️  初始化数据库..."
echo "=================================================="

# 测试数据库连接
echo "ℹ️ 测试数据库连接..."
python -c "
import os, sys
sys.path.append('${PROJECT_DIR}')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '${DJANGO_APP_NAME}.settings')
import django
django.setup()
from django.db import connection
try:
    connection.ensure_connection()
    print('✅ 数据库连接成功')
except Exception as e:
    print(f'❌ 数据库连接失败: {e}')
    sys.exit(1)
"

# 执行数据库迁移
echo "ℹ️ 执行数据库迁移..."
python manage.py makemigrations
python manage.py migrate

# 收集静态文件
echo "ℹ️ 收集静态文件..."
python manage.py collectstatic --noinput --clear

# 创建超级用户（如果不存在）
echo "ℹ️ 检查超级用户..."
python -c "
import os, sys
sys.path.append('${PROJECT_DIR}')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '${DJANGO_APP_NAME}.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@huisuobot.com', 'HuisuoAdmin@$(date +%Y%m)')
    print('✅ 超级用户创建成功: admin / HuisuoAdmin@$(date +%Y%m)')
else:
    print('ℹ️ 超级用户已存在')
"

# 创建必要的缓存表（如果使用Django Q）
echo "ℹ️ 创建缓存表..."
python manage.py createcachetable

echo "=================================================="
echo "🎉 huisuobot项目部署完成！"
echo "=================================================="
echo "📋 部署信息汇总："
echo "   项目目录: ${PROJECT_DIR}"
echo "   虚拟环境: ${VENV_DIR}"
echo "   环境配置: ${ENV_FILE}"
echo "   静态文件: ${PROJECT_DIR}/staticfiles"
echo "   媒体文件: ${PROJECT_DIR}/media"
echo "   数据库: ${DB_NAME} (用户: ${DB_USER})"
echo "   Django管理: admin / HuisuoAdmin@$(date +%Y%m)"
echo ""
echo "🔧 下一步操作："
echo "   1. 激活虚拟环境: source ${VENV_DIR}/bin/activate"
echo "   2. 测试运行: python manage.py runserver 0.0.0.0:8000"
echo "   3. 以root用户执行 3_config_services.sh 配置生产服务"
echo "=================================================="

# 生成部署完成标记文件
echo "$(date) - 部署完成" > "${PROJECT_DIR}/.deployed"
chmod 600 "${PROJECT_DIR}/.deployed"