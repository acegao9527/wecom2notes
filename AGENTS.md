# Codex 使用约定

## 过程要求
- 所有过程描述和对答，用中文,务必记住用中文交互

## 代码变更流程
- **功能块完成后提交推送**：每次完成一个独立功能块，并完成构建验证后，默认执行 `git add`、`git commit`、按当前分支策略合并，并 `git push` 到远程仓库；若目标分支、远程仓库或合并方式不明确，先向用户确认。
- **提交前必须展示结果**：提交前应说明本次变更范围、关键验证结果和将要提交的文件；如需 commit message，可先给出草稿。
- **代码修改后必须自测**：每次修改代码后，必须使用 `./docker-deploy.sh` 重新构建并启动容器，然后通过 `curl` 或其他方式验证修改点是否工作正常，严禁只改代码不验证。
- **验证日志**：验证过程中应检查 `docker logs` 确保没有新的 traceback 或错误日志。
- **测试环境处理**：
  - **Linux 环境**：视为生产部署环境，测试通过后保持容器运行
  - **Mac 环境**：视为本地测试环境，测试完成后务必关闭测试容器

## 技术栈
- **语言**：Python 3.12
- **框架**：FastAPI + uvicorn
- **数据库**：SQLite
- **部署**：Docker + Docker Compose
- **集成**：企业微信消息归档、Craft 笔记

## 企业微信相关
- 归档消息使用 SDK（`libWeWorkFinanceSdk.so`）拉取
- SDK 文件存放路径：
  - Linux 服务器：`lib/wework-x86_64/libWeWorkFinanceSdk_C.so`
  - Mac Docker 容器：`lib/wework-x86_64/libWeWorkFinanceSdk_C.so`
- 消息存档 Secret 从 `WECOM_APP_SECRET` 环境变量读取
- Mac 本地开发：设置 `WECOM_DISABLE_SDK=true` 禁用 SDK（Mac 无法加载 Linux .so 文件）

## 数据库配置
- 数据库文件路径从 `SQLITE_DB_PATH` 环境变量读取
- 默认路径：`data/savehelper.db`

## 部署配置
- 本地调试：Mac 环境，Apple Silicon (M1/M2)
  - SDK 无法加载（Mac 不支持 Linux .so 格式），需设置 `WECOM_DISABLE_SDK=true`
  - 如需测试完整 SDK 功能，使用 `./docker-deploy.sh` 在容器内运行
- 生产部署：Linux 服务器，x86_64 架构
  - 自动加载 `lib/wework-x86_64/libWeWorkFinanceSdk_C.so`

## 项目文件
- `main.py`：主程序，处理回调和消息轮询
- `src/services/database.py`：SQLite 数据库服务
- `src/services/wecom.py`：企业微信 SDK 服务
- `src/services/craft.py`：Craft 集成
- `src/services/message_processor.py`：消息处理器
- `src/services/formatter.py`：消息格式化
- `src/services/binding_service.py`：用户绑定服务
- `src/api/routers/wecom.py`：企微 API 路由
- `src/api/routers/craft.py`：Craft API 路由
- `src/models/`：数据模型定义
- `src/handlers/`：消息处理 handler
