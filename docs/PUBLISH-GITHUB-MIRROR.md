# AIMES CLI：GitHub 根目录完整镜像发布

## 目的与边界

`aimes publish` 将本地项目完整镜像到一个已有 GitHub 仓库的根目录。它使用本机 Git CLI 和 Git 已配置的认证方式，不要求将 GitHub Token 保存到 AIMES 配置中。

完整镜像意味着：目标分支中存在、但本地源目录中不存在的文件会被删除。因此请把 `--source` 指向你确实希望成为仓库完整内容的项目目录。该命令不会只更新某个子目录；仓库根目录是同步边界。

## 前置条件

- Python 3.10+，AIMES CLI 已安装。
- 本机已安装 Git，`git --version` 可正常运行。
- 本机已配置 GitHub HTTPS 凭据；当前实现将 GitHub 仓库规范化为 HTTPS URL。
- 对目标仓库具有写权限，且目标分支已存在并可克隆。

## 第一步：仅预览（默认行为）

```powershell
aimes publish --source "E:\work\my-project" --repo "owner/repository"
aimes publish --source "E:\work\my-project" --repo "owner/repository" --branch "main" --format json
```

预览会临时克隆远端分支并比较文件内容，输出新增、更新、删除、未变化的文件清单；不会提交或推送。未指定 `--branch` 时使用 GitHub 仓库默认分支。

## 第二步：确认后执行

```powershell
aimes publish --source "E:\work\my-project" --repo "owner/repository" --branch "main" --apply --confirm PUBLISH
```

`--apply` 与精确确认标记 `--confirm PUBLISH` 缺一不可。发布会在临时克隆中准备完整镜像、创建一个提交并普通推送；不会使用 `--force`。如果其他人同时更新了目标分支，推送将被 Git 拒绝，重新预览后再试。

## 安全规则

- 默认预览；不提供 `--apply` 不会推送。
- 不复制 `.git` 元数据、符号链接、虚拟环境、依赖目录、常见缓存/构建缓存、`.env*`、凭据文件和常见私钥文件。
- 对文本文件扫描常见私钥标记、GitHub Token、AWS Access Key 和 OpenAI API Key 样式。检测到疑似密钥时，执行模式会中止；预览仍会报告发现项。
- 不执行源项目脚本，不运行任意 Shell 命令；只调用固定的 Git 子命令。
- 使用普通 `git push`，不强制覆盖远端历史。远端并发更新导致推送被拒绝时，必须重新预览。
- 源目录必须存在且至少含一个可发布文件；文件系统根目录会被拒绝。
- 完整镜像会删除远端仓库根目录中所有不在本地镜像内的普通文件。执行前必须逐项检查删除清单。

## 重要限制

- 这是文件镜像，不是双向合并；远端独有文件不会保留。
- 敏感路径按规则排除，因此发布内容是排除安全/缓存路径后的本地镜像。
- 内容扫描只能识别部分常见密钥格式，不能保证发现所有秘密。不要把凭据放进项目源目录。
- 需要 GitHub 仓库已存在且目标分支可克隆；不负责创建仓库。
- 预览需要网络和 GitHub 读取权限；实际推送需要目标仓库写权限。
