#!/bin/bash
set -e

# 配置参数（与其他脚本一致）
PROJECT_NAME="huisuobot"
PROJECT_DIR="/var/www/huisuobot"
VENV_DIR="${PROJECT_DIR}/venv"
SYSTEM_USER="huisuobot"
SERVER_IP="192.168.1.100"  # 服务器IP/域名
DJANGO_APP_NAME="huisuobot"  # Django应用名称

# 路径定义
GUNICORN_SERVICE="/etc/systemd/system/${PROJECT_NAME}_web.service"
NGINX_CONF_SRC="nginx.conf"  # 同目录下的nginx配置文件
NGINX_CONF_DST="/etc/nginx/sites-available/${PROJECT_NAME}"
NGINX_CONF_ENABLED="/etc/nginx/sites-enabled/${PROJECT_NAME}"
SUPERVISOR_CONF_SRC="supervisor.conf"  # 同目录下的supervisor配置文件
SUPERVISOR_CONF_DST="/etc/supervisor/conf.d/${PROJECT_NAME}.conf"
LOG_DIR="/var/log/${PROJECT_NAME}"
PID_DIR="/var/run/${PROJECT_NAME}"

echo "=================================================="
echo "🚀 开始配置huisuobot系统服务..."
echo "=================================================="

# 检查是否为root用户
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ 错误：必须以root用户执行！"
    exit 1
fi

# 检查项目目录是否存在
if [ ! -d "${PROJECT_DIR}" ]; then
    echo "❌ 错误：项目目录不存在 ${PROJECT_DIR}"
    echo "请先执行 2_deploy_project.sh 部署项目"
    exit 1
fi

# 1. 配置Gunicorn Systemd服务
echo "ℹ️ 配置Gunicorn Web服务..."
cat > "${GUNICORN_SERVICE}" <<EOF
[Unit]
Description=Gunicorn service for ${PROJECT_NAME}
After=network.target mysql.service redis-server.service
Requires=mysql.service redis-server.service

[Service]
User=${SYSTEM_USER}
Group=${SYSTEM_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${VENV_DIR}/bin"
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${VENV_DIR}/bin/gunicorn \\
          --workers 3 \\
          --threads 2 \\
          --bind 127.0.0.1:8001 \\
          --timeout 120 \\
          --log-level=info \\
          --access-logfile ${LOG_DIR}/gunicorn_access.log \\
          --error-logfile ${LOG_DIR}/gunicorn_error.log \\
          --pid ${PID_DIR}/gunicorn.pid \\
          ${DJANGO_APP_NAME}.wsgi:application
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
KillMode=mixed
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo "✅ Gunicorn服务配置完成"

# 2. 配置Nginx反向代理
echo "ℹ️ 配置Nginx反向代理..."

# 检查Nginx配置文件是否存在
if [ ! -f "${NGINX_CONF_SRC}" ]; then
    echo "⚠️ 未找到Nginx配置文件 ${NGINX_CONF_SRC}，创建默认配置..."
    cat > "${NGINX_CONF_SRC}" <<EOF
# huisuobot项目Nginx配置
server {
    listen 80;
    server_name ${SERVER_IP};

    # 静态文件
    location /static/ {
        alias ${PROJECT_DIR}/staticfiles/;
        expires 30d;
        access_log off;
    }

    # 媒体文件
    location /media/ {
        alias ${PROJECT_DIR}/media/;
        expires 30d;
        access_log off;
    }

    # Django应用
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        send_timeout 300s;
    }

    # 禁止访问敏感文件
    location ~ /\.(?!well-known) {
        deny all;
    }

    location ~ /(\.env|\.git|\.sqlite3|\.pyc$) {
        deny all;
    }

    # 访问日志
    access_log ${LOG_DIR}/nginx_access.log;
    error_log ${LOG_DIR}/nginx_error.log;
}
EOF
    echo "✅ 默认Nginx配置已创建"
fi

# 复制Nginx配置
cp "${NGINX_CONF_SRC}" "${NGINX_CONF_DST}"

# 启用Nginx配置
if [ -L "${NGINX_CONF_ENABLED}" ]; then
    rm -f "${NGINX_CONF_ENABLED}"
fi
ln -s "${NGINX_CONF_DST}" "${NGINX_CONF_ENABLED}"
echo "✅ Nginx配置完成"

# 3. 配置Supervisor（用于后台任务和bot）
echo "ℹ️ 配置Supervisor服务..."

# 检查Supervisor配置文件是否存在
if [ ! -f "${SUPERVISOR_CONF_SRC}" ]; then
    echo "⚠️ 未找到Supervisor配置文件 ${SUPERVISOR_CONF_SRC}，创建默认配置..."
    cat > "${SUPERVISOR_CONF_SRC}" <<EOF
[program:${PROJECT_NAME}_qcluster]
command=${VENV_DIR}/bin/python manage.py qcluster
directory=${PROJECT_DIR}
user=${SYSTEM_USER}
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=${LOG_DIR}/qcluster.log
stderr_logfile=${LOG_DIR}/qcluster_error.log
environment=PATH="${VENV_DIR}/bin",DJANGO_SETTINGS_MODULE="${DJANGO_APP_NAME}.settings"

[program:${PROJECT_NAME}_bot]
command=${VENV_DIR}/bin/python manage.py runbot
directory=${PROJECT_DIR}
user=${SYSTEM_USER}
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=${LOG_DIR}/bot.log
stderr_logfile=${LOG_DIR}/bot_error.log
environment=PATH="${VENV_DIR}/bin",DJANGO_SETTINGS_MODULE="${DJANGO_APP_NAME}.settings"
EOF
    echo "✅ 默认Supervisor配置已创建"
fi

# 复制Supervisor配置
cp "${SUPERVISOR_CONF_SRC}" "${SUPERVISOR_CONF_DST}"
echo "✅ Supervisor配置完成"

# 4. 创建必要的目录并设置权限
echo "ℹ️ 创建目录并设置权限..."

# 创建日志目录
mkdir -p "${LOG_DIR}" "${PID_DIR}" "/var/log/supervisor"

# 设置目录权限
chown -R "${SYSTEM_USER}:${SYSTEM_USER}" "${LOG_DIR}" "${PID_DIR}" "${PROJECT_DIR}/logs" "${PROJECT_DIR}/data"
chmod 755 "${LOG_DIR}" "${PID_DIR}"
chmod 700 "${PROJECT_DIR}/logs" "${PROJECT_DIR}/data"

# 设置项目目录权限
chown -R "${SYSTEM_USER}:${SYSTEM_USER}" "${PROJECT_DIR}"
chmod 755 "${PROJECT_DIR}"
find "${PROJECT_DIR}" -type d -exec chmod 755 {} \;
find "${PROJECT_DIR}" -type f -exec chmod 644 {} \;
chmod 600 "${PROJECT_DIR}/.env"

echo "✅ 目录权限设置完成"

# 5. 启动所有服务
echo "ℹ️ 启动系统服务..."

# 启动Gunicorn
systemctl daemon-reload
systemctl enable "${PROJECT_NAME}_web"
systemctl start "${PROJECT_NAME}_web"
echo "✅ Gunicorn服务已启动"

# 测试并重启Nginx
echo "ℹ️ 测试Nginx配置..."
nginx -t
if [ $? -eq 0 ]; then
    systemctl restart nginx
    echo "✅ Nginx服务已重启"
else
    echo "❌ Nginx配置错误！"
    nginx -t
    exit 1
fi

# 启动Supervisor
supervisorctl reread
supervisorctl update
supervisorctl start all
echo "✅ Supervisor服务已启动"

# 设置开机自启
systemctl enable nginx
systemctl enable supervisor
echo "✅ 服务开机自启已设置"

# 6. 验证服务状态
echo "=================================================="
echo "✅ huisuobot服务配置完成，状态检查："
echo "--------------------------------------------------"

sleep 2  # 等待服务启动

check_service() {
    local service_name=$1
    local description=$2
    if systemctl is-active --quiet "${service_name}"; then
        echo "✅ ${description}：运行中"
        return 0
    else
        echo "❌ ${description}：未运行"
        systemctl status "${service_name}" --no-pager -l
        return 1
    fi
}

check_supervisor_program() {
    local program_name=$1
    local description=$2
    if supervisorctl status "${program_name}" 2>/dev/null | grep -q "RUNNING"; then
        echo "✅ ${description}：运行中"
        return 0
    else
        echo "⚠️ ${description}：未运行或检查失败"
        supervisorctl status "${program_name}"
        return 1
    fi
}

check_service "${PROJECT_NAME}_web" "Gunicorn Web服务"
check_service "nginx" "Nginx服务"
check_service "supervisor" "Supervisor服务"
check_supervisor_program "${PROJECT_NAME}_qcluster" "Django-Q队列服务"
check_supervisor_program "${PROJECT_NAME}_bot" "Bot服务"

echo "=================================================="
echo "🎉 huisuobot所有服务配置完成！"
echo "=================================================="
echo "📋 服务信息汇总："
echo "   Web访问: http://${SERVER_IP}"
echo "   管理后台: http://${SERVER_IP}/admin"
echo "   静态文件: ${PROJECT_DIR}/staticfiles"
echo "   媒体文件: ${PROJECT_DIR}/media"
echo "   日志目录: ${LOG_DIR}"
echo ""
echo "🔧 管理命令："
echo "   查看Gunicorn状态: sudo systemctl status ${PROJECT_NAME}_web"
echo "   查看Nginx状态: sudo systemctl status nginx"
echo "   查看Supervisor状态: sudo supervisorctl status"
echo "   查看服务日志: sudo tail -f ${LOG_DIR}/*.log"
echo "=================================================="

# 生成服务配置摘要
cat > "/etc/huisuobot/services.conf" <<EOF
# huisuobot项目服务配置摘要
# 生成时间: $(date)

[Services]
web_service = ${PROJECT_NAME}_web
nginx_config = ${NGINX_CONF_DST}
supervisor_config = ${SUPERVISOR_CONF_DST}
log_directory = ${LOG_DIR}
pid_directory = ${PID_DIR}

[Ports]
nginx_port = 80
gunicorn_port = 8001

[Access]
web_url = http://${SERVER_IP}
admin_url = http://${SERVER_IP}/admin
EOF

chmod 600 "/etc/huisuobot/services.conf"
echo "📄 服务配置摘要已保存至: /etc/huisuobot/services.conf"