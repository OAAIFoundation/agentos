# Edit and Save功能使用说明

## 概述

AgentOS Dashboard 现在支持直接在 Web 界面中编辑 Provider 和 Route 配置，无需手动修改 YAML 文件。

## 功能特性

### Provider 编辑
- ✅ 修改 Base URL
- ✅ 修改 API Key (支持 `env:VAR_NAME` 格式)
- ✅ 实时保存到 config.yaml
- ✅ 自动创建备份文件

### Route 编辑
- ✅ 修改 Match Model 模式 (支持通配符 `*`)
- ✅ 选择 Target Provider (下拉菜单)
- ✅ 修改 Target Model (preserve 或具体模型名)
- ✅ 编辑 Keywords (逗号分隔)
- ✅ 实时保存到 config.yaml
- ✅ 自动热重载

## 使用方法

### 编辑 Provider

1. 打开 Dashboard: `http://localhost:8000/dashboard`
2. 点击左侧 "Providers" 导航项
3. 找到要编辑的 Provider 卡片
4. 点击右上角 "Edit" 按钮
5. 在弹出的对话框中修改配置：
   - Base URL: 完整的 API 端点地址
   - API Key: 使用 `env:VARIABLE_NAME` 格式引用环境变量，或直接输入密钥
6. 点击 "Save Changes" 保存
7. 系统自动创建 `config.yaml.backup` 备份文件
8. 配置立即生效，无需重启服务

### 编辑 Route

1. 打开 Dashboard: `http://localhost:8000/dashboard`
2. 点击左侧 "Route Rules" 导航项
3. 找到要编辑的 Route 卡片
4. 点击右上角 "Edit" 按钮
5. 在弹出的对话框中修改配置：
   - **Match Model Pattern**: 使用 `*` 通配符匹配模型名
     - 示例: `gpt-4*` 匹配所有 gpt-4 系列模型
   - **Target Provider**: 从下拉菜单选择目标提供商
   - **Target Model**: 
     - 使用 `preserve` 保持原模型名
     - 或输入具体模型名如 `gpt-4o-mini`
   - **Keywords**: 用逗号分隔的关键词列表
     - 示例: `translate, summary, summarize`
     - 留空表示匹配所有 prompt
6. 点击 "Save Changes" 保存
7. 配置立即生效，路由规则自动更新

## 安全特性

- ✅ **自动备份**: 每次保存前自动创建 `config.yaml.backup`
- ✅ **配置验证**: 后端会验证配置结构，拒绝无效配置
- ✅ **热重载**: 配置更新后自动重载，无需重启服务
- ✅ **错误提示**: 保存失败时显示清晰的错误消息

## API 端点

编辑功能使用现有的配置 API：

- **GET** `/api/config` - 获取当前配置
- **POST** `/api/config` - 保存配置 (Content-Type: application/json)

## 测试

运行测试确保编辑功能正常工作：

```bash
python tests/test_edit_save.py
```

测试覆盖：
- ✅ Provider 编辑和保存
- ✅ Route 编辑和保存
- ✅ Keywords 修改
- ✅ 无效配置拒绝
- ✅ 备份文件创建

## 示例

### 修改 Provider URL

修改前:
```yaml
ollama:
  base_url: "http://localhost:11434/v1"
  api_key: "ollama"
```

操作: 点击 Edit → 修改 base_url 为 `http://localhost:11435/v1` → Save

修改后:
```yaml
ollama:
  base_url: "http://localhost:11435/v1"
  api_key: "ollama"
```

### 修改 Route 规则

修改前:
```yaml
- match_model: "gpt-4o"
  target_provider: "openai"
  target_model: "preserve"
```

操作: 点击 Edit → 修改 target_model 为 `gpt-4o-mini` → 添加 Keywords: `translate, summary` → Save

修改后:
```yaml
- match_model: "gpt-4o"
  contains_keywords: ["translate", "summary"]
  target_provider: "openai"
  target_model: "gpt-4o-mini"
```

## 注意事项

1. **备份文件**: 每次保存会覆盖 `config.yaml.backup`，如需保留历史备份请手动复制
2. **环境变量**: API Key 建议使用 `env:VAR_NAME` 格式，避免硬编码敏感信息
3. **通配符**: Match Model 支持 `*` 通配符，如 `gpt-4*` 匹配所有 gpt-4 系列
4. **热重载**: 配置保存后立即生效，正在进行的请求不受影响
5. **验证**: 后端会验证配置结构，缺少 `providers` 或 `routes` 字段会被拒绝

## 故障排除

### 保存失败 (400 Bad Request)
- 检查配置结构是否完整
- 确保 `providers` 和 `routes` 字段存在
- 查看浏览器控制台的错误详情

### 保存失败 (500 Internal Server Error)
- 检查 YAML 格式是否正确
- 查看服务器日志: `config.yaml` 写入权限
- 确认 `config/` 目录存在

### 修改未生效
- 刷新页面重新加载配置
- 检查 `config.yaml` 文件内容
- 查看服务器日志确认热重载成功

## 更多信息

- GitHub: https://github.com/OAAIFoundation/agentos
- Dashboard: http://localhost:8000/dashboard
- API 文档: http://localhost:8000/docs
