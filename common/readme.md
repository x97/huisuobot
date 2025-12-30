### 概览

按钮的核心是两件事：**UI 文本** 和 **callback_data**。UI 负责展示给用户，callback_data 是 Telegram 在用户点击时回传给机器人的短字符串，用来路由和携带必要参数。我们把 callback_data 设计成**命名空间化、短小且可解析**的格式，便于统一路由、权限校验和维护。

---

### callback_data 格式

**格式**  
```
<prefix>:<action>[:<arg1>[:<arg2>...]]
```

**含义**  
- **prefix**：命名空间，标识哪个模块负责处理（例如 `reports`、`tgusers`、`core`）。  
- **action**：动作名，表示要执行的操作（例如 `back_main`、`approve`、`my_reports`）。  
- **args**：可选参数，通常只放短 id 或页码，避免放长文本。参数会 URL 编码以防止冒号或特殊字符冲突。

**示例**  
- `core:back_main` 返回主菜单。  
- `reports:my_reports:2` 查看报告列表第 2 页。  
- `reports:approve:123` 管理员通过报告 id=123。

---

### 生成按钮的工具与示例

**工具职责**  
- `make_cb(prefix, action, *args)` 负责生成短小、编码后的 callback_data。  
- `single_button(label, prefix, action, *args)` 返回 `InlineKeyboardButton`，只负责 UI。  
- `append_back_button(keyboard, text="🔙 返回主菜单")` 在任意键盘后追加统一的返回按钮（默认 callback 为 `core:back_main`）。

**示例代码**
```python
# 生成 callback_data
cb = make_cb("core", "back_main")  # -> "core:back_main"

# 生成单个按钮
btn = single_button("🔙 返回主菜单", "core", "back_main")

# 在已有 keyboard 后追加返回按钮
kb = append_back_button(existing_keyboard)
```

**注意**  
- `make_cb` 会对参数做 URL 编码，确保安全。  
- 只在 callback_data 里传短 id 或页码，避免超过 Telegram 的 64 字节限制。

---

### 解析与路由

**解析函数**  
- `parse_cb(callback_data)` 返回 `(prefix, action, args)`，用于统一路由。

**路由模式**  
- 在 `core_bot` 或 app 的注册入口，按 prefix 注册 handler，例如：
  - `CallbackQueryHandler(reports_router, pattern=r"^reports:")` 由 `reports` 模块处理所有 `reports:` 回调。  
  - `CallbackQueryHandler(back_to_main_handler, pattern=r"^core:back_main$")` 处理返回主菜单。

**示例解析**
```python
prefix, action, args = parse_cb(query.data)
if prefix == "reports" and action == "approve":
    report_id = int(args[0])
    approve_report(report_id)
```

---

### Handler 设计与权限

**职责分离**  
- 按钮工厂只生成 UI（`reports/keyboards.py`）。  
- Handler 只解析 callback_data、做权限校验并调用业务函数（`reports/services.py`）。

**权限检查**  
- 在 handler 内做权限校验（例如 `user.is_admin`），不要只依赖 callback_data pattern。  
- 对敏感操作（通过、驳回、发放积分）在 handler 开头强制校验并 `query.answer("无权限")`。

**会话与 ConversationHandler**  
- 对话内按钮（如确认/取消）也使用命名空间，例如 `reports:confirm_report`、`reports:cancel_report`，并在 ConversationHandler 的 states 中用相应 pattern 注册。

---

### 最佳实践与注意事项

- **短小参数**：callback_data 总长度 < 64 字节，只传 id 或页码。  
- **URL 编码**：通过 `make_cb` 自动编码参数，避免冒号或特殊字符问题。  
- **统一前缀**：每个 app 固定 prefix（例如 `reports`），便于集中注册与日志追踪。  
- **回退按钮统一**：使用 `core:back_main` 作为全局返回主菜单的 callback，`core` 提供统一处理函数。  
- **测试覆盖**：为 `make_cb`/`parse_cb`、路由 handler、权限分支写单元测试。  
- **可读性**：action 命名要短且语义明确（`approve`、`reject`、`view`、`my_reports`、`report_page`）。

---

如果你愿意，我可以把 `make_cb`、`parse_cb`、`single_button`、`append_back_button` 的完整实现和几个常用按钮工厂（例如 `reports.my_reports_entry_button`、`reports.admin_actions`）直接生成给你，方便你粘贴到项目里。你想要我现在把这些工具文件生成出来吗