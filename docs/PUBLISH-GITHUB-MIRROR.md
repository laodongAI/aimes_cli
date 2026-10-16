# AIMES CLI：GitHub 根目录完整镜像发布

## 推荐方式：交互式发布向导

安装/升级到 AIMES CLI 0.7.4 后，在项目目录执行：

```powershell
aimes publish
```

向导会让你选择已有配置或新建配置，确认本地项目目录、GitHub 仓库、目标分支和提交说明。AIMES 会扫描项目标志文件识别技术栈，自动叠加对应的构建/缓存过滤规则，并读取根目录 `.gitignore` 中的正向排除规则，不再要求每次手工输入额外排除规则。之后先生成预览，展示新增、更新、删除、未变化和过滤掉的文件，并报告识别出的技术栈。只有输入精确的 `PUBLISH` 才会执行推送。若目标仓库尚无提交，AIMES 会识别空仓库并在预览中提示；首次发布将创建初始提交，未指定分支时优先使用远端声明的默认分支，否则回退到 `main`。

发布配置保存在用户目录 `~/.aimes/publish-profiles.json`（Windows 下通常是用户主目录中的 `.aimes` 目录）。配置只保存项目路径、仓库、分支、提交说明和排除规则，不保存 GitHub Token 或密码。可通过环境变量 `AIMES_CONFIG_HOME` 指定配置目录。

## 复用配置与参数模式

```powershell
# 列出已保存的配置
aimes publish --list-profiles

# 使用配置并预览
aimes publish --profile my-project

# 保存/更新配置
aimes publish --source "E:\work\my-project" --repo "owner/repository" --branch main --save-profile my-project

# 在默认过滤规则之外追加排除项（可重复）
aimes publish --source "E:\work\my-project" --repo "owner/repository" --exclude "test-data/**" --exclude "*.local.json"

# 脚本模式：先生成预览，再执行（需要显式确认）
aimes publish --profile my-project --apply --confirm PUBLISH
```

非交互模式默认只预览；`--apply` 与 `--confirm PUBLISH` 缺一不可。执行时使用普通非强制 Git push。

## 默认忽略规则

- Python 环境：`.venv/`、`venv/`、`env/`、`site-packages/`、`__pycache__/`、`*.pyc`、`*.pyo`、`*.pyd`。
- Node 和构建：`node_modules/`、`build/`、`dist/`、`coverage/`、`htmlcov/`。根据检测到的项目标志文件，还会追加适用规则，例如 Node.js 的 `.next/`、`.nuxt/`、`.vite/`，Java 的 `target/`、`.gradle/`，Go 的 `bin/`，Rust 的 `target/`，.NET 的 `bin/`、`obj/`，Python 的测试/打包缓存等。
- AI 工具辅助目录：`.claude/`、`.codex/`、`.cursor/`、`.aider/`、`.continue/`、`.windsurf/`、`.trae/`、`.qoder/`、`.zcode/`、`.gemini/`、`.opencode/`、`.copilot/`。
- 运行与缓存：`logs/`、`log/`、`tmp/`、`temp/`、`runtime/`、`.cache/`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`。
- 运行文件和编译产物：`*.log`、`*.pid`、`*.tmp`、`*.bak`、`*.swp`、`*.class`、`*.so`、`*.dll`、`*.dylib`。
- 凭据：常见 `.env*`、私钥/证书、凭据 JSON 和访问令牌等。

默认过滤是安全基线，不等同于完整的秘密检测。项目源码、`requirements.txt`、`pyproject.toml`、`package.json`、锁文件和常规文档不会仅因它们是配置文件而被排除。默认安全规则不可通过自定义规则取消。

自动规则和 `.gitignore` 之外仍可用自定义 `--exclude` 追加规则，支持文件名匹配、通配符和相对路径规则，例如 `*.local.json`、`test-data/**`、`src/generated/client.py`。多个规则可重复传入；已有发布配置中的自定义规则仍会继续生效。

## 完整镜像语义与安全边界

完整镜像意味着：目标分支中存在、但本地过滤后源目录中不存在的文件会被删除。因此目标仓库根目录是同步边界，不是双向合并。每次执行前必须检查删除清单。

- 需要目标仓库已存在，且本机 Git 已配置认证。已有仓库使用目标分支；空仓库可以在首次发布时创建目标分支和初始提交。
- 不复制 `.git` 元数据和符号链接，不执行源项目脚本。
- 扫描常见私钥标记、GitHub Token、AWS Access Key 和 OpenAI API Key 样式；检测到疑似密钥时，执行模式会中止。该扫描是启发式的，不能保证发现所有秘密。
- 使用普通 `git push`，不强制覆盖远端历史；并发更新导致推送被拒绝时，请重新预览。
- 源目录必须存在且至少含一个可发布文件；文件系统根目录会被拒绝。
